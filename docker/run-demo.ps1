$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$ContainerName = if ($env:CONTAINER_NAME) { $env:CONTAINER_NAME } else { "iccomp-electron-demo" }
$Display = if ($env:DISPLAY) { $env:DISPLAY } else { "host.docker.internal:0.0" }
$EnableTailscale = $env:ENABLE_TAILSCALE -in @("1", "true", "TRUE", "yes", "YES")
$TailscaleStateVolume = if ($env:TAILSCALE_STATE_VOLUME) { $env:TAILSCALE_STATE_VOLUME } else { "iccomp-tailscale-state" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

function Write-DemoLog {
    param([string]$Message)
    Write-Host "[demo] $Message"
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

docker image inspect "$ImageName" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-DemoLog "image $ImageName not found; building it first"
    docker build `
        -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
        -t "$ImageName" `
        "$ProjectRoot"
    Assert-LastExitCode "docker build"
}

Write-DemoLog "starting the real Electron cockpit inside Docker"
Write-DemoLog "DISPLAY=$Display; on Windows, start VcXsrv/Xming with access control disabled before running this script"
if ($EnableTailscale) {
    Write-DemoLog "tailscale enabled; state volume=$TailscaleStateVolume"
}

$DockerArgs = @(
    "run", "--rm", "-it",
    "--name", "$ContainerName",
    "-e", "DISPLAY=$Display"
)

foreach ($Name in @(
    "ICCOMP_COCKPIT_PROFILE",
    "REMOTE_HOST", "PHYTIUM_PI_HOST",
    "REMOTE_USER", "PHYTIUM_PI_USER",
    "REMOTE_PASS", "PHYTIUM_PI_PASSWORD",
    "REMOTE_SSH_PORT", "PHYTIUM_PI_PORT",
    "OPENAMP_DEMO_INPUT_SOURCE_MODE",
    "REMOTE_USRP_RX_DIR", "REMOTE_RX_RUN_ROOT", "REMOTE_USRP_PROJECT_ROOT",
    "REMOTE_USRP_DECODE_PYTHON", "OPENAMP_DEMO_REMOTE_DECODE_PYTHON",
    "JSCC_LINK_MODE", "OPENAMP_DEMO_LINK_MODE",
    "ANALOG_IN_PROCESS_LOCAL_CODEC", "ANALOG_WARMUP_LOCAL_CODEC",
    "ANALOG_SPS", "ANALOG_AMPLITUDE", "ANALOG_RX_TAIL_SEC", "ANALOG_REMOTE_CLEANUP_MODE", "ANALOG_REMOTE_DECODE_WORKER",
    "ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS",
    "MLKEM_TRANSPORT_MODE", "MLKEM_AUTH_ENABLED", "MLKEM_AUTH_SIG_POLICY",
    "OPENAMP_SSH_RUNNER", "OPENAMP_SSH_DOCKER_IMAGE", "SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER",
    "OPENAMP_USRP_TX_RUNNER", "OPENAMP_USRP_TX_DOCKER_IMAGE", "OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET",
    "OPENAMP_TVM_BATCH_RUNNER", "OPENAMP_DEMO_TVM_BATCH_RUNNER", "OPENAMP_TVM_BATCH_EXIT_GRACE_SEC"
)) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    if ($Value) {
        $DockerArgs += @("-e", "${Name}=${Value}")
    }
}

if ($EnableTailscale) {
    $DockerArgs += @(
        "--cap-add=NET_ADMIN",
        "--cap-add=NET_RAW",
        "--device=/dev/net/tun",
        "-v", "${TailscaleStateVolume}:/var/lib/tailscale",
        "-e", "ENABLE_TAILSCALE=1"
    )
    foreach ($Name in @(
        "TS_AUTHKEY", "TAILSCALE_AUTHKEY",
        "TS_HOSTNAME", "TAILSCALE_HOSTNAME",
        "TS_ACCEPT_DNS", "TAILSCALE_ACCEPT_DNS",
        "TS_ACCEPT_ROUTES", "TAILSCALE_ACCEPT_ROUTES",
        "TS_EXTRA_ARGS", "TAILSCALE_EXTRA_ARGS",
        "TAILSCALE_PING_TARGET"
    )) {
        $Value = [Environment]::GetEnvironmentVariable($Name)
        if ($Value) {
            $DockerArgs += @("-e", "${Name}=${Value}")
        }
    }
}

$DockerArgs += @("$ImageName", "bash", "docker/start-electron-prod-demo.sh")

docker @DockerArgs
Assert-LastExitCode "Electron demo"
