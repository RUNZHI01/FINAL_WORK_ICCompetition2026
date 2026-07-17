param(
    [switch]$Deploy,
    [switch]$Verify,
    [switch]$BuildOta,
    [string]$BoardHost = "100.121.87.73",
    [string]$BoardUser = "user",
    [int]$BoardPort = 22,
    [string]$BoardPassword = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Workspace = "/workspace"
$OutTar = "$Workspace/artifacts/iq_board_sync.tar.gz"
$OutManifest = "$Workspace/artifacts/iq_board_sync_manifest.txt"
$RepoRootEnv = "REPO_ROOT=/workspace"
$OutTarEnv = "OUT_TAR=/workspace/artifacts/iq_board_sync.tar.gz"
$OutManifestEnv = "OUT_MANIFEST=/workspace/artifacts/iq_board_sync_manifest.txt"

function Write-IqSyncLog {
    param([string]$Message)
    Write-Host "[iq-sync] $Message"
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

docker image inspect "$ImageName" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-IqSyncLog "image $ImageName not found; building it first"
    docker build `
        -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
        -t "$ImageName" `
        "$ProjectRoot"
    Assert-LastExitCode "docker build"
}

New-Item -ItemType Directory -Force (Join-Path $ProjectRoot "artifacts") *> $null

Write-IqSyncLog "packing IQ direct board sync bundle with Docker"
docker run --rm `
    -v "${ProjectRoot}:$Workspace" `
    -e "$RepoRootEnv" `
    -e "$OutTarEnv" `
    -e "$OutManifestEnv" `
    "$ImageName" `
    bash "$Workspace/scripts/prepare_iq_board_sync.sh"
Assert-LastExitCode "prepare IQ board sync bundle"

Write-IqSyncLog "tar: $(Join-Path $ProjectRoot 'artifacts/iq_board_sync.tar.gz')"
Write-IqSyncLog "manifest: $(Join-Path $ProjectRoot 'artifacts/iq_board_sync_manifest.txt')"

if (-not $Deploy) {
    Write-IqSyncLog "package ready; pass -Deploy to synchronize it to the board"
    exit 0
}

if (-not $BoardPassword) {
    foreach ($candidate in @(
        $env:REMOTE_PASS,
        $env:REMOTE_PASSWORD,
        $env:PHYTIUM_PI_PASS,
        $env:PHYTIUM_PI_PASSWORD,
        $env:BOARD_PASS
    )) {
        if ($candidate) {
            $BoardPassword = $candidate
            break
        }
    }
}
if (-not $BoardPassword) {
    $secure = Read-Host "Board SSH password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $BoardPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

$DeployScript = @'
set -euo pipefail

ssh_common=(
  sshpass -e ssh -n
  -p "$REMOTE_SSH_PORT"
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/tmp/iq-board-sync-known-hosts
  -o ConnectTimeout=20
  -o ServerAliveInterval=5
  -o ServerAliveCountMax=2
  "${REMOTE_USER}@${REMOTE_HOST}"
)
scp_common=(
  sshpass -e scp
  -P "$REMOTE_SSH_PORT"
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/tmp/iq-board-sync-known-hosts
  -o ConnectTimeout=20
)

bundle=/workspace/artifacts/iq_board_sync.tar.gz
remote_bundle=/tmp/iq_board_sync.tar.gz
printf '[iq-sync] uploading bundle to %s@%s:%s\n' "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_SSH_PORT"
"${scp_common[@]}" "$bundle" "${REMOTE_USER}@${REMOTE_HOST}:${remote_bundle}"

"${ssh_common[@]}" 'set -euo pipefail
stage=$(mktemp -d /tmp/iq-board-sync.XXXXXX)
trap '\''rm -rf "$stage"'\'' EXIT
tar -xzf /tmp/iq_board_sync.tar.gz -C "$stage"
install -d /home/user/USRP292x /home/user/host_pic_to_latent/jscc/src
cp -f "$stage"/USRP292x/* /home/user/USRP292x/
cp -f "$stage"/host_pic_to_latent/jscc/src/test_model.py /home/user/host_pic_to_latent/jscc/src/test_model.py
cp -f "$stage"/scripts/tvm_inference_helper.py /home/user/tvm_inference_helper.py
cp -f "$stage"/scripts/latent_transport.py /home/user/latent_transport.py
chmod +x /home/user/USRP292x/*.sh
printf "[iq-sync] board files installed\n"'

local_hash=$(sha256sum "$bundle" | awk '{print $1}')
remote_hash=$("${ssh_common[@]}" "sha256sum '$remote_bundle'" | cut -d ' ' -f1)
if [[ "$local_hash" != "$remote_hash" ]]; then
  printf '[iq-sync] bundle hash mismatch: local=%s remote=%s\n' "$local_hash" "$remote_hash" >&2
  exit 1
fi
printf '[iq-sync] bundle hash verified: %s\n' "$local_hash"

for mapping in \
  'USRP292x/RunAnalogLatentBatch.py:/home/user/USRP292x/RunAnalogLatentBatch.py' \
  'USRP292x/OtaRxPersistentServer.cpp:/home/user/USRP292x/OtaRxPersistentServer.cpp' \
  'scripts/tvm_inference_helper.py:/home/user/tvm_inference_helper.py'; do
  local_path=${mapping%%:*}
  remote_path=${mapping#*:}
  local_hash=$(sha256sum "/workspace/$local_path" | awk '{print $1}')
  remote_hash=$("${ssh_common[@]}" "sha256sum '$remote_path'" | cut -d ' ' -f1)
  if [[ "$local_hash" != "$remote_hash" ]]; then
    printf '[iq-sync] file hash mismatch: %s\n' "$local_path" >&2
    exit 1
  fi
  printf '[iq-sync] file verified: %s\n' "$local_path"
done

if [[ "$VERIFY_BOARD" == "1" ]]; then
  "${ssh_common[@]}" 'set -euo pipefail
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate tvm310_safe
cd /home/user/USRP292x
python -m py_compile RunAnalogLatentBatch.py AnalogLatentLink.py
python /home/user/USRP292x/RunAnalogLatentBatch.py --help >/dev/null'
  printf '[iq-sync] board Python verification passed\n'
fi

if [[ "$BUILD_OTA" == "1" ]]; then
  "${ssh_common[@]}" 'set -euo pipefail
cd /home/user/USRP292x
OTA_TARGETS="OtaRxPersistentServer OtaTxPersistentServer" bash BuildOtaTools.sh'
  printf '[iq-sync] board OTA binaries rebuilt\n'
fi
'@

$DeployScriptB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($DeployScript))
$verifyFlag = if ($Verify) { "1" } else { "0" }
$buildFlag = if ($BuildOta) { "1" } else { "0" }

Write-IqSyncLog "deploying to $BoardUser@$BoardHost`:$BoardPort with Docker"
docker run --rm `
    -v "${ProjectRoot}:$Workspace" `
    -e "REMOTE_HOST=$BoardHost" `
    -e "REMOTE_USER=$BoardUser" `
    -e "REMOTE_SSH_PORT=$BoardPort" `
    -e "SSHPASS=$BoardPassword" `
    -e "VERIFY_BOARD=$verifyFlag" `
    -e "BUILD_OTA=$buildFlag" `
    -e "DEPLOY_SCRIPT_B64=$DeployScriptB64" `
    "$ImageName" `
    bash -lc 'printf "%s" "$DEPLOY_SCRIPT_B64" | base64 -d | bash'
Assert-LastExitCode "deploy IQ board sync bundle"

Write-IqSyncLog "board synchronization complete"
