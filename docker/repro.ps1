$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

function Write-ReproLog {
    param([string]$Message)
    Write-Host "[repro] $Message"
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Write-ReproLog "using vendored source tree"

Write-ReproLog "building Docker image: $ImageName"
docker build `
    -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
    -t "$ImageName" `
    "$ProjectRoot"
Assert-LastExitCode "docker build"

Write-ReproLog "checking Python dependencies"
docker run --rm "$ImageName" python "docker/check_deps.py"
Assert-LastExitCode "dependency check"

Write-ReproLog "running minimal reproducibility tests"
docker run --rm "$ImageName" pytest -q `
    "mlkem_link/tests/test_auth.py" `
    "mlkem_link/tests/test_session.py" `
    "mlkem_link/tests/test_tui_remote_tcp_server.py" `
    "scripts/test_latent_transport.py" `
    "scripts/test_fit.py"
Assert-LastExitCode "minimal reproducibility tests"

Write-ReproLog "checking prerecorded demo API"
docker run --rm "$ImageName" bash "docker/api-smoke.sh"
Assert-LastExitCode "prerecorded demo API"

Write-ReproLog "running Electron smoke test with Xvfb"
docker run --rm "$ImageName" bash "docker/electron-smoke.sh"
Assert-LastExitCode "Electron smoke test"

Write-ReproLog "reproducibility validation completed"
