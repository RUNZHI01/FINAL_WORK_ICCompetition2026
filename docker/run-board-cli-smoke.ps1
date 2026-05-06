$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$RemoteHost = if ($env:REMOTE_HOST) { $env:REMOTE_HOST } elseif ($env:PHYTIUM_PI_HOST) { $env:PHYTIUM_PI_HOST } else { "100.121.87.73" }
$RemoteUser = if ($env:REMOTE_USER) { $env:REMOTE_USER } elseif ($env:PHYTIUM_PI_USER) { $env:PHYTIUM_PI_USER } else { "user" }
$RemotePass = if ($env:REMOTE_PASS) { $env:REMOTE_PASS } elseif ($env:PHYTIUM_PI_PASSWORD) { $env:PHYTIUM_PI_PASSWORD } else { "" }
$StateVolume = if ($env:TAILSCALE_STATE_VOLUME) { $env:TAILSCALE_STATE_VOLUME } else { "iccomp-tailscale-state" }
$PingTarget = if ($env:TAILSCALE_PING_TARGET) { $env:TAILSCALE_PING_TARGET } else { $RemoteHost }
$BoardCliMaxInputs = if ($env:BOARD_CLI_MAX_INPUTS) { $env:BOARD_CLI_MAX_INPUTS } else { "300" }
$BoardDepsCacheRoot = if ($env:BOARD_DEPS_CACHE_ROOT) { $env:BOARD_DEPS_CACHE_ROOT } else { "/home/user/iccomp_board_deps_cache" }
$RefreshBoardDepsCache = if ($env:BOARD_CLI_REFRESH_CACHE) { $env:BOARD_CLI_REFRESH_CACHE } else { "0" }
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
SCRIPT_START_TS="$(date +%s)"

log() {
    printf '[board-cli-smoke] %s\n' "$*"
}

elapsed_since() {
    local start_ts="$1"
    local now_ts
    now_ts="$(date +%s)"
    printf '%ss' "$((now_ts - start_ts))"
}

human_bytes() {
    if command -v numfmt >/dev/null 2>&1; then
        numfmt --to=iec-i --suffix=B "$1"
    else
        printf '%s bytes' "$1"
    fi
}

run_step() {
    local label="$1"
    shift
    local step_start
    step_start="$(date +%s)"
    log "start: ${label}"
    "$@"
    log "done: ${label} ($(elapsed_since "${step_start}"))"
}

tar_excludes=(
    --exclude='.git'
    --exclude='Semantic-Communication/.git'
    --exclude='liboqs/.git'
    --exclude='Tongsuo/.git'
    --exclude='board_deps/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*'
    --exclude='board_deps/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz.part-*'
)

tailscale_start="$(date +%s)"
log "start: start tailscale"
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
log "done: start tailscale ($(elapsed_since "${tailscale_start}"))"
RUN_ROOT="/home/user/iccomp_repo_selfcontained_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
log "remote run root: ${RUN_ROOT}"
run_step "create remote run directory" "${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"

payload_bytes="$(du -sb "${tar_excludes[@]}" /repo | awk '{print $1}')"
log "upload payload apparent size: $(human_bytes "${payload_bytes}")"
log "uploading repository archive; compressed transfer is usually similar because runtimes and models are already compressed"
upload_start="$(date +%s)"
tar -C /repo "${tar_excludes[@]}" -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
log "done: upload and remote extract ($(elapsed_since "${upload_start}"))"
remote_repo_size="$("${ssh_common[@]}" "du -sh '${REMOTE_REPO}' | awk '{print \$1}'")"
log "remote repo size: ${remote_repo_size}"

if [ "${BOARD_CLI_REFRESH_CACHE:-0}" = "1" ]; then
    cache_start="$(date +%s)"
    log "refreshing reusable dependency cache: ${BOARD_DEPS_CACHE_ROOT}"
    "${ssh_common[@]}" "rm -rf '${BOARD_DEPS_CACHE_ROOT}.new' '${BOARD_DEPS_CACHE_ROOT}.old' && mkdir -p '${BOARD_DEPS_CACHE_ROOT}.new' && cp -a '${REMOTE_REPO}/board_deps' '${BOARD_DEPS_CACHE_ROOT}.new/board_deps' && if [ -e '${BOARD_DEPS_CACHE_ROOT}' ]; then mv '${BOARD_DEPS_CACHE_ROOT}' '${BOARD_DEPS_CACHE_ROOT}.old'; fi && mv '${BOARD_DEPS_CACHE_ROOT}.new' '${BOARD_DEPS_CACHE_ROOT}' && rm -rf '${BOARD_DEPS_CACHE_ROOT}.old'"
    log "done: refresh dependency cache ($(elapsed_since "${cache_start}"))"
fi

benchmark_start="$(date +%s)"
log "running isolated TVM/MNN/PyTorch benchmark; BOARD_CLI_MAX_INPUTS=${BOARD_CLI_MAX_INPUTS}"
"${ssh_common[@]}" "BOARD_CLI_MAX_INPUTS='${BOARD_CLI_MAX_INPUTS}' bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
log "done: isolated benchmark ($(elapsed_since "${benchmark_start}"))"
if "${ssh_common[@]}" "test -f '${RUN_ROOT}/logs/demo-kpi-summary.json'"; then
    log "demo KPI summary:"
    "${ssh_common[@]}" "cat '${RUN_ROOT}/logs/demo-kpi-summary.json'"
fi
run_size="$("${ssh_common[@]}" "du -sh '${RUN_ROOT}' | awk '{print \$1}'")"
log "remote run size: ${run_size}"
log "output root: ${RUN_ROOT}"
log "total elapsed: $(elapsed_since "${SCRIPT_START_TS}")"
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
    -e "BOARD_DEPS_CACHE_ROOT=$BoardDepsCacheRoot" `
    -e "BOARD_CLI_REFRESH_CACHE=$RefreshBoardDepsCache" `
    -e "LOCAL_SCRIPT_B64=$SmokeScriptB64" `
    "$ImageName" `
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'

if ($LASTEXITCODE -ne 0) {
    throw "board CLI smoke failed"
}
