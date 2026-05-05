$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$env:ENABLE_TAILSCALE = "1"
if (-not $env:CONTAINER_NAME) {
    $env:CONTAINER_NAME = "iccomp-electron-demo-tailscale"
}
if (-not $env:TAILSCALE_HOSTNAME) {
    $env:TAILSCALE_HOSTNAME = "iccomp-demo"
}
if (-not $env:TAILSCALE_PING_TARGET) {
    $env:TAILSCALE_PING_TARGET = "100.121.87.73"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "run-demo.ps1")
