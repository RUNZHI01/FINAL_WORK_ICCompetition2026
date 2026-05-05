$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Quote-Bash {
    param([string]$Value)
    return "'" + $Value.Replace("'", "'\''") + "'"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$WslPathOutput = & wsl.exe -e wslpath -a "$ProjectRoot" 2>&1
$WslPathExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($WslPathExitCode -ne 0) {
    throw "wslpath failed. Make sure WSL is installed and running."
}
$ProjectRootWsl = ($WslPathOutput | Where-Object { $_ -like "/*" } | Select-Object -First 1)
if (-not $ProjectRootWsl) {
    throw "Could not translate project path to WSL path: $ProjectRoot"
}

$EnvNames = @(
    "IMAGE_NAME",
    "CONTAINER_NAME",
    "TAILSCALE_STATE_VOLUME",
    "TAILSCALE_HOSTNAME",
    "TAILSCALE_PING_TARGET",
    "TS_AUTHKEY",
    "TAILSCALE_AUTHKEY",
    "TS_ACCEPT_DNS",
    "TAILSCALE_ACCEPT_DNS",
    "TS_ACCEPT_ROUTES",
    "TAILSCALE_ACCEPT_ROUTES",
    "TS_EXTRA_ARGS",
    "TAILSCALE_EXTRA_ARGS",
    "REMOTE_HOST",
    "PHYTIUM_PI_HOST",
    "REMOTE_USER",
    "PHYTIUM_PI_USER",
    "REMOTE_PASS",
    "PHYTIUM_PI_PASSWORD",
    "MLKEM_REMOTE_PYTHON",
    "MLKEM_REMOTE_OQS_INSTALL_PATH",
    "MLKEM_REMOTE_LD_LIBRARY_PATH",
    "MLKEM_REMOTE_TONGSUO_SIG_BRIDGE",
    "MLKEM_REMOTE_TONGSUO_KEM_BRIDGE",
    "MLKEM_REMOTE_RUN_LOGGER_DIR",
    "COCKPIT_OPEN_DEVTOOLS",
    "DEMO_STARTUP_LOG_DELAY_SEC",
    "DEMO_LOG_TAIL"
)

$EnvPrefix = New-Object System.Collections.Generic.List[string]
foreach ($Name in $EnvNames) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    if ($Value) {
        $EnvPrefix.Add("$Name=$(Quote-Bash $Value)")
    }
}

$RunCommand = "bash docker/run-demo-wslg-tailscale.sh"
if ($EnvPrefix.Count -gt 0) {
    $RunCommand = "env " + ($EnvPrefix -join " ") + " " + $RunCommand
}
$Command = "cd $(Quote-Bash $ProjectRootWsl) && $RunCommand"

Write-Host "[wslg-demo] launching through WSLg. This script reuses Docker volume iccomp-tailscale-state unless TAILSCALE_STATE_VOLUME is set."
wsl.exe -e bash -lc $Command
if ($LASTEXITCODE -ne 0) {
    throw "WSLg Tailscale demo failed with exit code $LASTEXITCODE"
}
