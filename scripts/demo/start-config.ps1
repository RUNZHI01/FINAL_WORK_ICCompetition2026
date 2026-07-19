# Connection values shared by the public demo entrypoint and its tests.
Set-StrictMode -Version Latest

function Get-FirstNonEmptyDemoValue {
    param(
        [AllowNull()][object[]]$Values
    )

    foreach ($Value in $Values) {
        if ($null -eq $Value) {
            continue
        }
        $Text = [string]$Value
        if (-not [string]::IsNullOrWhiteSpace($Text)) {
            return $Text
        }
    }
    return ""
}

function Resolve-DemoStartupConfig {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$BoundParameters,
        [Parameter(Mandatory = $true)][string]$BoardHost,
        [Parameter(Mandatory = $true)][string]$BoardUser,
        [Parameter(Mandatory = $true)][int]$BoardPort,
        [AllowEmptyString()][string]$BoardPassword = ""
    )

    $HostValue = if ($BoundParameters.ContainsKey("BoardHost")) {
        $BoardHost
    }
    else {
        Get-FirstNonEmptyDemoValue -Values @($env:REMOTE_HOST, $env:PHYTIUM_PI_HOST, $BoardHost)
    }
    $UserValue = if ($BoundParameters.ContainsKey("BoardUser")) {
        $BoardUser
    }
    else {
        Get-FirstNonEmptyDemoValue -Values @($env:REMOTE_USER, $env:PHYTIUM_PI_USER, $BoardUser)
    }
    $PortValue = if ($BoundParameters.ContainsKey("BoardPort")) {
        [string]$BoardPort
    }
    else {
        Get-FirstNonEmptyDemoValue -Values @($env:REMOTE_SSH_PORT, $env:PHYTIUM_PI_PORT, [string]$BoardPort)
    }
    $PasswordValue = if ($BoundParameters.ContainsKey("BoardPassword")) {
        $BoardPassword
    }
    else {
        Get-FirstNonEmptyDemoValue -Values @(
            $env:REMOTE_PASS,
            $env:REMOTE_PASSWORD,
            $env:PHYTIUM_PI_PASS,
            $env:PHYTIUM_PI_PASSWORD,
            $env:BOARD_PASS
        )
    }

    $HostValue = [string]$HostValue
    $UserValue = [string]$UserValue
    if ([string]::IsNullOrWhiteSpace($HostValue)) {
        throw "Board host must not be empty."
    }
    if ([string]::IsNullOrWhiteSpace($UserValue)) {
        throw "Board user must not be empty."
    }

    $ResolvedPort = 0
    if (-not [int]::TryParse([string]$PortValue, [ref]$ResolvedPort) -or
        $ResolvedPort -lt 1 -or
        $ResolvedPort -gt 65535) {
        throw "Board port must be an integer between 1 and 65535."
    }

    return [pscustomobject]@{
        Host = $HostValue.Trim()
        User = $UserValue.Trim()
        Port = $ResolvedPort
        Password = [string]$PasswordValue
    }
}
