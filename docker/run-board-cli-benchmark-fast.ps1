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
$KeepFastWork = if ($env:BOARD_CLI_FAST_KEEP_WORK) { $env:BOARD_CLI_FAST_KEEP_WORK } else { "0" }
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
    throw "board SSH password is required for board CLI benchmark."
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

$BenchmarkScript = @'
set -euo pipefail
SCRIPT_START_TS="$(date +%s)"

log() {
    printf '[board-cli-fast] %s\n' "$*"
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

fast_tar_excludes=(
    --exclude='.git'
    --exclude='Semantic-Communication/.git'
    --exclude='liboqs'
    --exclude='Tongsuo'
    --exclude='board_deps/runtime'
    --exclude='board_deps/openamp'
    --exclude='board_deps/tvm'
    --exclude='board_deps/mnn'
    --exclude='board_deps/pytorch'
    --exclude='board_deps/inputs'
    --exclude='board_deps/crypto'
    --exclude='**/node_modules'
    --exclude='**/__pycache__'
    --exclude='**/.pytest_cache'
)

tailscale_start="$(date +%s)"
log "start: start tailscale"
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
log "done: start tailscale ($(elapsed_since "${tailscale_start}"))"

RUN_ROOT="/home/user/iccomp_benchmark_fast_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
CACHE_ROOT="${BOARD_DEPS_CACHE_ROOT:-/home/user/iccomp_board_deps_cache}"
CACHE_BOARD_DEPS="${CACHE_ROOT}/board_deps"
CACHE_RUNTIME="${CACHE_ROOT}/runtime"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")

log "remote run root: ${RUN_ROOT}"
log "dependency cache root: ${CACHE_ROOT}"

cache_check='set -e
cache="$1"
for p in \
  runtime/tvm_py310.tar.gz \
  runtime/mnn_py312.tar.gz.part-00 \
  runtime/mnn_py312.tar.gz.part-01 \
  runtime/mnn_py312.tar.gz.part-02 \
  tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz \
  tvm/current/optimized_model.so \
  mnn/origin/model1.mnn \
  pytorch/compressed_gan.pt \
  inputs/places365-latents.tar.gz \
  inputs/mnn-encoder-outputs.tar.gz
do
  if [ ! -e "${cache}/${p}" ]; then
    echo "missing cache dependency: ${cache}/${p}" >&2
    exit 44
  fi
done'

if ! printf '%s' "${cache_check}" | "${ssh_stream[@]}" "bash -s -- '${CACHE_BOARD_DEPS}'"; then
    log "dependency cache is missing or incomplete."
    log "create it once with: BOARD_CLI_REFRESH_CACHE=1 docker/run-board-cli-smoke.*"
    exit 44
fi

log "start: create remote run directory"
dir_start="$(date +%s)"
"${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"
log "done: create remote run directory ($(elapsed_since "${dir_start}"))"

payload_bytes="$(du -sb "${fast_tar_excludes[@]}" /repo | awk '{print $1}')"
log "upload payload apparent size: $(human_bytes "${payload_bytes}")"
log "uploading code overlay without board_deps runtime/model/input payloads"
upload_start="$(date +%s)"
tar -C /repo "${fast_tar_excludes[@]}" -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
log "done: upload code overlay ($(elapsed_since "${upload_start}"))"

link_start="$(date +%s)"
log "start: link cached board_deps into remote repo"
"${ssh_common[@]}" "mkdir -p '${REMOTE_REPO}/board_deps' && for d in runtime inputs tvm mnn pytorch crypto; do rm -rf '${REMOTE_REPO}/board_deps/'\"\$d\"; ln -s '${CACHE_BOARD_DEPS}/'\"\$d\" '${REMOTE_REPO}/board_deps/'\"\$d\"; done"
log "done: link cached board_deps ($(elapsed_since "${link_start}"))"

runtime_start="$(date +%s)"
log "start: prepare cached Python runtimes"
"${ssh_common[@]}" "set -e; mkdir -p '${CACHE_RUNTIME}'; if [ ! -d '${CACHE_RUNTIME}/tvm_py310' ]; then tar -xzf '${CACHE_BOARD_DEPS}/runtime/tvm_py310.tar.gz' -C '${CACHE_RUNTIME}'; fi; if [ ! -d '${CACHE_RUNTIME}/mnn_py312' ]; then cat '${CACHE_BOARD_DEPS}'/runtime/mnn_py312.tar.gz.part-* | tar -xzf - -C '${CACHE_RUNTIME}'; fi"
log "done: prepare cached Python runtimes ($(elapsed_since "${runtime_start}"))"

benchmark_start="$(date +%s)"
log "running fast TVM/MNN/PyTorch benchmark; BOARD_CLI_MAX_INPUTS=${BOARD_CLI_MAX_INPUTS}"
"${ssh_common[@]}" "BOARD_CLI_MAX_INPUTS='${BOARD_CLI_MAX_INPUTS}' BOARD_CLI_RUNTIME_CACHE='${CACHE_RUNTIME}' bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
log "done: fast benchmark ($(elapsed_since "${benchmark_start}"))"

if "${ssh_common[@]}" "test -f '${RUN_ROOT}/logs/demo-kpi-summary.json'"; then
    log "demo KPI summary:"
    "${ssh_common[@]}" "cat '${RUN_ROOT}/logs/demo-kpi-summary.json'"
fi

if [ "${BOARD_CLI_FAST_KEEP_WORK:-0}" != "1" ]; then
    cleanup_start="$(date +%s)"
    log "start: clean transient fast benchmark work tree"
    "${ssh_common[@]}" "rm -rf '${REMOTE_REPO}' '${RUN_ROOT}/work' '${RUN_ROOT}/runtime'"
    log "done: clean transient fast benchmark work tree ($(elapsed_since "${cleanup_start}"))"
fi

run_size="$("${ssh_common[@]}" "du -sh '${RUN_ROOT}' | awk '{print \$1}'")"
log "remote run size: ${run_size}"
log "output root: ${RUN_ROOT}"
log "total elapsed: $(elapsed_since "${SCRIPT_START_TS}")"
'@

$BenchmarkScriptB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($BenchmarkScript))

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
    -e "BOARD_CLI_FAST_KEEP_WORK=$KeepFastWork" `
    -e "LOCAL_SCRIPT_B64=$BenchmarkScriptB64" `
    "$ImageName" `
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'

if ($LASTEXITCODE -ne 0) {
    throw "board CLI fast benchmark failed"
}
