#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOCAL_BRIDGE="${SCRIPT_DIR}/aircraft_position_bridge.py"

if [[ -f "$LOCAL_BRIDGE" ]]; then
  exec python3 "$LOCAL_BRIDGE" "$@"
fi

REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

exec python3 \
  "${REPO_ROOT}/session_bootstrap/demo/openamp_control_plane_demo/aircraft_position_bridge.py" \
  "$@"
