param(
    [string]$BoardHost = "100.121.87.73",
    [string]$BoardUser = "user",
    [int]$BoardPort = 22,
    [string]$GitBashPath = "",
    [string]$BoardPassword = "user"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Set-DefaultEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )
    if (-not [Environment]::GetEnvironmentVariable($Name, "Process")) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Find-GitBash {
    param([string]$ExplicitPath)

    $candidates = @()
    if ($ExplicitPath) {
        $candidates += $ExplicitPath
    }
    $candidates += @(
        "E:\Software\Scoop\apps\git\current\bin\bash.exe",
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files\Git\usr\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $execPath = (& git --exec-path).Trim()
        $derived = Join-Path (Split-Path $execPath -Parent) "bin\bash.exe"
        if (Test-Path $derived) {
            return (Resolve-Path $derived).Path
        }
    }

    throw "Git Bash not found. Install Git for Windows or pass -GitBashPath. WSL bash is intentionally not used."
}

function Resolve-BoardPassword {
    param([string]$ExplicitPassword)

    foreach ($candidate in @(
        $ExplicitPassword,
        $env:REMOTE_PASS,
        $env:REMOTE_PASSWORD,
        $env:PHYTIUM_PI_PASS,
        $env:PHYTIUM_PI_PASSWORD,
        $env:BOARD_PASS
    )) {
        if ($candidate) {
            return $candidate
        }
    }

    $secure = Read-Host "Board SSH password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$WorkspaceRoot = Split-Path -Parent $RepoRoot
$FinalImageDir = Join-Path $WorkspaceRoot "原始图像_Top300_最终"
$FinalLatentDir = Join-Path $RepoRoot "Semantic-Communication\session_bootstrap\tmp\pytorch_board_runtime_20260717\showcase_usrp_final_300"
$FinalInputOrder = Join-Path $RepoRoot "host_pic_to_latent\showcase_final_300_order.tsv"
$Bash = Find-GitBash -ExplicitPath $GitBashPath
$Password = Resolve-BoardPassword -ExplicitPassword $BoardPassword

Set-DefaultEnv "REMOTE_HOST" $BoardHost
Set-DefaultEnv "PHYTIUM_PI_HOST" $BoardHost
Set-DefaultEnv "REMOTE_USER" $BoardUser
Set-DefaultEnv "PHYTIUM_PI_USER" $BoardUser
Set-DefaultEnv "REMOTE_SSH_PORT" ([string]$BoardPort)
Set-DefaultEnv "PHYTIUM_PI_PORT" ([string]$BoardPort)
[Environment]::SetEnvironmentVariable("REMOTE_PASS", $Password, "Process")
[Environment]::SetEnvironmentVariable("PHYTIUM_PI_PASSWORD", $Password, "Process")

Set-DefaultEnv "OPENAMP_SSH_RUNNER" "docker"
Set-DefaultEnv "OPENAMP_SSH_DOCKER_IMAGE" "iccomp-usrp-tx:latest"
$TxControlPort = if ($env:TX_CONTROL_PORT) { $env:TX_CONTROL_PORT } elseif ($env:USRP_TX_CONTROL_PORT) { $env:USRP_TX_CONTROL_PORT } else { "29221" }
Set-DefaultEnv "OPENAMP_SSH_DOCKER_CONTAINER" "cockpit-usrp-tx-$TxControlPort"
Set-DefaultEnv "OPENAMP_FIT_SSH_RUNNER" "docker"
Set-DefaultEnv "OPENAMP_FIT_BATCH_PHASES" "1"
Set-DefaultEnv "OPENAMP_FIT_USE_REMOTE_PROJECT" "0"
Set-DefaultEnv "MLKEM_LOCAL_CLIENT_RUNNER" "docker"
Set-DefaultEnv "MLKEM_LOCAL_CLIENT_DOCKER_IMAGE" "iccomp-usrp-tx:latest"
Set-DefaultEnv "OPENAMP_USRP_TX_RUNNER" "docker"
Set-DefaultEnv "OPENAMP_USRP_TX_DOCKER_IMAGE" "iccomp-usrp-tx:latest"
Set-DefaultEnv "OPENAMP_USRP_TX_DOCKER_NETWORK" "bridge"

Set-DefaultEnv "MLKEM_TRANSPORT_MODE" "usrp"
Set-DefaultEnv "OPENAMP_DEMO_INPUT_SOURCE_MODE" "usrp"
Set-DefaultEnv "JSCC_LINK_MODE" "qpsk"
Set-DefaultEnv "OPENAMP_DEMO_LINK_MODE" "qpsk"
Set-DefaultEnv "MLKEM_AUTH_ENABLED" "1"
Set-DefaultEnv "MLKEM_AUTH_SIG_POLICY" "DUAL_REQUIRED"
if ((Test-Path -LiteralPath $FinalImageDir -PathType Container) -and
    (Test-Path -LiteralPath $FinalLatentDir -PathType Container)) {
    Set-DefaultEnv "OPENAMP_DEMO_LOCAL_IMAGE_DIR" $FinalImageDir
    Set-DefaultEnv "OPENAMP_DEMO_LOCAL_LATENT_DIR" $FinalLatentDir
    Set-DefaultEnv "OPENAMP_DEMO_IMAGE_TO_LATENT_OUTPUT_DIR" $FinalLatentDir
    Set-DefaultEnv "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED" "0"
    Set-DefaultEnv "USRP_INPUT_ORDER_FILE" $FinalInputOrder
}
Set-DefaultEnv "MSYS2_ARG_CONV_EXCL" "*"

[Environment]::SetEnvironmentVariable("COCKPIT_SCRIPT_DIR_WIN", $ScriptDir, "Process")

$BoardNetworkScript = Join-Path $RepoRoot "USRP292x\ConfigureUsrp2922DemoNetwork.ps1"
if (-not (Test-Path -LiteralPath $BoardNetworkScript -PathType Leaf)) {
    throw "Board RX network recovery script not found: $BoardNetworkScript"
}

Write-Host "[demo] Git Bash: $Bash"
Write-Host "[demo] Board: $BoardUser@$BoardHost`:$BoardPort"
Write-Host "[demo] Defaults: USRP IQ direct, ML-KEM+SM4, ML-DSA+SM2, no image warmup"
if ($env:OPENAMP_DEMO_LOCAL_LATENT_DIR -eq $FinalLatentDir) {
    Write-Host "[demo] Showcase inputs: $FinalImageDir (300 pre-encoded latents)"
}
Write-Host "[demo] Board RX USRP network recovery (eth0)..."
& $BoardNetworkScript `
    -Target Board `
    -BoardHost $BoardHost `
    -BoardUser $BoardUser `
    -BoardPassword $Password `
    -BoardPort $BoardPort `
    -BoardInterface eth0 `
    -Fast
Write-Host "[demo] Board RX USRP network ready."

& $Bash -lc 'cd "$(cygpath -u "$COCKPIT_SCRIPT_DIR_WIN")" && ./start-dev.sh'
if ($LASTEXITCODE -ne 0) {
    throw "Cockpit demo startup failed with exit code $LASTEXITCODE"
}
