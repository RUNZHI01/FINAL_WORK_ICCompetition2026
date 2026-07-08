#!/usr/bin/env bash
set -euo pipefail

export ENABLE_TAILSCALE=1
export ICCOMP_COCKPIT_PROFILE="${ICCOMP_COCKPIT_PROFILE:-tvm250-prerecorded}"
export CONTAINER_NAME="${CONTAINER_NAME:-iccomp-electron-demo-tailscale}"
export TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-iccomp-demo}"
export TAILSCALE_PING_TARGET="${TAILSCALE_PING_TARGET:-100.121.87.73}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/run-demo.sh"
