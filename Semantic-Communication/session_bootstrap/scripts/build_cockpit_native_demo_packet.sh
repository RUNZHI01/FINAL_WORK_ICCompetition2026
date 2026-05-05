#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PACK_ROOT_DEFAULT="$COCKPIT_ROOT/runtime/deliverables/cockpit_native_demo_packet_$TIMESTAMP"
PACK_ROOT="$PACK_ROOT_DEFAULT"
SKIP_REHEARSAL=0

while (($#)); do
    case "$1" in
        --output-dir)
            PACK_ROOT="${2:?missing value for --output-dir}"
            shift 2
            ;;
        --skip-rehearsal)
            SKIP_REHEARSAL=1
            shift
            ;;
        *)
            echo "Unsupported argument: $1" >&2
            exit 2
            ;;
    esac
done

PACK_ROOT="$(python3 - <<'PY' "$PACK_ROOT"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"
PACK_NAME="$(basename "$PACK_ROOT")"
PACK_PARENT="$(dirname "$PACK_ROOT")"
ARCHIVE_PATH="$PACK_PARENT/${PACK_NAME}.tar.gz"
ZIP_PATH="$PACK_PARENT/${PACK_NAME}.zip"
CHECKSUM_PATH="$PACK_ROOT/SHA256SUMS.txt"
LATEST_DIR="$PACK_PARENT/cockpit_native_demo_packet_latest"
LATEST_ARCHIVE="$PACK_PARENT/cockpit_native_demo_packet_latest.tar.gz"
LATEST_ZIP="$PACK_PARENT/cockpit_native_demo_packet_latest.zip"
LATEST_NOTE="$PACK_PARENT/cockpit_native_demo_packet_latest.txt"
LATEST_HTML="$PACK_PARENT/cockpit_native_demo_packet_latest.html"
LATEST_CMD="$PACK_PARENT/cockpit_native_demo_packet_latest.cmd"
LATEST_PS1="$PACK_PARENT/cockpit_native_demo_packet_latest.ps1"
CAPTURE_DIR="$COCKPIT_ROOT/runtime/captures/demo_pack"

mkdir -p "$PACK_ROOT"

if [[ "$SKIP_REHEARSAL" -ne 1 ]]; then
    bash "$SCRIPT_DIR/run_cockpit_native_demo_rehearsal.sh" --skip-gui --output-dir "$CAPTURE_DIR" >/tmp/cockpit_native_packet_rehearsal.log 2>&1
    cat /tmp/cockpit_native_packet_rehearsal.log
fi

cp "$PROJECT_ROOT/session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md" "$PACK_ROOT/"
cp "$PROJECT_ROOT/session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md" "$PACK_ROOT/"
cp "$CAPTURE_DIR/manifest.md" "$PACK_ROOT/"
cp "$CAPTURE_DIR/landing.png" "$PACK_ROOT/"
cp "$CAPTURE_DIR/flight.png" "$PACK_ROOT/"
cp "$CAPTURE_DIR/actiondock.png" "$PACK_ROOT/"

bash "$SCRIPT_DIR/print_cockpit_native_go_no_go.sh" "$CAPTURE_DIR" > "$PACK_ROOT/go_no_go.txt"

"$PROJECT_ROOT/cockpit_native/.venv/bin/python" - <<'PY' "$PACK_ROOT"
from __future__ import annotations

import json
from pathlib import Path

from cockpit_native.adapter import DemoRepoAdapter

pack_root = Path(__import__("sys").argv[1]).resolve()
ui = DemoRepoAdapter(project_root=Path('.').resolve()).load_contract_bundle().ui_state
story = ui["meta"]["demo_story"]
position_source = ui["zones"]["center_tactical_view"]["position_source"]
payload = {
    "headline": story["performance_headline"],
    "position_source": position_source,
    "demo_flow": story["flow"],
    "artifacts": {
        "landing": "landing.png",
        "flight": "flight.png",
        "actiondock": "actiondock.png",
        "manifest": "manifest.md",
        "go_no_go": "go_no_go.txt",
        "html": "index.html",
        "embedded_html": "index_embedded.html",
        "talk_track": "cockpit_native_demo_talk_track_2026-03-24.md",
        "packet_index": "cockpit_native_demo_packet_index_2026-03-24.md",
    },
}
(pack_root / "SUMMARY.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

python3 - <<'PY' "$PACK_ROOT"
from __future__ import annotations

import base64
from pathlib import Path

pack_root = Path(__import__("sys").argv[1]).resolve()
headline = "1844.1 ms -> 153.778 ms，Current 相比 baseline 提升 91.66%。"
landing_data = base64.b64encode((pack_root / "landing.png").read_bytes()).decode("ascii")
flight_data = base64.b64encode((pack_root / "flight.png").read_bytes()).decode("ascii")
actiondock_data = base64.b64encode((pack_root / "actiondock.png").read_bytes()).decode("ascii")
body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>cockpit_native demo packet</title>
  <style>
    :root {{
      --bg: #06111b;
      --panel: #0c1c2b;
      --panel2: #102437;
      --line: #274c69;
      --accent: #84ecff;
      --gold: #f0c27a;
      --text: #eef8ff;
      --muted: #99b5c9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Ubuntu Sans", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 20% 0%, rgba(132,236,255,0.08), transparent 32%),
        radial-gradient(circle at 100% 30%, rgba(240,194,122,0.05), transparent 28%),
        linear-gradient(180deg, #06111b, #040a10 68%);
      color: var(--text);
    }}
    .wrap {{
      width: min(1480px, calc(100vw - 40px));
      margin: 24px auto 48px;
    }}
    .hero, .panel {{
      background: linear-gradient(180deg, rgba(16,36,55,0.96), rgba(9,20,31,0.96));
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 18px 60px rgba(0,0,0,0.25);
    }}
    .hero {{
      padding: 24px 26px;
      margin-bottom: 18px;
    }}
    .eyebrow {{
      color: var(--accent);
      font: 700 11px/1.2 "Ubuntu Sans Mono", monospace;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 38px;
      line-height: 1.05;
    }}
    .headline {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
    }}
    .support {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 15px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      padding: 20px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .chip {{
      padding: 10px 14px;
      border: 1px solid rgba(132,236,255,0.28);
      border-radius: 999px;
      background: rgba(132,236,255,0.06);
      color: var(--text);
      font-size: 14px;
    }}
    .chip strong {{ color: var(--accent); }}
    ol {{
      margin: 10px 0 0 20px;
      padding: 0;
      color: var(--text);
      line-height: 1.55;
    }}
    .shots {{
      display: grid;
      gap: 18px;
    }}
    .shot {{
      background: linear-gradient(180deg, rgba(14,28,42,0.96), rgba(9,18,28,0.96));
      border: 1px solid rgba(132,236,255,0.16);
      border-radius: 18px;
      padding: 14px;
    }}
    .shot h2 {{
      margin: 0 0 10px;
      font-size: 20px;
    }}
    img {{
      width: 100%;
      height: auto;
      display: block;
      border-radius: 12px;
      border: 1px solid rgba(132,236,255,0.16);
    }}
    .foot {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 960px) {{
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 30px; }}
      .headline {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">Feiteng / Native Cockpit Demo Packet</div>
      <h1>cockpit_native 演示总览</h1>
      <p class="headline">{headline}</p>
      <p class="support">这套原生座舱不是网页 mock，而是直接承接 TVM/OpenAMP 合同、任务地图和 live action 的演示壳体。</p>
      <div class="chips">
        <div class="chip"><strong>开场</strong> landing.png</div>
        <div class="chip"><strong>地图</strong> flight.png</div>
        <div class="chip"><strong>控制台</strong> actiondock.png</div>
        <div class="chip"><strong>口径</strong> go_no_go.txt / manifest.md</div>
      </div>
    </section>
    <section class="grid">
      <div class="panel">
        <div class="eyebrow">Demo Flow</div>
        <ol>
          <li>首页：给 headline 和中国任务区第一印象。</li>
          <li>飞行合同页：讲地图、位置来源和可信性能结论。</li>
          <li>执行页：按 Current / Reload / Probe 的顺序做 live 演示。</li>
        </ol>
      </div>
      <div class="panel">
        <div class="eyebrow">Openers</div>
        <p class="support"><strong>30 秒：</strong>这不是网页 mock，而是原生 Qt/QML 座舱；当前可信 headline 是 1844.1 ms -> 153.778 ms，Current 相比 baseline 提升 91.66%。</p>
        <p class="support"><strong>2 分钟：</strong>首页讲 headline 和中国任务区态势板；飞行页讲地图、位置来源和性能结论；执行页按 Current / Reload / Probe 的顺序做 live 演示。</p>
      </div>
    </section>
    <section class="shots">
      <article class="shot">
        <h2>1. Landing</h2>
        <img src="landing.png" alt="cockpit landing" />
      </article>
      <article class="shot">
        <h2>2. Flight</h2>
        <img src="flight.png" alt="cockpit flight" />
      </article>
      <article class="shot">
        <h2>3. Action Dock</h2>
        <img src="actiondock.png" alt="cockpit action dock" />
      </article>
    </section>
    <p class="foot">附带文件：README.txt / OPEN_ME_FIRST.txt / manifest.md / go_no_go.txt / SHA256SUMS.txt / talk track / packet index</p>
  </div>
</body>
</html>
"""
(pack_root / "index.html").write_text(body, encoding="utf-8")
(pack_root / "index_embedded.html").write_text(
    body
    .replace('src="landing.png"', f'src="data:image/png;base64,{landing_data}"')
    .replace('src="flight.png"', f'src="data:image/png;base64,{flight_data}"')
    .replace('src="actiondock.png"', f'src="data:image/png;base64,{actiondock_data}"'),
    encoding="utf-8",
)
print(pack_root / "index.html")
PY

cat > "$PACK_ROOT/OPEN_ME_FIRST.txt" <<EOF
cockpit_native demo packet

Start here:
1. go_no_go.txt
2. manifest.md
3. index_embedded.html
4. index.html
5. cockpit_native_demo_talk_track_2026-03-24.md
6. landing.png
7. flight.png
8. actiondock.png

One-line headline:
1844.1 ms -> 153.778 ms, Current relative to baseline improves 91.66%.
EOF

cat > "$PACK_ROOT/WINDOWS_OPEN_FIRST.txt" <<EOF
Windows quick open:

1. Double-click index_embedded.html
2. If browser blocks local content, open landing.png / flight.png / actiondock.png directly
3. Read go_no_go.txt for the live status summary

One-line headline:
1844.1 ms -> 153.778 ms, Current relative to baseline improves 91.66%.
EOF

cat > "$PACK_ROOT/FAILOVER.txt" <<EOF
cockpit_native failover plan

If live GUI is unstable:
1. Open cockpit_native_demo_packet_latest.html or index_embedded.html
2. Start from landing.png and state the headline:
   1844.1 ms -> 153.778 ms, Current relative to baseline improves 91.66%
3. Then show flight.png and explain:
   - China flight board
   - explicit position source
   - no fake live GPS
4. Then show actiondock.png and explain:
   - Current / Reload / Probe
   - live actions are clickable
   - limitations are explicit, not hidden

Minimum acceptable fallback order:
- go_no_go.txt
- landing.png
- flight.png
- actiondock.png
- cockpit_native_demo_talk_track_2026-03-24.md
EOF

cat > "$PACK_ROOT/PRESENTER_CARD.txt" <<EOF
cockpit_native presenter card

Headline:
1844.1 ms -> 153.778 ms, Current relative to baseline improves 91.66%

30s opener:
这不是网页 mock，而是原生 Qt/QML 座舱；当前可信 headline 是 1844.1 ms -> 153.778 ms，Current 相比 baseline 提升 91.66%。

2min structure:
1. 首页讲 headline 和中国任务区态势板
2. 飞行页讲地图、位置来源和可信性能结论
3. 执行页按 Current / Reload / Probe 的顺序做 live 演示

Live order:
1. current_online_rebuild
2. reload_contracts
3. probe_live_board
EOF

cat > "$PACK_ROOT/open_demo_packet.ps1" <<'EOF'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$embedded = Join-Path $root 'index_embedded.html'
$fallback = Join-Path $root 'index.html'
if (Test-Path $embedded) {
    Start-Process $embedded
} elseif (Test-Path $fallback) {
    Start-Process $fallback
} else {
    Write-Host "No overview html found in demo packet." -ForegroundColor Yellow
}
EOF

cat > "$PACK_ROOT/open_demo_packet.cmd" <<'EOF'
@echo off
setlocal
set ROOT=%~dp0
if exist "%ROOT%index_embedded.html" (
  start "" "%ROOT%index_embedded.html"
) else if exist "%ROOT%index.html" (
  start "" "%ROOT%index.html"
) else (
  echo No overview html found in demo packet.
)
endlocal
EOF

cat > "$PACK_ROOT/README.txt" <<EOF
cockpit_native demo packet

Files:
- OPEN_ME_FIRST.txt
- PRESENTER_CARD.txt
- FAILOVER.txt
- WINDOWS_OPEN_FIRST.txt
- open_demo_packet.ps1
- open_demo_packet.cmd
- SUMMARY.json
- index_embedded.html
- index.html
- landing.png
- flight.png
- actiondock.png
- manifest.md
- go_no_go.txt
- SHA256SUMS.txt
- cockpit_native_demo_talk_track_2026-03-24.md
- cockpit_native_demo_packet_index_2026-03-24.md

Recommended read order:
1. go_no_go.txt
2. manifest.md
3. index_embedded.html
4. index.html
5. cockpit_native_demo_talk_track_2026-03-24.md
6. landing.png -> flight.png -> actiondock.png
EOF

(
    cd "$PACK_ROOT"
    sha256sum \
        OPEN_ME_FIRST.txt \
        PRESENTER_CARD.txt \
        FAILOVER.txt \
        WINDOWS_OPEN_FIRST.txt \
        open_demo_packet.ps1 \
        open_demo_packet.cmd \
        SUMMARY.json \
        index_embedded.html \
        index.html \
        README.txt \
        landing.png \
        flight.png \
        actiondock.png \
        manifest.md \
        go_no_go.txt \
        cockpit_native_demo_talk_track_2026-03-24.md \
        cockpit_native_demo_packet_index_2026-03-24.md \
        > "$CHECKSUM_PATH"
)

tar -czf "$ARCHIVE_PATH" -C "$PACK_PARENT" "$PACK_NAME"

python3 - <<'PY' "$PACK_PARENT" "$PACK_NAME" "$ZIP_PATH"
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

pack_parent = Path(sys.argv[1]).resolve()
pack_name = sys.argv[2]
zip_path = Path(sys.argv[3]).resolve()
root = pack_parent / pack_name

with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(pack_parent))
PY

mkdir -p "$LATEST_DIR"
cp "$PACK_ROOT/README.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/SHA256SUMS.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/landing.png" "$LATEST_DIR/"
cp "$PACK_ROOT/flight.png" "$LATEST_DIR/"
cp "$PACK_ROOT/actiondock.png" "$LATEST_DIR/"
cp "$PACK_ROOT/manifest.md" "$LATEST_DIR/"
cp "$PACK_ROOT/go_no_go.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/cockpit_native_demo_talk_track_2026-03-24.md" "$LATEST_DIR/"
cp "$PACK_ROOT/cockpit_native_demo_packet_index_2026-03-24.md" "$LATEST_DIR/"
cp "$PACK_ROOT/OPEN_ME_FIRST.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/PRESENTER_CARD.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/FAILOVER.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/WINDOWS_OPEN_FIRST.txt" "$LATEST_DIR/"
cp "$PACK_ROOT/open_demo_packet.ps1" "$LATEST_DIR/"
cp "$PACK_ROOT/open_demo_packet.cmd" "$LATEST_DIR/"
cp "$PACK_ROOT/SUMMARY.json" "$LATEST_DIR/"
cp "$PACK_ROOT/index_embedded.html" "$LATEST_DIR/"
cp "$PACK_ROOT/index.html" "$LATEST_DIR/"

cp "$ARCHIVE_PATH" "$LATEST_ARCHIVE"
cp "$ZIP_PATH" "$LATEST_ZIP"
cp "$LATEST_DIR/index_embedded.html" "$LATEST_HTML"

cat > "$LATEST_CMD" <<'EOF'
@echo off
setlocal
set ROOT=%~dp0
if exist "%ROOT%cockpit_native_demo_packet_latest.html" (
  start "" "%ROOT%cockpit_native_demo_packet_latest.html"
) else (
  echo Missing cockpit_native_demo_packet_latest.html
)
endlocal
EOF

cat > "$LATEST_PS1" <<'EOF'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $root 'cockpit_native_demo_packet_latest.html'
if (Test-Path $html) {
    Start-Process $html
} else {
    Write-Host "Missing cockpit_native_demo_packet_latest.html" -ForegroundColor Yellow
}
EOF

cat > "$LATEST_NOTE" <<EOF
cockpit_native latest deliverable

headline: 1844.1 ms -> 153.778 ms, Current relative to baseline improves 91.66%
latest_dir=$LATEST_DIR
latest_tar_gz=$LATEST_ARCHIVE
latest_zip=$LATEST_ZIP
latest_html=$LATEST_HTML
latest_cmd=$LATEST_CMD
latest_ps1=$LATEST_PS1
source_packet=$PACK_ROOT

open_order:
1. $LATEST_HTML
2. $LATEST_DIR/go_no_go.txt
3. $LATEST_DIR/manifest.md
4. $LATEST_DIR/index_embedded.html
5. $LATEST_DIR/index.html
6. $LATEST_DIR/cockpit_native_demo_talk_track_2026-03-24.md
7. $LATEST_DIR/landing.png
8. $LATEST_DIR/flight.png
9. $LATEST_DIR/actiondock.png
EOF

printf '%s\n' "$ARCHIVE_PATH"
printf '%s\n' "$ZIP_PATH"
printf '%s\n' "$LATEST_DIR"
printf '%s\n' "$LATEST_ARCHIVE"
printf '%s\n' "$LATEST_ZIP"
printf '%s\n' "$LATEST_HTML"
