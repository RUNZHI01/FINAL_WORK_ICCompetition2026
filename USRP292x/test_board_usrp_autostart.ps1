$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$bootScript = Join-Path $PSScriptRoot "BoardUsrp2922BootConnect.sh"
$serviceFile = Join-Path $PSScriptRoot "usrp2922-board-autostart.service"
$installScript = Join-Path $PSScriptRoot "InstallBoardUsrp2922Autostart.sh"

foreach ($path in @($bootScript, $serviceFile, $installScript)) {
    if (-not (Test-Path $path)) {
        throw "missing autostart file: $path"
    }
}

$bootContent = Get-Content -Raw $bootScript
foreach ($requiredText in @(
    "USRP2922_BOARD_IFACE",
    "192.168.10.22",
    "SetupUsrp2922BoardNetwork.sh",
    "USRP2922_PROBE_UHD=0",
    "USRP2922_SKIP_CLEANUP=1"
)) {
    if (-not $bootContent.Contains($requiredText)) {
        throw "boot script missing required text: $requiredText"
    }
}

$serviceContent = Get-Content -Raw $serviceFile
foreach ($requiredText in @(
    "After=NetworkManager.service",
    "ExecStart=/home/user/USRP292x/BoardUsrp2922BootConnect.sh",
    "Type=oneshot",
    "WantedBy=multi-user.target"
)) {
    if (-not $serviceContent.Contains($requiredText)) {
        throw "service missing required text: $requiredText"
    }
}

$installContent = Get-Content -Raw $installScript
foreach ($requiredText in @(
    "systemctl daemon-reload",
    "systemctl enable usrp2922-board-autostart.service",
    "systemctl start usrp2922-board-autostart.service"
)) {
    if (-not $installContent.Contains($requiredText)) {
        throw "installer missing required text: $requiredText"
    }
}

Write-Host "board-usrp-autostart-files-ok"
