#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
VENV_PYTHON="$COCKPIT_ROOT/.venv/bin/python"
OUTPUT_DIR="${1:-$COCKPIT_ROOT/runtime/captures/demo_pack}"

if [[ -n "${COCKPIT_NATIVE_DEMO_PACK_WIDTH:-}" && -n "${COCKPIT_NATIVE_DEMO_PACK_HEIGHT:-}" ]]; then
    CAPTURE_WIDTH="${COCKPIT_NATIVE_DEMO_PACK_WIDTH}"
    CAPTURE_HEIGHT="${COCKPIT_NATIVE_DEMO_PACK_HEIGHT}"
else
    read -r CAPTURE_WIDTH CAPTURE_HEIGHT < <(
        "$VENV_PYTHON" - <<'PY'
from __future__ import annotations

try:
    from PySide6.QtGui import QGuiApplication
except Exception:
    print("1920 1200")
    raise SystemExit(0)

app = QGuiApplication(["demo-pack-size-probe"])
screen = app.primaryScreen()
if screen is None:
    print("1920 1200")
    raise SystemExit(0)

geometry = screen.geometry()
dpr = max(1.0, float(screen.devicePixelRatio()))
width = int(geometry.width() * min(dpr, 1.5))
height = int(geometry.height() * min(dpr, 1.5))
width = max(1920, min(2560, width))
height = max(1200, min(1600, height))
print(f"{width} {height}")
PY
    )
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Missing native cockpit venv interpreter: $VENV_PYTHON" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

bash "$SCRIPT_DIR/run_cockpit_native_capture.sh" --page 0 --width "$CAPTURE_WIDTH" --height "$CAPTURE_HEIGHT" --output "$OUTPUT_DIR/landing.png"
bash "$SCRIPT_DIR/run_cockpit_native_capture.sh" --page 1 --width "$CAPTURE_WIDTH" --height "$CAPTURE_HEIGHT" --output "$OUTPUT_DIR/flight.png"
bash "$SCRIPT_DIR/run_cockpit_native_capture.sh" --page 2 --width "$CAPTURE_WIDTH" --height "$CAPTURE_HEIGHT" --output "$OUTPUT_DIR/actiondock.png"

printf '%s\n' "$OUTPUT_DIR"
