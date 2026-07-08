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
