#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
VENV_PYTHON="$COCKPIT_ROOT/.venv/bin/python"
OPERATOR_API_BASE="${COCKPIT_NATIVE_OPERATOR_API_BASE:-http://127.0.0.1:8079}"
OPERATOR_LOG_PATH="${COCKPIT_NATIVE_OPERATOR_LOG_PATH:-$COCKPIT_ROOT/runtime/openamp_demo_server.log}"
COCKPIT_LOG_PATH="${COCKPIT_NATIVE_REHEARSAL_LOG_PATH:-$COCKPIT_ROOT/runtime/cockpit_native_rehearsal.log}"
CAPTURE_DIR_DEFAULT="$COCKPIT_ROOT/runtime/captures/demo_pack"
MANIFEST_PATH_DEFAULT="$COCKPIT_ROOT/runtime/captures/demo_pack/manifest.md"

CAPTURE_DIR="$CAPTURE_DIR_DEFAULT"
MANIFEST_PATH="$MANIFEST_PATH_DEFAULT"
SKIP_CAPTURE=0
SKIP_GUI=0

while (($#)); do
    case "$1" in
        --output-dir)
            CAPTURE_DIR="${2:?missing value for --output-dir}"
            shift 2
            ;;
        --manifest)
            MANIFEST_PATH="${2:?missing value for --manifest}"
            shift 2
            ;;
        --skip-capture)
            SKIP_CAPTURE=1
            shift
            ;;
        --skip-gui)
            SKIP_GUI=1
            shift
            ;;
        *)
            echo "Unsupported argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Missing native cockpit venv interpreter: $VENV_PYTHON" >&2
    exit 1
fi

mkdir -p "$COCKPIT_ROOT/runtime" "$CAPTURE_DIR"
mkdir -p "$(dirname "$MANIFEST_PATH")"

health_check() {
    "$VENV_PYTHON" - <<'PY' "$OPERATOR_API_BASE"
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
}

capture_probe() {
    "$VENV_PYTHON" - <<'PY' "$OPERATOR_API_BASE"
from __future__ import annotations

import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request(base + "/api/aircraft-position", headers={"Accept": "application/json"})
with opener.open(request, timeout=2.0) as response:
    payload = json.loads(response.read().decode("utf-8"))

print(json.dumps(
    {
        "source_kind": payload.get("source_kind"),
        "source_status": payload.get("source_status"),
        "source_label": payload.get("source_label"),
        "position": payload.get("position"),
    },
    ensure_ascii=False,
))
PY
}

presenter_card() {
    "$VENV_PYTHON" - <<'PY'
from __future__ import annotations

from pathlib import Path

from cockpit_native.adapter import DemoRepoAdapter

ui = DemoRepoAdapter(project_root=Path('.').resolve()).load_contract_bundle().ui_state
story = ui["meta"]["demo_story"]
headline = story["performance_headline"]
flow = story["flow"]
position_source = ui["zones"]["center_tactical_view"]["position_source"]

print("[rehearsal] presenter card:")
print(f"  headline: {headline['summary']}")
print(f"  source:   {position_source['label']} / {position_source['status']}")
print(f"  location: {position_source['coordinate_text']}")
print(f"  note:     {position_source['summary']}")
print("  demo flow:")
for index, step in enumerate(flow, start=1):
    print(f"    {index}. {step['action_id']} -> {step['title']}")
    print(f"       {step['detail']}")
print(f"  report:   {headline['report_path']}")
print("  opener_30s:")
print("    这不是网页 mock，而是原生 Qt/QML 座舱；当前可信 headline 是 1844.1 ms -> 153.778 ms，Current 相比 baseline 提升 91.66%。")
print("  opener_2min:")
print("    首页讲 headline 和中国任务区态势板；飞行页讲地图、位置来源和性能结论；执行页按 Current / Reload / Probe 的顺序做 live 演示。")
PY
}

write_manifest() {
    "$VENV_PYTHON" - <<'PY' "$MANIFEST_PATH" "$CAPTURE_DIR"
from __future__ import annotations

from pathlib import Path

from cockpit_native.adapter import DemoRepoAdapter

manifest_path = Path(__import__("sys").argv[1]).resolve()
capture_dir = Path(__import__("sys").argv[2]).resolve()
ui = DemoRepoAdapter(project_root=Path('.').resolve()).load_contract_bundle().ui_state
story = ui["meta"]["demo_story"]
headline = story["performance_headline"]
flow = story["flow"]
position_source = ui["zones"]["center_tactical_view"]["position_source"]

body = f"""# cockpit_native demo pack

## Headline

- {headline['summary']}
- {headline['callout']}
- report: `{headline['report_path']}`

## Position Source

- label: `{position_source['label']}`
- status: `{position_source['status']}`
- coordinates: `{position_source['coordinate_text']}`
- note: {position_source['summary']}

## Demo Flow

1. `{flow[0]['action_id']}` - {flow[0]['title']}
   {flow[0]['detail']}
2. `{flow[1]['action_id']}` - {flow[1]['title']}
   {flow[1]['detail']}
3. `{flow[2]['action_id']}` - {flow[2]['title']}
   {flow[2]['detail']}

## 30s opener

这不是网页 mock，而是原生 Qt/QML 座舱；当前可信 headline 是 `1844.1 ms -> 153.778 ms`，`Current 相比 baseline 提升 91.66%`。

## 2min opener

首页讲 headline 和中国任务区态势板；飞行页讲地图、位置来源和性能结论；执行页按 `Current / Reload / Probe` 的顺序做 live 演示。

## Static Pack

- `{capture_dir / 'landing.png'}`
- `{capture_dir / 'flight.png'}`
- `{capture_dir / 'actiondock.png'}`
"""
manifest_path.write_text(body, encoding="utf-8")
print(manifest_path)
PY
}

echo "[rehearsal] project root: $PROJECT_ROOT"
echo "[rehearsal] operator API: $OPERATOR_API_BASE"

if ! health_check >/dev/null 2>&1; then
    echo "[rehearsal] operator server is offline, launching repo demo server..."
    nohup bash "$SCRIPT_DIR/run_openamp_demo.sh" >"$OPERATOR_LOG_PATH" 2>&1 &
    for ((step=0; step<20; step+=1)); do
        if health_check >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

health_check >/dev/null
echo "[rehearsal] operator server healthy"
echo "[rehearsal] aircraft-position:"
capture_probe
presenter_card

if [[ "$SKIP_CAPTURE" -ne 1 ]]; then
    echo "[rehearsal] exporting demo pack to: $CAPTURE_DIR"
    bash "$SCRIPT_DIR/export_cockpit_native_demo_pack.sh" "$CAPTURE_DIR" >/tmp/cockpit_native_demo_pack.log 2>&1
    cat /tmp/cockpit_native_demo_pack.log
fi

echo "[rehearsal] writing manifest:"
write_manifest

if [[ "$SKIP_GUI" -ne 1 ]]; then
    echo "[rehearsal] launching live cockpit..."
    nohup env COCKPIT_NATIVE_SKIP_OPERATOR_AUTOSTART=1 bash "$SCRIPT_DIR/run_cockpit_native.sh" >"$COCKPIT_LOG_PATH" 2>&1 &
    sleep 5
    echo "[rehearsal] live cockpit processes:"
    ps -ef | grep -E 'cockpit_native/.venv/bin/python -m cockpit_native --software-render' | grep -v grep || true
    echo "[rehearsal] live cockpit log: $COCKPIT_LOG_PATH"
fi

echo "[rehearsal] static pack:"
echo "  $CAPTURE_DIR/landing.png"
echo "  $CAPTURE_DIR/flight.png"
echo "  $CAPTURE_DIR/actiondock.png"
echo "[rehearsal] manifest:"
echo "  $MANIFEST_PATH"
echo "[rehearsal] go-no-go:"
bash "$SCRIPT_DIR/print_cockpit_native_go_no_go.sh" "$CAPTURE_DIR"
