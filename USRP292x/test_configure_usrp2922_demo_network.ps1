$ErrorActionPreference = "Stop"

$ScriptPath = Join-Path $PSScriptRoot "ConfigureUsrp2922DemoNetwork.ps1"
if (-not (Test-Path $ScriptPath)) {
    throw "missing script: $ScriptPath"
}

$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $ScriptPath,
    [ref]$tokens,
    [ref]$parseErrors
)

if ($parseErrors.Count -ne 0) {
    $messages = $parseErrors | ForEach-Object { "$($_.Extent.StartLineNumber): $($_.Message)" }
    throw "PowerShell parse errors:`n$($messages -join "`n")"
}

$paramNames = $ast.ParamBlock.Parameters |
    ForEach-Object { $_.Name.VariablePath.UserPath }

foreach ($requiredParam in @(
    "Target",
    "InterfaceAlias",
    "BoardHost",
    "BoardUser",
    "BoardPassword",
    "BoardPort",
    "BoardInterface",
    "Fast",
    "GitBashPath"
)) {
    if ($paramNames -notcontains $requiredParam) {
        throw "missing parameter: $requiredParam"
    }
}

$content = Get-Content -Raw $ScriptPath
foreach ($requiredText in @(
    "192.168.10.1",
    "192.168.10.2",
    "192.168.10.11",
    "192.168.10.22",
    "/32",
    "SetupUsrp2922BoardNetwork.sh",
    "ssh_with_password_paramiko.py",
    "Get-NetRoute",
    "New-NetRoute",
    "USRP2922_PROBE_UHD=0",
    "USRP2922_SKIP_CLEANUP=1",
    "USRP2922_PING_COUNT=1",
    "-lc"
)) {
    if (-not $content.Contains($requiredText)) {
        throw "missing required text: $requiredText"
    }
}

if (-not $content.Contains('[string]$BoardInterface = "eth0"')) {
    throw "BoardInterface must default to eth0 for the demo wiring."
}

$canonicalScript = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\setup_usrp2922_network.sh"
if (-not (Test-Path $canonicalScript)) {
    throw "missing canonical script: $canonicalScript"
}

$canonicalContent = Get-Content -Raw $canonicalScript
foreach ($requiredText in @(
    "USRP2922_PROBE_UHD",
    "USRP2922_SKIP_CLEANUP",
    "USRP2922_PING_COUNT"
)) {
    if (-not $canonicalContent.Contains($requiredText)) {
        throw "canonical script missing fast-init support: $requiredText"
    }
}

$boardWhatIf = powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath `
    -Target Board `
    -BoardHost "demo-board" `
    -BoardUser "user" `
    -BoardPassword "user" `
    -WhatIf 2>&1

if ($LASTEXITCODE -ne 0) {
    throw "Board -WhatIf failed:`n$($boardWhatIf | Out-String)"
}

Write-Host "configure-usrp2922-demo-network-ok"
