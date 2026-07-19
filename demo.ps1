param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "init", "check", "help")]
    [string]$Action = "start",
    [string]$BoardHost = "100.121.87.73",
    [string]$BoardUser = "user",
    [int]$BoardPort = 22,
    [string]$GitBashPath = "",
    [string]$BoardPassword = "",
    [switch]$ForceNodeInstall,
    [switch]$ForceDockerBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$StartScript = Join-Path $PSScriptRoot "scripts\demo\start.ps1"
$InitScript = Join-Path $PSScriptRoot "scripts\demo\init.ps1"
$StartParameterNames = @("BoardHost", "BoardUser", "BoardPort", "GitBashPath", "BoardPassword")
$InitParameterNames = @("ForceNodeInstall", "ForceDockerBuild")

function Assert-NoBoundParameters {
    param(
        [Parameter(Mandatory = $true)][string[]]$Names,
        [Parameter(Mandatory = $true)][string]$ForAction
    )

    $Unexpected = @($Names | Where-Object { $PSBoundParametersSnapshot.ContainsKey($_) })
    if ($Unexpected.Count -gt 0) {
        throw "动作 '$ForAction' 不接受参数：$($Unexpected -join ', ')"
    }
}

function Get-BoundParameters {
    param([Parameter(Mandatory = $true)][string[]]$Names)

    $Result = @{}
    foreach ($Name in $Names) {
        if ($PSBoundParametersSnapshot.ContainsKey($Name)) {
            $Result[$Name] = $PSBoundParametersSnapshot[$Name]
        }
    }
    return $Result
}

$PSBoundParametersSnapshot = @{} + $PSBoundParameters

switch ($Action) {
    "start" {
        Assert-NoBoundParameters -Names $InitParameterNames -ForAction $Action
        $Arguments = Get-BoundParameters -Names $StartParameterNames
        & $StartScript @Arguments
        exit 0
    }
    "init" {
        Assert-NoBoundParameters -Names $StartParameterNames -ForAction $Action
        $Arguments = Get-BoundParameters -Names $InitParameterNames
        & $InitScript @Arguments
        exit 0
    }
    "check" {
        Assert-NoBoundParameters -Names ($StartParameterNames + $InitParameterNames) -ForAction $Action
        & $InitScript -CheckOnly
        exit 0
    }
    "help" {
        Assert-NoBoundParameters -Names ($StartParameterNames + $InitParameterNames) -ForAction $Action
        Write-Output @'
用法：
  .\demo.ps1             启动现场演示
  .\demo.ps1 start       启动现场演示
  .\demo.ps1 init        首次初始化本机
  .\demo.ps1 check       只读检查本机环境
  .\demo.ps1 help        显示本帮助

临时连接配置：
  $env:REMOTE_HOST = "100.121.87.73"
  $env:REMOTE_USER = "user"
  .\demo.ps1

命令行参数优先；变量为空时使用默认地址和用户。
现场说明：scripts/demo/STARTUP.md
'@
        exit 0
    }
}
