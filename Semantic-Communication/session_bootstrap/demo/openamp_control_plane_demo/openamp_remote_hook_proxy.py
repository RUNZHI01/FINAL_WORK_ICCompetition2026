#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import io
import json
from functools import lru_cache
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = PROJECT_ROOT / "session_bootstrap" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from openamp_control_wrapper import resolve_bash_executable  # noqa: E402

SSH_HELPER = PROJECT_ROOT / "session_bootstrap" / "scripts" / "ssh_with_password.sh"
BRIDGE_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_rpmsg_bridge.py"
PROTOCOL_SCRIPT = PROJECT_ROOT / "openamp_mock" / "protocol.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Forward OpenAMP wrapper hook stdin to the board-side rpmsg bridge over SSH so the "
            "demo can expose real control-plane phases without rewriting the inference data path."
        )
    )
    parser.add_argument("--host", required=True, help="Board SSH host.")
    parser.add_argument("--user", required=True, help="Board SSH user.")
    parser.add_argument("--password", required=True, help="Board SSH password.")
    parser.add_argument("--port", default="22", help="Board SSH port.")
    parser.add_argument("--remote-project-root", default="", help="Optional remote repo root override.")
    parser.add_argument("--remote-jscc-dir", default="", help="Optional remote JSCC workspace for root inference.")
    parser.add_argument(
        "--remote-output-root",
        default="/tmp/openamp_demo_hook",
        help="Remote directory used for per-phase bridge artifacts.",
    )
    parser.add_argument("--rpmsg-ctrl", default="/dev/rpmsg_ctrl0", help="Board rpmsg control device.")
    parser.add_argument("--rpmsg-dev", default="/dev/rpmsg0", help="Board rpmsg endpoint device.")
    return parser.parse_args()


def read_event(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def detect_phase(event: dict[str, Any]) -> str:
    phase = str(event.get("phase") or "").strip().upper()
    if phase:
        return phase
    return "STATUS_REQ"


def detect_job_id(event: dict[str, Any]) -> int:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    try:
        return int(payload.get("job_id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    for name in (
        "host",
        "user",
        "password",
        "port",
        "remote_project_root",
        "remote_jscc_dir",
        "remote_output_root",
        "rpmsg_ctrl",
        "rpmsg_dev",
    ):
        value = getattr(args, name, None)
        if isinstance(value, str):
            setattr(args, name, value.strip())
    return args


def parse_json_dict_lines(raw: str) -> list[tuple[int, dict[str, Any]]]:
    parsed: list[tuple[int, dict[str, Any]]] = []
    for line_index, raw_line in enumerate(raw.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            parsed.append((line_index, payload))
    return parsed


def is_synthetic_sudo_failure(payload: dict[str, Any]) -> bool:
    note = str(payload.get("note") or "")
    return (
        payload.get("source") == "openamp_demo_remote_hook_proxy"
        and payload.get("transport_status") == "permission_gate"
        and "could not launch the board-side bridge under sudo" in note
    )


def suppress_synthetic_sudo_failure_tail(raw: str) -> tuple[str, bool]:
    parsed = parse_json_dict_lines(raw)
    if len(parsed) < 2:
        return raw, False

    tail_line_index, tail_payload = parsed[-1]
    if not is_synthetic_sudo_failure(tail_payload):
        return raw, False
    if not any(not is_synthetic_sudo_failure(payload) for _, payload in parsed[:-1]):
        return raw, False

    lines = raw.splitlines()
    filtered_lines = [line for index, line in enumerate(lines) if index != tail_line_index]
    filtered = "\n".join(filtered_lines)
    if raw.endswith("\n") and filtered:
        filtered += "\n"
    return filtered, True


@lru_cache(maxsize=1)
def build_bridge_bundle_base64() -> str:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w") as archive:
            for relative_path, source in (
                ("session_bootstrap/scripts/openamp_rpmsg_bridge.py", BRIDGE_SCRIPT),
                ("openamp_mock/protocol.py", PROTOCOL_SCRIPT),
            ):
                payload = source.read_bytes()
                info = tarfile.TarInfo(relative_path)
                info.size = len(payload)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(payload))

            init_info = tarfile.TarInfo("openamp_mock/__init__.py")
            init_info.size = 0
            init_info.mode = 0o644
            init_info.mtime = 0
            archive.addfile(init_info, io.BytesIO(b""))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def build_remote_command(args: argparse.Namespace, *, phase: str, job_id: int, hook_event_b64: str = "") -> str:
    remote_output_dir = f"{args.remote_output_root.rstrip('/')}/{job_id or 'adhoc'}/{phase.lower()}"
    remote_project_root = str(args.remote_project_root or "").strip()
    # Keep the validated bundle fallback, but prefer the existing remote project copy when available
    # to avoid re-extracting the bridge runtime on every heartbeat.
    bridge_bundle = build_bridge_bundle_base64()
    return f"""
set -euo pipefail
PHASE={shlex.quote(phase)}
OUTPUT_DIR={shlex.quote(remote_output_dir)}
REMOTE_PROJECT_ROOT={shlex.quote(remote_project_root)}
HOOK_EVENT_B64={shlex.quote(hook_event_b64)}
STAGE_ROOT="$(mktemp -d /tmp/openamp_demo_bridge.XXXXXX)"
HOOK_INPUT_FILE="$STAGE_ROOT/hook_event.json"
cleanup() {{
  if command -v sudo >/dev/null 2>&1; then
    printf '%s\\n' "${{SUDO_PASSWORD:-}}" | sudo -S -p '' rm -rf "$STAGE_ROOT" >/dev/null 2>&1 || true
  fi
  rm -rf "$STAGE_ROOT" >/dev/null 2>&1 || true
}}
trap cleanup EXIT
REMOTE_BRIDGE_SCRIPT=""
REMOTE_BRIDGE_PYTHONPATH=""
if [[ -n "$REMOTE_PROJECT_ROOT" ]] && [[ -f "$REMOTE_PROJECT_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py" ]] && [[ -f "$REMOTE_PROJECT_ROOT/openamp_mock/protocol.py" ]]; then
  REMOTE_BRIDGE_SCRIPT="$REMOTE_PROJECT_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py"
  REMOTE_BRIDGE_PYTHONPATH="$REMOTE_PROJECT_ROOT"
else
  STAGE_ROOT="$STAGE_ROOT" PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import base64
import gzip
import io
import os
from pathlib import Path
import tarfile

stage_root = Path(os.environ["STAGE_ROOT"])
stage_root.mkdir(parents=True, exist_ok=True)
bundle = base64.b64decode({bridge_bundle!r})
with gzip.GzipFile(fileobj=io.BytesIO(bundle), mode="rb") as gzip_file:
    with tarfile.open(fileobj=gzip_file, mode="r:") as archive:
        archive.extractall(stage_root)
PY
fi
BRIDGE_SCRIPT="${{REMOTE_BRIDGE_SCRIPT:-$STAGE_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py}}"
BRIDGE_PYTHONPATH="${{REMOTE_BRIDGE_PYTHONPATH:-$STAGE_ROOT}}"
if [[ "${{SUDO_PASSWORD+x}}" != "x" ]]; then
  IFS= read -r SUDO_PASSWORD || SUDO_PASSWORD=""
fi
HOOK_INPUT_FILE="$HOOK_INPUT_FILE" HOOK_EVENT_B64="$HOOK_EVENT_B64" python3 - <<'PY'
import base64
import os
from pathlib import Path

Path(os.environ["HOOK_INPUT_FILE"]).write_bytes(
    base64.b64decode(os.environ.get("HOOK_EVENT_B64", ""))
)
PY
mkdir -p "$OUTPUT_DIR"
emit_sudo_failure() {{
  local detail="${{1:-sudo returned a non-zero exit status.}}"
  PHASE="$PHASE" NOTE="$detail" RPMSG_CTRL={shlex.quote(args.rpmsg_ctrl)} RPMSG_DEV={shlex.quote(args.rpmsg_dev)} python3 - <<'PY'
import json
import os

phase = os.environ.get("PHASE", "").strip() or "STATUS_REQ"
detail = os.environ.get("NOTE", "").strip() or "sudo returned a non-zero exit status."
print(
    json.dumps(
        {{
            "phase": phase,
            "source": "openamp_demo_remote_hook_proxy",
            "transport_status": "permission_gate",
            "protocol_semantics": "not_attempted",
            "note": f"{{phase}} could not launch the board-side bridge under sudo: {{detail}}",
            "rpmsg_ctrl": os.environ.get("RPMSG_CTRL", ""),
            "rpmsg_dev": os.environ.get("RPMSG_DEV", ""),
        }},
        ensure_ascii=False,
    )
)
PY
}}
run_bridge() {{
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BRIDGE_PYTHONPATH${{PYTHONPATH:+:$PYTHONPATH}}" OPENAMP_PHASE="$PHASE" python3 "$BRIDGE_SCRIPT" --hook-stdin --rpmsg-ctrl {shlex.quote(args.rpmsg_ctrl)} --rpmsg-dev {shlex.quote(args.rpmsg_dev)} --output-dir "$OUTPUT_DIR" <"$HOOK_INPUT_FILE"
}}
run_bridge_with_sudo() {{
  local bridge_stdout="$STAGE_ROOT/bridge.stdout"
  local bridge_stderr="$STAGE_ROOT/bridge.stderr"
  if printf '%s\\n' "$SUDO_PASSWORD" | sudo -S -p '' env PYTHONDONTWRITEBYTECODE=1 OPENAMP_PHASE="$PHASE" PYTHONPATH="$BRIDGE_PYTHONPATH" bash -lc 'python3 "$1" --hook-stdin --rpmsg-ctrl "$2" --rpmsg-dev "$3" --output-dir "$4" < "$5"' bash "$BRIDGE_SCRIPT" {shlex.quote(args.rpmsg_ctrl)} {shlex.quote(args.rpmsg_dev)} "$OUTPUT_DIR" "$HOOK_INPUT_FILE" >"$bridge_stdout" 2>"$bridge_stderr"; then
    if [[ -s "$bridge_stdout" ]]; then
      cat "$bridge_stdout"
    fi
    if [[ -s "$bridge_stderr" ]]; then
      cat "$bridge_stderr" >&2
    fi
    return 0
  fi
  if [[ -s "$bridge_stdout" ]]; then
    cat "$bridge_stdout"
  fi
  if [[ -s "$bridge_stderr" ]]; then
    cat "$bridge_stderr" >&2
  fi
  local sudo_detail=""
  if [[ -s "$bridge_stderr" ]]; then
    sudo_detail="$(python3 - "$bridge_stderr" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").strip()
print(" ".join(text.split()))
PY
)"
  fi
  emit_sudo_failure "$sudo_detail"
  return 1
}}

# Prefer direct device access; otherwise use the operator-supplied board password for this bridge step only.
if [[ "$(id -u)" -eq 0 ]] || {{ [[ -r {shlex.quote(args.rpmsg_dev)} ]] && [[ -w {shlex.quote(args.rpmsg_dev)} ]]; }}; then
  run_bridge
elif command -v sudo >/dev/null 2>&1; then
  run_bridge_with_sudo
else
  run_bridge
fi
""".strip()


def build_remote_stdin_wrapper_command() -> str:
    return """
set -euo pipefail
WRAPPER_STAGE_ROOT="$(mktemp -d /tmp/openamp_demo_proxy.XXXXXX)"
WRAPPER_SCRIPT="$WRAPPER_STAGE_ROOT/remote_hook.sh"
cleanup() {
  rm -rf "$WRAPPER_STAGE_ROOT" >/dev/null 2>&1 || true
}
trap cleanup EXIT
IFS= read -r OPENAMP_REMOTE_SUDO_PASSWORD || OPENAMP_REMOTE_SUDO_PASSWORD=""
cat >"$WRAPPER_SCRIPT"
SUDO_PASSWORD="$OPENAMP_REMOTE_SUDO_PASSWORD" bash "$WRAPPER_SCRIPT"
""".strip()


def decode_completed_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def main() -> int:
    args = normalize_args(parse_args())
    raw_event = sys.stdin.read()
    event = read_event(raw_event)
    phase = detect_phase(event)
    job_id = detect_job_id(event)
    hook_event_b64 = base64.b64encode(raw_event.encode("utf-8")).decode("ascii")
    remote_command = build_remote_command(args, phase=phase, job_id=job_id, hook_event_b64=hook_event_b64)
    remote_input = f"{args.password}\n{remote_command}\n".encode("utf-8")
    command = [
        resolve_bash_executable(),
        str(SSH_HELPER),
        "--host",
        args.host,
        "--user",
        args.user,
        "--pass",
        args.password,
        "--port",
        args.port,
        "--",
        "bash",
        "-lc",
        build_remote_stdin_wrapper_command(),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        input=remote_input,
        capture_output=True,
        check=False,
    )
    result_stdout = decode_completed_output(result.stdout)
    result_stderr = decode_completed_output(result.stderr)
    stdout, suppressed_tail = suppress_synthetic_sudo_failure_tail(result_stdout)
    if stdout:
        sys.stdout.write(stdout)
    if result_stderr:
        sys.stderr.write(result_stderr)
    if result.returncode == 0 or suppressed_tail:
        return 0
    if stdout.strip():
        return result.returncode
    sys.stdout.write(
        json.dumps(
            {
                "phase": phase,
                "source": "openamp_demo_remote_hook_proxy",
                "transport_status": "ssh_bridge_launch_failed",
                "protocol_semantics": "not_verified",
                "note": f"远端 bridge 启动失败，rc={result.returncode}。",
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
