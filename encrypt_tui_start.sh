#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
LIBOQS_DIST="$ROOT_DIR/liboqs-dist"

cd "$ROOT_DIR"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "[encrypt_tui_start] 缺少虚拟环境: $VENV_PYTHON" >&2
    echo "[encrypt_tui_start] 先执行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
fi

if [ -z "${OQS_INSTALL_PATH:-}" ] && [ -d "$LIBOQS_DIST" ]; then
    export OQS_INSTALL_PATH="$LIBOQS_DIST"
fi

if ! "$VENV_PYTHON" -c "import textual" >/dev/null 2>&1; then
    echo "[encrypt_tui_start] 当前 .venv 缺少 textual，先执行: source .venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
fi

mkdir -p "$ROOT_DIR/artifacts/tui_sessions"

exec "$VENV_PYTHON" "$ROOT_DIR/scripts/demo_tui.py" "$@"
