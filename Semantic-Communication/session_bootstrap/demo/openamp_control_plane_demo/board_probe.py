from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from remote_failure import build_diagnostics, build_operator_message, classify_status_category


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_ROOT = PROJECT_ROOT / "session_bootstrap" / "reports"
CONNECT_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "connect_phytium_pi.sh"
SSH_WITH_PASSWORD_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "ssh_with_password.sh"
DEFAULT_LIVE_PROBE_OUTPUT = REPORTS_ROOT / "openamp_demo_live_probe_latest.json"

REMOTE_PROBE_CODE = r"""
import glob
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""

def sha256(path):
    if not os.path.exists(path):
        return ""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

remoteproc = []
for state_path in sorted(glob.glob("/sys/class/remoteproc/remoteproc*/state")):
    base = Path(state_path).parent
    remoteproc.append(
        {
            "name": base.name,
            "state": read_text(state_path),
            "firmware": read_text(base / "firmware"),
        }
    )

rpmsg_devices = sorted(glob.glob("/dev/rpmsg*"))
rpmsg_channels = []
for name_path in sorted(glob.glob("/sys/bus/rpmsg/devices/*/name")):
    name = read_text(name_path)
    if name:
        rpmsg_channels.append(name)

firmware_path = "/lib/firmware/openamp_core0.elf"
payload = {
    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "hostname": socket.gethostname(),
    "whoami": subprocess.check_output(["whoami"], text=True).strip(),
    "remoteproc": remoteproc,
    "rpmsg_devices": rpmsg_devices,
    "rpmsg_channels": sorted(set(rpmsg_channels)),
    "firmware": {
        "path": firmware_path,
        "exists": os.path.exists(firmware_path),
        "size": os.path.getsize(firmware_path) if os.path.exists(firmware_path) else 0,
        "sha256": sha256(firmware_path),
    },
}
print(json.dumps(payload, ensure_ascii=True))
"""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def is_successful_probe(payload: dict[str, Any] | None) -> bool:
    return bool(payload and payload.get("reachable") and payload.get("status") == "success")


def load_probe_output(output_path: str | Path) -> dict[str, Any] | None:
    path = resolve_project_path(output_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def parse_env_file(env_file: str | None) -> dict[str, str]:
    if not env_file:
        return {}
    path = Path(env_file)
    if not path.is_absolute():
        path = (PROJECT_ROOT / env_file).resolve()
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_probe_login(values: dict[str, str]) -> tuple[str, str, str, str]:
    host = values.get("REMOTE_HOST") or values.get("PHYTIUM_PI_HOST") or ""
    user = values.get("REMOTE_USER") or values.get("PHYTIUM_PI_USER") or ""
    password = values.get("REMOTE_PASS") or values.get("PHYTIUM_PI_PASSWORD") or ""
    port = values.get("REMOTE_SSH_PORT") or values.get("PHYTIUM_PI_PORT") or "22"
    return host, user, password, port


def build_probe_command(env_file: str | None = None, env_values: dict[str, str] | None = None) -> list[str]:
    remote_cmd = f"python3 -c {shlex.quote(REMOTE_PROBE_CODE)}"
    values = dict(env_values or {})
    if not values:
        values = parse_env_file(env_file)
    host, user, password, port = resolve_probe_login(values)
    if host and user and password:
        return [
            "bash",
            str(SSH_WITH_PASSWORD_SCRIPT),
            "--host",
            host,
            "--user",
            user,
            "--pass",
            password,
            "--port",
            port,
            "--",
            remote_cmd,
        ]

    command = ["bash", str(CONNECT_SCRIPT)]
    if env_file:
        command.extend(["--env", env_file])
    command.extend(["--", remote_cmd])
    return command


def parse_json_stdout(raw: str) -> dict[str, Any]:
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise ValueError("probe produced no JSON payload")


def summarize_probe(details: dict[str, Any]) -> str:
    remoteproc = details.get("remoteproc", [])
    states = ", ".join(
        f"{item.get('name', 'remoteproc')}={item.get('state', 'unknown')}" for item in remoteproc
    ) or "no remoteproc entries"
    rpmsg_count = len(details.get("rpmsg_devices", []))
    firmware_sha = details.get("firmware", {}).get("sha256", "")
    firmware_note = f"firmware {firmware_sha[:12]}" if firmware_sha else "firmware sha unavailable"
    return f"{details.get('hostname', 'board')} reachable; {states}; {rpmsg_count} rpmsg device(s); {firmware_note}."


def run_live_probe(
    env_file: str | None = None,
    timeout_sec: float = 30.0,
    env_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    requested_at = now_iso()
    try:
        if env_values is None:
            command = build_probe_command(env_file)
        else:
            command = build_probe_command(env_file, env_values=env_values)
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "requested_at": requested_at,
            "reachable": False,
            "status": "timeout",
            "status_category": "timeout",
            "summary": build_operator_message("probe", "timeout"),
            "error": build_operator_message("probe", "timeout"),
            "details": {},
            "diagnostics": {},
        }
    except OSError as exc:
        status_category = classify_status_category(status="launch_error", error=str(exc))
        return {
            "requested_at": requested_at,
            "reachable": False,
            "status": "launch_error",
            "status_category": status_category,
            "summary": build_operator_message("probe", status_category),
            "error": build_operator_message("probe", status_category),
            "details": {},
            "diagnostics": build_diagnostics(error=str(exc)),
        }

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        status_category = classify_status_category(status="error", stderr=stderr, stdout=stdout)
        return {
            "requested_at": requested_at,
            "reachable": False,
            "status": "error",
            "status_category": status_category,
            "summary": build_operator_message("probe", status_category),
            "error": build_operator_message("probe", status_category),
            "details": {},
            "diagnostics": build_diagnostics(stdout=stdout, stderr=stderr, returncode=result.returncode),
        }

    try:
        details = parse_json_stdout(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        status_category = classify_status_category(
            status="parse_error",
            stderr=stderr,
            stdout=stdout,
            error=str(exc),
        )
        return {
            "requested_at": requested_at,
            "reachable": False,
            "status": "parse_error",
            "status_category": status_category,
            "summary": build_operator_message("probe", status_category),
            "error": build_operator_message("probe", status_category),
            "details": {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
            "diagnostics": build_diagnostics(stdout=stdout, stderr=stderr, error=str(exc)),
        }

    return {
        "requested_at": requested_at,
        "reachable": True,
        "status": "success",
        "status_category": "success",
        "summary": summarize_probe(details),
        "error": "",
        "details": details,
        "diagnostics": {},
    }


def write_probe_output(payload: dict[str, Any], output_path: str | Path) -> None:
    path = resolve_project_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
