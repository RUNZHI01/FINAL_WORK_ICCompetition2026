$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$ContainerName = if ($env:CONTAINER_NAME) { $env:CONTAINER_NAME } else { "iccomp-tailscale-login" }
$StateVolume = if ($env:TAILSCALE_STATE_VOLUME) { $env:TAILSCALE_STATE_VOLUME } else { "iccomp-tailscale-state" }
$Hostname = if ($env:TAILSCALE_HOSTNAME) { $env:TAILSCALE_HOSTNAME } else { "iccomp-demo" }
$AcceptDns = if ($env:TS_ACCEPT_DNS) { $env:TS_ACCEPT_DNS } else { "false" }
$AcceptRoutes = if ($env:TS_ACCEPT_ROUTES) { $env:TS_ACCEPT_ROUTES } else { "true" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

function Write-LoginLog {
    param([string]$Message)
    Write-Host "[tailscale-login] $Message"
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

docker image inspect "$ImageName" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-LoginLog "image $ImageName not found; building it first"
    docker build `
        -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
        -t "$ImageName" `
        "$ProjectRoot"
    Assert-LastExitCode "docker build"
}

$DockerArgs = @(
    "run", "--rm", "-i",
    "--name", "$ContainerName",
    "--cap-add=NET_ADMIN",
    "--cap-add=NET_RAW",
    "--device=/dev/net/tun",
    "-v", "${StateVolume}:/var/lib/tailscale",
    "-e", "TS_LOGIN_MODE=interactive",
    "-e", "TAILSCALE_HOSTNAME=$Hostname",
    "-e", "TS_ACCEPT_DNS=$AcceptDns",
    "-e", "TS_ACCEPT_ROUTES=$AcceptRoutes"
)

if (-not [Console]::IsInputRedirected) {
    $DockerArgs += @("--tty")
}

foreach ($Name in @("TAILSCALE_PING_TARGET", "TS_EXTRA_ARGS", "TAILSCALE_EXTRA_ARGS")) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    if ($Value) {
        $DockerArgs += @("-e", "${Name}=${Value}")
    }
}

$DockerArgs += @("$ImageName", "bash", "docker/start-tailscale.sh")

Write-LoginLog "using state volume: $StateVolume"
Write-LoginLog "open the printed login URL in your browser, finish auth, then this command will return"
docker @DockerArgs
Assert-LastExitCode "tailscale login"
