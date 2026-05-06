$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$RemoteHost = if ($env:REMOTE_HOST) { $env:REMOTE_HOST } elseif ($env:PHYTIUM_PI_HOST) { $env:PHYTIUM_PI_HOST } else { "100.121.87.73" }
$RemoteUser = if ($env:REMOTE_USER) { $env:REMOTE_USER } elseif ($env:PHYTIUM_PI_USER) { $env:PHYTIUM_PI_USER } else { "user" }
$RemotePass = if ($env:REMOTE_PASS) { $env:REMOTE_PASS } elseif ($env:PHYTIUM_PI_PASSWORD) { $env:PHYTIUM_PI_PASSWORD } else { "" }
$StateVolume = if ($env:TAILSCALE_STATE_VOLUME) { $env:TAILSCALE_STATE_VOLUME } else { "iccomp-tailscale-state" }
$PingTarget = if ($env:TAILSCALE_PING_TARGET) { $env:TAILSCALE_PING_TARGET } else { $RemoteHost }
$BoardCliMaxInputs = if ($env:BOARD_CLI_MAX_INPUTS) { $env:BOARD_CLI_MAX_INPUTS } else { "300" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path

if (-not $RemotePass) {
    $SecurePass = Read-Host -Prompt "Enter board SSH password" -AsSecureString
    $Bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePass)
    try {
        $RemotePass = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
    }
    finally {
        if ($Bstr -ne [IntPtr]::Zero) {
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
        }
    }
}

if (-not $RemotePass) {
    throw "board SSH password is required for board CLI smoke."
}

docker image inspect "$ImageName" *> $null
if ($LASTEXITCODE -ne 0) {
    docker build `
        -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
        -t "$ImageName" `
        "$ProjectRoot"
    if ($LASTEXITCODE -ne 0) {
        throw "docker build failed"
    }
}

$SmokeScript = @'
set -euo pipefail
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
RUN_ROOT="/home/user/iccomp_repo_selfcontained_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
printf '[board-cli-smoke] remote run root: %s\n' "${RUN_ROOT}"
"${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"
tar -C /repo \
  --exclude='.git' \
  --exclude='Semantic-Communication/.git' \
  --exclude='liboqs/.git' \
  --exclude='Tongsuo/.git' \
  --exclude='board_deps/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*' \
  -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
"${ssh_common[@]}" "bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
printf '[board-cli-smoke] output root: %s\n' "${RUN_ROOT}"
'@

$SmokeScriptB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($SmokeScript))

docker run --rm `
    --cap-add=NET_ADMIN `
    --cap-add=NET_RAW `
    --device=/dev/net/tun `
    -v "${StateVolume}:/var/lib/tailscale" `
    -v "${ProjectRoot}:/repo:ro" `
    -e "TAILSCALE_PING_TARGET=$PingTarget" `
    -e "TS_LOGIN_WAIT_SEC=8" `
    -e "REMOTE_HOST=$RemoteHost" `
    -e "REMOTE_USER=$RemoteUser" `
    -e "SSHPASS=$RemotePass" `
    -e "BOARD_CLI_MAX_INPUTS=$BoardCliMaxInputs" `
    -e "LOCAL_SCRIPT_B64=$SmokeScriptB64" `
    "$ImageName" `
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'

if ($LASTEXITCODE -ne 0) {
    throw "board CLI smoke failed"
}
