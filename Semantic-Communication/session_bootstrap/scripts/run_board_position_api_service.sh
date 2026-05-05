#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOCAL_SERVICE="${SCRIPT_DIR}/board_position_api_service.py"

if [[ -f "$LOCAL_SERVICE" ]]; then
  exec python3 "$LOCAL_SERVICE" "$@"
fi

REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

exec python3 \
  "${REPO_ROOT}/session_bootstrap/demo/openamp_control_plane_demo/board_position_api_service.py" \
  "$@"
