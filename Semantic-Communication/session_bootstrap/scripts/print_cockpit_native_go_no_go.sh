#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
VENV_PYTHON="$COCKPIT_ROOT/.venv/bin/python"
OPERATOR_API_BASE="${COCKPIT_NATIVE_OPERATOR_API_BASE:-http://127.0.0.1:8079}"
CAPTURE_DIR="${1:-$COCKPIT_ROOT/runtime/captures/demo_pack}"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "[go-no-go] NO-GO"
    echo "reason: missing venv python at $VENV_PYTHON"
    exit 1
fi

operator_ok=0
if "$VENV_PYTHON" - <<'PY' "$OPERATOR_API_BASE" >/dev/null 2>&1
from __future__ import annotations

import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request(base + "/api/health", headers={"Accept": "application/json"})
with opener.open(request, timeout=1.5) as response:
    payload = json.loads(response.read().decode("utf-8"))
raise SystemExit(0 if str(payload.get("status") or "").strip().lower() == "ok" else 1)
PY
then
    operator_ok=1
fi

live_pid_count=$(ps -ef | grep -E 'cockpit_native/.venv/bin/python -m cockpit_native --software-render' | grep -v grep | wc -l | tr -d ' ' || true)
static_pack_ok=1
for artifact in landing.png flight.png actiondock.png manifest.md; do
    if [[ ! -f "$CAPTURE_DIR/$artifact" ]]; then
        static_pack_ok=0
        break
    fi
done

"$VENV_PYTHON" - <<'PY' "$PROJECT_ROOT" "$OPERATOR_API_BASE" "$CAPTURE_DIR" "$operator_ok" "$live_pid_count" "$static_pack_ok"
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

project_root = Path(sys.argv[1]).resolve()
operator_api_base = sys.argv[2].rstrip("/")
capture_dir = Path(sys.argv[3]).resolve()
operator_ok = sys.argv[4] == "1"
live_pid_count = int(sys.argv[5])
static_pack_ok = sys.argv[6] == "1"

from cockpit_native.adapter import DemoRepoAdapter

adapter = DemoRepoAdapter(project_root=project_root)
ui = adapter.load_contract_bundle().ui_state
story = ui["meta"]["demo_story"]
headline = story["performance_headline"]
flow = story["flow"]
position_source = ui["zones"]["center_tactical_view"]["position_source"]

status = "GO" if operator_ok and static_pack_ok else ("WARN" if operator_ok or static_pack_ok else "NO-GO")
print(f"[go-no-go] {status}")
print(f"headline: {headline['summary']}")
print(f"operator: {'healthy' if operator_ok else 'offline'} @ {operator_api_base}")
print(f"location: {position_source['label']} / {position_source['status']} / {position_source['coordinate_text']}")
print(f"live_cockpit_processes: {live_pid_count}")
print(f"static_pack: {'ready' if static_pack_ok else 'missing'} @ {capture_dir}")
print("demo_flow:")
for index, step in enumerate(flow, start=1):
    print(f"  {index}. {step['action_id']} -> {step['title']}")
print("talk_track: session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md")
print("static_pack_files:")
for artifact in ("landing.png", "flight.png", "actiondock.png", "manifest.md"):
    print(f"  - {capture_dir / artifact}")
PY
