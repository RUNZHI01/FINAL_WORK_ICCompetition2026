[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet("Status", "UpperHost", "Board", "Both")]
    [string]$Target = "Status",

    [string]$InterfaceAlias = "",
    [string]$UpperHostAddress = "192.168.10.1",
    [byte]$UpperHostPrefixLength = 32,
    [string]$UpperUsrpAddress = "192.168.10.2",

    [string]$BoardHost = "100.121.87.73",
    [string]$BoardUser = "user",
    [string]$BoardPassword = "user",
    [int]$BoardPort = 22,
    [string]$BoardInterface = "eth0",
    [string]$GitBashPath = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Script:DemoScriptRoot = $PSScriptRoot

# Demo address plan:
#   UpperHost/TX: 192.168.10.1/32 -> USRP 192.168.10.2/32
#   Board/RX:     192.168.10.11/32 -> USRP 192.168.10.22/32

function Write-DemoLog {
    param([string]$Message)
    Write-Host "[usrp-net] $Message"
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

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Require-Administrator {
    if (-not (Test-IsAdministrator)) {
        throw "UpperHost network configuration requires an elevated PowerShell window."
    }
}

function Get-AdapterCandidates {
    $adapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -in @("Up", "Disconnected") } |
        Sort-Object Status, Name)
    if ($adapters.Count -eq 0) {
        $adapters = @(Get-NetAdapter -ErrorAction SilentlyContinue |
            Where-Object { $_.Status -in @("Up", "Disconnected") } |
            Sort-Object Status, Name)
    }
    return $adapters
}

function Show-AdapterCandidates {
    Write-DemoLog "candidate Windows adapters:"
    $idx = 0
    foreach ($adapter in Get-AdapterCandidates) {
        $idx += 1
        Write-Host ("  {0}. {1}  status={2}  ifIndex={3}  desc={4}" -f `
            $idx, $adapter.Name, $adapter.Status, $adapter.ifIndex, $adapter.InterfaceDescription)
    }
}

function Resolve-InterfaceAlias {
    if ($InterfaceAlias) {
        return $InterfaceAlias
    }
    Show-AdapterCandidates
    throw "Pass -InterfaceAlias with the USRP Ethernet adapter name. This script does not auto-select a NIC."
}

function Show-UpperHostStatus {
    param(
        [string]$DeviceAddress,
        [string]$HostAddress
    )

    Write-DemoLog "address plan: Windows host ${HostAddress}/32, explicit route ${DeviceAddress}/32 on the USRP NIC"
    Show-AdapterCandidates

    Write-DemoLog "current 192.168.10.x IPv4 addresses:"
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -like "192.168.10.*" } |
        Select-Object InterfaceAlias, InterfaceIndex, IPAddress, PrefixLength, SkipAsSource |
        Format-Table -AutoSize

    Write-DemoLog "current route entries for $DeviceAddress/32 and 192.168.10.0/24:"
    Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.DestinationPrefix -in @("${DeviceAddress}/32", "192.168.10.0/24") } |
        Select-Object DestinationPrefix, InterfaceAlias, InterfaceIndex, NextHop, RouteMetric, PolicyStore |
        Format-Table -AutoSize

    Write-DemoLog "ping ${DeviceAddress}:"
    if (Test-Connection -ComputerName $DeviceAddress -Count 2 -Quiet -ErrorAction SilentlyContinue) {
        Write-Host "  reachable"
    }
    else {
        Write-Host "  unreachable"
    }
}

function Configure-UpperHostLink {
    $alias = Resolve-InterfaceAlias
    Require-Administrator

    $adapter = Get-NetAdapter -Name $alias -ErrorAction Stop
    $destinationPrefix = "${UpperUsrpAddress}/32"
    Write-DemoLog "configuring Windows UpperHost link on '$alias'"
    Write-DemoLog "host IP ${UpperHostAddress}/${UpperHostPrefixLength}; USRP route $destinationPrefix"

    $existingAddresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $UpperHostAddress })

    foreach ($address in $existingAddresses) {
        if ([int]$address.PrefixLength -ne [int]$UpperHostPrefixLength) {
            if ($PSCmdlet.ShouldProcess("$UpperHostAddress on $alias", "remove wrong prefix length $($address.PrefixLength)")) {
                Remove-NetIPAddress -InputObject $address -Confirm:$false
            }
        }
    }

    $current = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $UpperHostAddress -and [int]$_.PrefixLength -eq [int]$UpperHostPrefixLength })
    if ($current.Count -eq 0) {
        if ($PSCmdlet.ShouldProcess("$alias", "add $UpperHostAddress/$UpperHostPrefixLength")) {
            New-NetIPAddress `
                -InterfaceIndex $adapter.ifIndex `
                -IPAddress $UpperHostAddress `
                -PrefixLength $UpperHostPrefixLength `
                -AddressFamily IPv4 `
                -SkipAsSource $false `
                -PolicyStore ActiveStore | Out-Null
        }
    }
    else {
        Write-DemoLog "host IP already present"
    }

    $oldRoutes = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix $destinationPrefix -ErrorAction SilentlyContinue)
    foreach ($route in $oldRoutes) {
        if ($PSCmdlet.ShouldProcess($destinationPrefix, "remove stale exact route on interface index $($route.InterfaceIndex)")) {
            Remove-NetRoute -InputObject $route -Confirm:$false
        }
    }

    if ($PSCmdlet.ShouldProcess("$alias", "add on-link route $destinationPrefix")) {
        New-NetRoute `
            -DestinationPrefix $destinationPrefix `
            -InterfaceIndex $adapter.ifIndex `
            -NextHop "0.0.0.0" `
            -RouteMetric 10 `
            -PolicyStore ActiveStore | Out-Null
    }

    Show-UpperHostStatus -DeviceAddress $UpperUsrpAddress -HostAddress $UpperHostAddress
}

function ConvertTo-ShellSingleQuoted {
    param([string]$Text)
    return "'" + ($Text -replace "'", "'\\''") + "'"
}

function New-BoardRemoteCommand {
    $scriptPath = "/home/user/USRP292x/SetupUsrp2922BoardNetwork.sh"
    $quotedScript = ConvertTo-ShellSingleQuoted $scriptPath
    $quotedPass = ConvertTo-ShellSingleQuoted $BoardPassword
    $envArgs = ""
    if ($BoardInterface) {
        $envArgs = "USRP2922_BOARD_IFACE=$(ConvertTo-ShellSingleQuoted $BoardInterface) "
    }
    return "SCRIPT=$quotedScript; if [ ! -x " + '"$SCRIPT"' + " ]; then echo board network script not found or not executable: " + '"$SCRIPT"' + " >&2; exit 1; fi; printf '%s\n' $quotedPass | sudo -S env ${envArgs}" + '"$SCRIPT"'
}

function Configure-BoardLink {
    $scriptDir = $Script:DemoScriptRoot
    if (-not $scriptDir) {
        throw "Cannot resolve script directory for board network configuration."
    }
    $repoRoot = Resolve-Path (Join-Path $scriptDir "..")
    $remoteCommand = New-BoardRemoteCommand
    $paramikoScript = Join-Path $repoRoot.Path "Semantic-Communication\session_bootstrap\scripts\ssh_with_password_paramiko.py"
    if (-not (Test-Path $paramikoScript)) {
        throw "Paramiko SSH helper not found: $paramikoScript"
    }

    $env:USRP_DEMO_BOARD_PASS = $BoardPassword

    Write-DemoLog "configuring board RX link through SSH: ${BoardUser}@${BoardHost}:${BoardPort}"
    if ($BoardInterface) {
        Write-DemoLog "board interface override: $BoardInterface"
    }
    if ($PSCmdlet.ShouldProcess("$BoardUser@$BoardHost", "run SetupUsrp2922BoardNetwork.sh")) {
        Write-DemoLog "waiting for board NetworkManager and UHD probe; this can take about 30-60 seconds"
        & python $paramikoScript `
            --host $BoardHost `
            --user $BoardUser `
            --pass-env USRP_DEMO_BOARD_PASS `
            --port $BoardPort `
            --timeout-sec 60 `
            -- `
            $remoteCommand
        if ($LASTEXITCODE -ne 0) {
            throw "board network configuration failed with exit code $LASTEXITCODE"
        }
    }
}

switch ($Target) {
    "Status" {
        Show-UpperHostStatus -DeviceAddress $UpperUsrpAddress -HostAddress $UpperHostAddress
    }
    "UpperHost" {
        Configure-UpperHostLink
    }
    "Board" {
        Configure-BoardLink
    }
    "Both" {
        Configure-UpperHostLink
        Configure-BoardLink
    }
}
