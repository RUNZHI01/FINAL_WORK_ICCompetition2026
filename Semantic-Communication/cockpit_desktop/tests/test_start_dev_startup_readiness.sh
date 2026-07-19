#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COCKPIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

FAKE_BIN="$TMP_ROOT/bin"
EVENT_LOG="$TMP_ROOT/events.log"
mkdir -p "$FAKE_BIN"
touch "$EVENT_LOG"

cat >"$FAKE_BIN/python3" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-" ]]; then
  echo "startup-services" >>"$START_DEV_TEST_EVENTS"
  exit 0
fi
echo "backend-start $*" >>"$START_DEV_TEST_EVENTS"
exit 0
SH
chmod +x "$FAKE_BIN/python3"
ln -s python3 "$FAKE_BIN/python"

cat >"$FAKE_BIN/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "curl $*" >>"$START_DEV_TEST_EVENTS"
printf '{"status":"ok"}\n'
SH
chmod +x "$FAKE_BIN/curl"

cat >"$FAKE_BIN/npm" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "frontend-start $*" >>"$START_DEV_TEST_EVENTS"
exit 0
SH
chmod +x "$FAKE_BIN/npm"

cat >"$FAKE_BIN/powershell.exe" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$FAKE_BIN/powershell.exe"

MISSING_NODE_MODULES="$TMP_ROOT/missing-node-modules"
READY_NODE_MODULES="$TMP_ROOT/ready-node-modules"
mkdir -p "$READY_NODE_MODULES/.bin"
touch "$READY_NODE_MODULES/.bin/electron-vite"
set +e
PATH="$FAKE_BIN:$PATH" \
START_DEV_TEST_EVENTS="$EVENT_LOG" \
TMPDIR="$TMP_ROOT" \
COCKPIT_NODE_MODULES_DIR="$MISSING_NODE_MODULES" \
COCKPIT_BACKEND_PORT=18079 \
COCKPIT_FRONTEND_PORT=15173 \
REMOTE_HOST=100.121.87.73 \
REMOTE_USER=user \
REMOTE_PASS=test-secret \
  "$COCKPIT_DIR/start-dev.sh" >"$TMP_ROOT/missing-deps.out" 2>&1
missing_deps_status=$?
set -e

if [[ "$missing_deps_status" -eq 0 ]]; then
  echo "startup should fail when cockpit node_modules is missing" >&2
  cat "$TMP_ROOT/missing-deps.out" >&2
  exit 1
fi
if ! grep -q 'init.ps1' "$TMP_ROOT/missing-deps.out"; then
  echo "missing dependency error should point to init.ps1" >&2
  cat "$TMP_ROOT/missing-deps.out" >&2
  exit 1
fi
if grep -q '^backend-start ' "$EVENT_LOG"; then
  echo "backend started before local dependency preflight" >&2
  cat "$EVENT_LOG" >&2
  exit 1
fi

PATH="$FAKE_BIN:$PATH" \
START_DEV_TEST_EVENTS="$EVENT_LOG" \
TMPDIR="$TMP_ROOT" \
COCKPIT_NODE_MODULES_DIR="$READY_NODE_MODULES" \
COCKPIT_BACKEND_PORT=18079 \
COCKPIT_FRONTEND_PORT=15173 \
REMOTE_HOST=100.121.87.73 \
REMOTE_USER=user \
  REMOTE_PASS=test-secret \
  "$COCKPIT_DIR/start-dev.sh" >"$TMP_ROOT/start-dev.out"

if ! grep -q '^startup-services$' "$EVENT_LOG"; then
  echo "missing startup service readiness call" >&2
  cat "$EVENT_LOG" >&2
  exit 1
fi

readiness_line="$(grep -n '^startup-services$' "$EVENT_LOG" | head -1 | cut -d: -f1)"
frontend_line="$(grep -n '^frontend-start ' "$EVENT_LOG" | head -1 | cut -d: -f1)"
if [[ -z "$frontend_line" ]]; then
  echo "missing frontend start" >&2
  cat "$EVENT_LOG" >&2
  exit 1
fi
if (( readiness_line >= frontend_line )); then
  echo "frontend started before service readiness completed" >&2
  cat "$EVENT_LOG" >&2
  exit 1
fi

if ! grep -q 'USRP IQ 微批默认: STREAMING_TVM=0' "$TMP_ROOT/start-dev.out"; then
  echo "IQ streaming TVM should be disabled by default" >&2
  cat "$TMP_ROOT/start-dev.out" >&2
  exit 1
fi

echo "start-dev-startup-readiness-ok"
