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
    "ssh_with_password.sh",
    "Get-NetRoute",
    "New-NetRoute"
)) {
    if (-not $content.Contains($requiredText)) {
        throw "missing required text: $requiredText"
    }
}

Write-Host "configure-usrp2922-demo-network-ok"
