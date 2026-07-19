$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if ($Expected -ne $Actual) {
        throw "$Message`: expected '$Expected', got '$Actual'"
    }
}

function Assert-Throws {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Script,
        [Parameter(Mandatory = $true)][string]$Message
    )
    try {
        & $Script
    }
    catch {
        return
    }
    throw "$Message`: expected an exception"
}

function Assert-Matches {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if ($Text -notmatch $Pattern) {
        throw "$Message`: pattern '$Pattern' was not found"
    }
}

function Assert-NotMatches {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if ($Text -match $Pattern) {
        throw "$Message`: forbidden pattern '$Pattern' was found"
    }
}

$CockpitDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ConfigScript = Join-Path $CockpitDir "start-demo-config.ps1"
$EnvironmentNames = @(
    "REMOTE_HOST",
    "PHYTIUM_PI_HOST",
    "REMOTE_USER",
    "PHYTIUM_PI_USER",
    "REMOTE_SSH_PORT",
    "PHYTIUM_PI_PORT",
    "REMOTE_PASS",
    "REMOTE_PASSWORD",
    "PHYTIUM_PI_PASS",
    "PHYTIUM_PI_PASSWORD",
    "BOARD_PASS"
)
$OriginalEnvironment = @{}
foreach ($Name in $EnvironmentNames) {
    $OriginalEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
    [Environment]::SetEnvironmentVariable($Name, $null, "Process")
}

try {
    . $ConfigScript

    function Invoke-ResolveWithRealBoundParameters {
        param(
            [string]$BoardHost = "100.121.87.73",
            [string]$BoardUser = "user",
            [int]$BoardPort = 22,
            [string]$BoardPassword = ""
        )

        Resolve-DemoStartupConfig `
            -BoundParameters $PSBoundParameters `
            -BoardHost $BoardHost `
            -BoardUser $BoardUser `
            -BoardPort $BoardPort `
            -BoardPassword $BoardPassword
    }

    $env:REMOTE_HOST = "198.51.100.99"
    $env:REMOTE_USER = "stale-user"
    $env:REMOTE_SSH_PORT = "2022"
    $env:REMOTE_PASS = "stale-secret"
    $Explicit = Resolve-DemoStartupConfig `
        -BoundParameters @{
            BoardHost = "203.0.113.10"
            BoardUser = "operator"
            BoardPort = 2202
            BoardPassword = "explicit-secret"
        } `
        -BoardHost "203.0.113.10" `
        -BoardUser "operator" `
        -BoardPort 2202 `
        -BoardPassword "explicit-secret"
    Assert-Equal "203.0.113.10" $Explicit.Host "explicit host wins"
    Assert-Equal "operator" $Explicit.User "explicit user wins"
    Assert-Equal 2202 $Explicit.Port "explicit port wins"
    Assert-Equal "explicit-secret" $Explicit.Password "explicit password wins"

    $RealBoundParameters = Invoke-ResolveWithRealBoundParameters `
        -BoardHost "203.0.113.11" `
        -BoardUser "real-operator" `
        -BoardPort 2203 `
        -BoardPassword "real-explicit-secret"
    Assert-Equal "203.0.113.11" $RealBoundParameters.Host "real bound host wins"
    Assert-Equal "real-operator" $RealBoundParameters.User "real bound user wins"
    Assert-Equal 2203 $RealBoundParameters.Port "real bound port wins"
    Assert-Equal "real-explicit-secret" $RealBoundParameters.Password "real bound password wins"

    $env:REMOTE_HOST = "198.51.100.20"
    $env:REMOTE_USER = "env-user"
    $env:REMOTE_SSH_PORT = "2222"
    $env:REMOTE_PASS = "env-secret"
    $FromEnvironment = Resolve-DemoStartupConfig `
        -BoundParameters @{} `
        -BoardHost "100.121.87.73" `
        -BoardUser "user" `
        -BoardPort 22 `
        -BoardPassword ""
    Assert-Equal "198.51.100.20" $FromEnvironment.Host "environment host beats default"
    Assert-Equal "env-user" $FromEnvironment.User "environment user beats default"
    Assert-Equal 2222 $FromEnvironment.Port "environment port beats default"
    Assert-Equal "env-secret" $FromEnvironment.Password "environment password is used"

    $PasswordNames = @(
        "REMOTE_PASS",
        "REMOTE_PASSWORD",
        "PHYTIUM_PI_PASS",
        "PHYTIUM_PI_PASSWORD",
        "BOARD_PASS"
    )
    foreach ($Name in $PasswordNames) {
        foreach ($Candidate in $PasswordNames) {
            [Environment]::SetEnvironmentVariable($Candidate, $null, "Process")
        }
        [Environment]::SetEnvironmentVariable($Name, "secret-$Name", "Process")
        $Resolved = Resolve-DemoStartupConfig `
            -BoundParameters @{} `
            -BoardHost "100.121.87.73" `
            -BoardUser "user" `
            -BoardPort 22 `
            -BoardPassword ""
        Assert-Equal "secret-$Name" $Resolved.Password "$Name is accepted"
    }

    foreach ($Name in $EnvironmentNames) {
        [Environment]::SetEnvironmentVariable($Name, $null, "Process")
    }
    $Defaults = Resolve-DemoStartupConfig `
        -BoundParameters @{} `
        -BoardHost "100.121.87.73" `
        -BoardUser "user" `
        -BoardPort 22 `
        -BoardPassword ""
    Assert-Equal "100.121.87.73" $Defaults.Host "public host default is retained"
    Assert-Equal "user" $Defaults.User "public user default is retained"
    Assert-Equal 22 $Defaults.Port "public port default is retained"
    Assert-Equal "" $Defaults.Password "missing password is left for secure prompt"

    $env:REMOTE_SSH_PORT = "70000"
    Assert-Throws {
        Resolve-DemoStartupConfig `
            -BoundParameters @{} `
            -BoardHost "100.121.87.73" `
            -BoardUser "user" `
            -BoardPort 22 `
            -BoardPassword ""
    } "out-of-range environment port is rejected"

    $StartDemo = Get-Content -Raw -LiteralPath (Join-Path $CockpitDir "start-demo.ps1")
    Assert-Matches $StartDemo '\[string\]\$BoardPassword\s*=\s*""' "wrapper has no default password"
    Assert-Matches $StartDemo 'start-demo-config\.ps1' "wrapper loads the configuration helper"
    Assert-Matches $StartDemo 'Resolve-DemoStartupConfig' "wrapper resolves one startup configuration"
    Assert-NotMatches $StartDemo 'Set-DefaultEnv\s+"REMOTE_(HOST|USER|SSH_PORT)"' "wrapper does not preserve stale connection environment"
    Assert-Matches $StartDemo 'Set-DefaultEnv\s+"JSCC_LINK_MODE"\s+"qpsk"' "recommended wrapper defaults to QPSK"
    Assert-Matches $StartDemo 'Set-DefaultEnv\s+"OPENAMP_DEMO_LINK_MODE"\s+"qpsk"' "recommended backend defaults to QPSK"
    Assert-Matches $StartDemo 'Assert-DemoHostReady' "wrapper checks local dependencies"
    Assert-Matches $StartDemo 'host_pic_to_latent\\encoder_outputs' "wrapper checks a host latent cache"
    $PreflightIndex = $StartDemo.IndexOf('Assert-DemoHostReady -RepoRoot')
    $BoardNetworkIndex = $StartDemo.IndexOf('& $BoardNetworkScript')
    if ($PreflightIndex -lt 0 -or $BoardNetworkIndex -lt 0 -or $PreflightIndex -ge $BoardNetworkIndex) {
        throw "local dependency preflight must run before board network recovery"
    }

    $StartDev = Get-Content -Raw -LiteralPath (Join-Path $CockpitDir "start-dev.sh")
    Assert-Matches $StartDev 'JSCC_LINK_MODE="\$\{JSCC_LINK_MODE:-qpsk\}"' "Git Bash entry defaults to QPSK"
    Assert-Matches $StartDev 'OPENAMP_DEMO_LINK_MODE="\$\{OPENAMP_DEMO_LINK_MODE:-qpsk\}"' "Git Bash backend defaults to QPSK"

    $PackageRoot = (Resolve-Path (Join-Path $CockpitDir "..\..")).Path
    $DockerPowerShell = Get-Content -Raw -LiteralPath (Join-Path $PackageRoot "docker\run-demo-tailscale.ps1")
    $DockerBash = Get-Content -Raw -LiteralPath (Join-Path $PackageRoot "docker\run-demo-tailscale.sh")
    Assert-Matches $DockerPowerShell 'JSCC_LINK_MODE\s*=\s*"iq-direct"' "PowerShell compatibility entry remains IQ-direct"
    Assert-Matches $DockerBash 'JSCC_LINK_MODE:-iq-direct' "Bash compatibility entry remains IQ-direct"

    $BoardNetwork = Get-Content -Raw -LiteralPath (Join-Path $PackageRoot "USRP292x\ConfigureUsrp2922DemoNetwork.ps1")
    Assert-Matches $BoardNetwork '\[string\]\$BoardPassword\s*=\s*""' "board network recovery has no default password"
    Assert-Matches $BoardNetwork 'Read-Host\s+"Board SSH password"\s+-AsSecureString' "standalone board recovery prompts securely"
}
finally {
    foreach ($Name in $EnvironmentNames) {
        [Environment]::SetEnvironmentVariable($Name, $OriginalEnvironment[$Name], "Process")
    }
}

Write-Output "start-demo-config-ok"
