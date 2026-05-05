#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_PACKET_DIR="$PROJECT_ROOT/cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest"
PACKET_DIR="${1:-$DEFAULT_PACKET_DIR}"

PACKET_DIR="$(python3 - <<'PY' "$PACKET_DIR"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"

if [[ ! -d "$PACKET_DIR" ]]; then
    echo "[packet-verify] NO-GO"
    echo "reason: packet directory not found: $PACKET_DIR"
    exit 1
fi

required_files=(
    OPEN_ME_FIRST.txt
    WINDOWS_OPEN_FIRST.txt
    README.txt
    SUMMARY.json
    SHA256SUMS.txt
    manifest.md
    go_no_go.txt
    cockpit_native_demo_talk_track_2026-03-24.md
    cockpit_native_demo_packet_index_2026-03-24.md
    index.html
    index_embedded.html
    open_demo_packet.ps1
    open_demo_packet.cmd
    landing.png
    flight.png
    actiondock.png
)

missing=()
for artifact in "${required_files[@]}"; do
    if [[ ! -f "$PACKET_DIR/$artifact" ]]; then
        missing+=("$artifact")
    fi
done

if ((${#missing[@]} > 0)); then
    echo "[packet-verify] NO-GO"
    echo "reason: missing artifacts"
    printf '  - %s\n' "${missing[@]}"
    exit 1
fi

checksum_ok=0
if (
    cd "$PACKET_DIR"
    sha256sum -c SHA256SUMS.txt >/tmp/cockpit_packet_checksum.log 2>&1
); then
    checksum_ok=1
fi

if [[ "$checksum_ok" -ne 1 ]]; then
    echo "[packet-verify] NO-GO"
    echo "reason: checksum verification failed"
    cat /tmp/cockpit_packet_checksum.log
    exit 1
fi

echo "[packet-verify] GO"
echo "packet_dir: $PACKET_DIR"
echo "artifacts: ${#required_files[@]}"
echo "checksum: ok"
echo "open_first: $PACKET_DIR/OPEN_ME_FIRST.txt"
echo "embedded_html: $PACKET_DIR/index_embedded.html"
echo "talk_track: $PACKET_DIR/cockpit_native_demo_talk_track_2026-03-24.md"
