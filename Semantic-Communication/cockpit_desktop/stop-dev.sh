#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
FRONTEND_PORT="${COCKPIT_FRONTEND_PORT:-5173}"

to_windows_path() {
  local path="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path"
    return 0
  fi
  (cd "$path" && pwd -W) 2>/dev/null || printf '%s\n' "$path"
}

stop_windows_port_listeners() {
  local port="$1"
  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi
  COCKPIT_STOP_PORT="$port" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
    $ErrorActionPreference = "SilentlyContinue"
    $port = [int]$env:COCKPIT_STOP_PORT
    Get-NetTCPConnection -State Listen -LocalPort $port |
      Select-Object -ExpandProperty OwningProcess -Unique |
      Where-Object { $_ -and $_ -ne $PID } |
      ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  ' >/dev/null 2>&1 || true
}

stop_windows_cockpit_processes() {
  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi
  local repo_root_win script_dir_win
  repo_root_win="$(to_windows_path "$REPO_ROOT")"
  script_dir_win="$(to_windows_path "$SCRIPT_DIR")"
  COCKPIT_REPO_ROOT_WIN="$repo_root_win" \
  COCKPIT_SCRIPT_DIR_WIN="$script_dir_win" \
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
      $ErrorActionPreference = "SilentlyContinue"
      $roots = @($env:COCKPIT_REPO_ROOT_WIN, $env:COCKPIT_SCRIPT_DIR_WIN) |
        Where-Object { $_ } |
        ForEach-Object { [regex]::Escape($_) }
      $serverPattern = "Semantic-Communication[/\\]session_bootstrap[/\\]demo[/\\]openamp_control_plane_demo[/\\]server\.py"
      $targetPatterns = @(
        "server\.py.*--host.*--port",
        "electron-vite(\.js)?\s+dev",
        "npm-cli\.js.*run\s+dev",
        "electron\.exe.*cockpit_desktop",
        "esbuild\.exe.*--service="
      )
      Get-CimInstance Win32_Process | Where-Object {
        $cmd = $_.CommandLine
        if (-not $cmd) {
          $false
        } else {
          $inTree = (($roots | Where-Object { $cmd -match $_ }).Count -gt 0)
          $matchesTarget = (($targetPatterns | Where-Object { $cmd -match $_ }).Count -gt 0)
          ($inTree -and $matchesTarget) -or ($cmd -match $serverPattern)
        }
      } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      }
    ' >/dev/null 2>&1 || true
}

find_port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti TCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "$port/tcp" 2>/dev/null || true
    return 0
  fi
  return 0
}

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

echo "停止 Cockpit Desktop 开发环境..."

stop_pid_file "${TMPDIR:-/tmp}/cockpit-dev.pid"
stop_pid_file "${TMPDIR:-/tmp}/cockpit-backend.pid"

if command -v powershell.exe >/dev/null 2>&1; then
  stop_windows_cockpit_processes
  stop_windows_port_listeners "$BACKEND_PORT"
  stop_windows_port_listeners "$FRONTEND_PORT"
fi

BACKEND_PIDS="$(find_port_pids "$BACKEND_PORT")"
if [[ -n "$BACKEND_PIDS" ]]; then
  kill $BACKEND_PIDS 2>/dev/null || true
fi

FRONTEND_PIDS="$(find_port_pids "$FRONTEND_PORT")"
if [[ -n "$FRONTEND_PIDS" ]]; then
  kill $FRONTEND_PIDS 2>/dev/null || true
fi

pkill -f "electron-vite dev" 2>/dev/null || true
pkill -f "server.py --host" 2>/dev/null || true

echo "开发环境已停止"
