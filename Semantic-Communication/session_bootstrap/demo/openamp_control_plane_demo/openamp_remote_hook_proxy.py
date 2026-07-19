#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
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


def build_remote_command(
    args: argparse.Namespace,
    *,
    phase: str,
    job_id: int,
    hook_event_b64: str = "",
) -> str:
    remote_output_dir = f"{args.remote_output_root.rstrip('/')}/{job_id or 'adhoc'}/{phase.lower()}"
    remote_project_root = str(args.remote_project_root or "").strip()
    # Keep the validated bundle fallback, but prefer the existing remote project copy when available
    # to avoid re-extracting the bridge runtime on every heartbeat.
    bridge_bundle = build_bridge_bundle_base64()
    bridge_cache_key = hashlib.sha256(base64.b64decode(bridge_bundle)).hexdigest()[:20]
    return f"""
set -euo pipefail
PHASE={shlex.quote(phase)}
OUTPUT_DIR={shlex.quote(remote_output_dir)}
REMOTE_PROJECT_ROOT={shlex.quote(remote_project_root)}
BRIDGE_CACHE_ROOT=/tmp/openamp_demo_bridge_cache.$(id -u)/{bridge_cache_key}
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
  if [[ ! -f "$BRIDGE_CACHE_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py" ]] || [[ ! -f "$BRIDGE_CACHE_ROOT/openamp_mock/protocol.py" ]]; then
    rm -rf "$BRIDGE_CACHE_ROOT"
    mkdir -p "$BRIDGE_CACHE_ROOT"
    BRIDGE_CACHE_ROOT="$BRIDGE_CACHE_ROOT" PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import base64
import gzip
import io
import os
from pathlib import Path
import tarfile

stage_root = Path(os.environ["BRIDGE_CACHE_ROOT"])
stage_root.mkdir(parents=True, exist_ok=True)
bundle = base64.b64decode({bridge_bundle!r})
with gzip.GzipFile(fileobj=io.BytesIO(bundle), mode="rb") as gzip_file:
    with tarfile.open(fileobj=gzip_file, mode="r:") as archive:
        archive.extractall(stage_root)
PY
  fi
  REMOTE_BRIDGE_SCRIPT="$BRIDGE_CACHE_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py"
  REMOTE_BRIDGE_PYTHONPATH="$BRIDGE_CACHE_ROOT"
fi
BRIDGE_SCRIPT="$REMOTE_BRIDGE_SCRIPT"
BRIDGE_PYTHONPATH="$REMOTE_BRIDGE_PYTHONPATH"
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


SEQUENCE_START_PREFIX = "__OPENAMP_SEQUENCE_START__"
SEQUENCE_END_PREFIX = "__OPENAMP_SEQUENCE_END__"


def sequence_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = event.get("events")
    if not isinstance(raw_events, list):
        return []
    events: list[dict[str, Any]] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        raw_event = item.get("event") if isinstance(item.get("event"), dict) else item
        phase = detect_phase(raw_event)
        payload = raw_event.get("payload") if isinstance(raw_event.get("payload"), dict) else {}
        try:
            delay_before_sec = max(0.0, min(float(item.get("delay_before_sec", 0.0) or 0.0), 30.0))
        except (TypeError, ValueError):
            delay_before_sec = 0.0
        events.append(
            {
                "phase": phase,
                "payload": payload,
                "delay_before_sec": delay_before_sec,
            }
        )
    return events


def build_remote_sequence_command(args: argparse.Namespace, events: list[dict[str, Any]]) -> str:
    bridge_events: list[dict[str, Any]] = []
    for event in events:
        phase = detect_phase(event)
        job_id = detect_job_id(event)
        bridge_events.append(
            {
                "phase": phase,
                "payload": event.get("payload", {}),
                "delay_before_sec": float(event.get("delay_before_sec", 0.0) or 0.0),
                "output_dir": f"{args.remote_output_root.rstrip('/')}/{job_id or 'adhoc'}/{phase.lower()}",
            }
        )
    raw_event = json.dumps({"events": bridge_events}, ensure_ascii=False, separators=(",", ":"))
    hook_event_b64 = base64.b64encode(raw_event.encode("utf-8")).decode("ascii")
    return build_remote_command(
        args,
        phase="SEQUENCE",
        job_id=detect_job_id(events[0]) if events else 0,
        hook_event_b64=hook_event_b64,
    )


def parse_sequence_output(raw: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: dict[int, dict[str, Any]] = {}
    current_index: int | None = None
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if line.startswith(f"{SEQUENCE_START_PREFIX}:"):
            parts = line.split(":", 2)
            try:
                current_index = int(parts[1])
            except (IndexError, ValueError):
                current_index = None
                continue
            segments[current_index] = {"lines": [], "returncode": None}
            continue
        if line.startswith(f"{SEQUENCE_END_PREFIX}:"):
            parts = line.split(":", 3)
            try:
                index = int(parts[1])
                returncode = int(parts[3])
            except (IndexError, ValueError):
                current_index = None
                continue
            segments.setdefault(index, {"lines": [], "returncode": None})["returncode"] = returncode
            current_index = None
            continue
        if current_index is not None:
            segments[current_index]["lines"].append(raw_line)

    results: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        segment = segments.get(index, {"lines": [], "returncode": None})
        segment_stdout = "\n".join(segment["lines"]).strip()
        parsed = parse_json_dict_lines(segment_stdout)
        response: dict[str, Any] = {}
        for _line_index, candidate in reversed(parsed):
            if not is_synthetic_sudo_failure(candidate):
                response = candidate
                break
        if not response and parsed:
            response = parsed[-1][1]
        results.append(
            {
                "phase": detect_phase(event),
                "response": response,
                "stdout": segment_stdout,
                "returncode": segment.get("returncode"),
            }
        )
    return results


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


def resolve_docker_exec_container() -> str:
    runner = str(os.environ.get("OPENAMP_SSH_RUNNER") or "").strip().lower()
    if runner != "docker":
        return ""
    tx_port = str(os.environ.get("TX_CONTROL_PORT") or os.environ.get("USRP_TX_CONTROL_PORT") or "29221").strip()
    container = str(os.environ.get("OPENAMP_SSH_DOCKER_CONTAINER") or f"cockpit-usrp-tx-{tx_port}").strip()
    if not container:
        return ""
    try:
        probe = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return container if probe.returncode == 0 and probe.stdout.strip() == "true" else ""


def build_docker_exec_command(args: argparse.Namespace, container: str) -> list[str]:
    ssh_options = [
        "-p",
        args.port,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "BatchMode=no",
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "ControlMaster=auto",
        "-o",
        "ControlPersist=60",
        "-o",
        "ControlPath=/tmp/ssh_mux/%C",
    ]
    remote_command = shlex.join(["bash", "-lc", build_remote_stdin_wrapper_command()])
    return [
        "docker",
        "exec",
        "-i",
        "-e",
        "SSHPASS",
        container,
        "sh",
        "-c",
        'mkdir -p /tmp/ssh_mux && chmod 700 /tmp/ssh_mux && exec sshpass -e ssh "$@"',
        "sh",
        *ssh_options,
        f"{args.user}@{args.host}",
        remote_command,
    ]


def main() -> int:
    args = normalize_args(parse_args())
    raw_event = sys.stdin.read()
    event = read_event(raw_event)
    events = sequence_events(event)
    if events:
        phase = detect_phase(events[0])
        remote_command = build_remote_sequence_command(args, events)
    else:
        phase = detect_phase(event)
        job_id = detect_job_id(event)
        hook_event_b64 = base64.b64encode(raw_event.encode("utf-8")).decode("ascii")
        remote_command = build_remote_command(args, phase=phase, job_id=job_id, hook_event_b64=hook_event_b64)
    remote_input = f"{args.password}\n{remote_command}\n".encode("utf-8")
    docker_container = resolve_docker_exec_container()
    if docker_container:
        command = build_docker_exec_command(args, docker_container)
    else:
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
    command_env = os.environ.copy()
    if docker_container:
        command_env["SSHPASS"] = args.password
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=command_env,
        input=remote_input,
        capture_output=True,
        check=False,
    )
    result_stdout = decode_completed_output(result.stdout)
    result_stderr = decode_completed_output(result.stderr)
    if events:
        sys.stdout.write(
            json.dumps(
                {
                    "proxy_sequence": True,
                    "results": parse_sequence_output(result_stdout, events),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        if result_stderr:
            sys.stderr.write(result_stderr)
        return result.returncode
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
