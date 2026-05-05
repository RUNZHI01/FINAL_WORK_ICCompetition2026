#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import textwrap
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SSH_HELPER = PROJECT_ROOT / "session_bootstrap/scripts/ssh_with_password.sh"
FIT_TEMPLATE = PROJECT_ROOT / "session_bootstrap/templates/openamp_fit_report_template.md"
COVERAGE_TEMPLATE = PROJECT_ROOT / "session_bootstrap/templates/openamp_coverage_matrix_template.md"

FIT_ID = "FIT-01"
TC_ID = "TC-003"
SCENARIO = "wrong expected_sha256 JOB_REQ on real board path"
RISK_ITEM = "unknown artifact execution risk"
TRUSTED_CURRENT_SHA = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
DEFAULT_WRONG_SHA = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0"
DEFAULT_REMOTE_ENV_FILE = (
    PROJECT_ROOT / "session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
)
DEFAULT_REMOTE_PROJECT_ROOT = "/home/user/tvm_metaschedule_execution_project"
DEFAULT_REMOTE_OUTPUT_ROOT = "/tmp/openamp_wrong_sha_fit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the OpenAMP FIT-01 wrong-SHA board probe when SSH is available, "
            "or emit a structured blocked bundle when the board cannot be reached."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Bundle output directory. Defaults to session_bootstrap/reports/openamp_wrong_sha_fit_<timestamp>.",
    )
    parser.add_argument("--job-id", type=int, default=9301, help="JOB_REQ job_id used for FIT-01.")
    parser.add_argument(
        "--trusted-current-sha",
        default=TRUSTED_CURRENT_SHA,
        help="Trusted current SHA recorded by the firmware.",
    )
    parser.add_argument(
        "--wrong-sha",
        default=DEFAULT_WRONG_SHA,
        help="Mutated expected_sha256 used to trigger FIT-01.",
    )
    parser.add_argument(
        "--remote-env-file",
        default=str(DEFAULT_REMOTE_ENV_FILE),
        help="Env file that provides REMOTE_HOST/REMOTE_USER/REMOTE_PASS/REMOTE_SSH_PORT.",
    )
    parser.add_argument(
        "--remote-project-root",
        default=DEFAULT_REMOTE_PROJECT_ROOT,
        help="Remote repo root used when the board run is executed over SSH.",
    )
    parser.add_argument(
        "--remote-output-root",
        default=DEFAULT_REMOTE_OUTPUT_ROOT,
        help="Remote temp root for the board-side evidence bundle.",
    )
    parser.add_argument(
        "--rpmsg-ctrl",
        default="/dev/rpmsg_ctrl0",
        help="RPMsg control node passed to the bridge on the board.",
    )
    parser.add_argument(
        "--rpmsg-dev",
        default="/dev/rpmsg0",
        help="RPMsg endpoint passed to the bridge on the board.",
    )
    parser.add_argument(
        "--ssh-timeout-sec",
        type=float,
        default=20.0,
        help="Timeout for each SSH call.",
    )
    parser.add_argument(
        "--response-timeout-sec",
        type=float,
        default=2.0,
        help="Bridge response timeout in seconds.",
    )
    parser.add_argument(
        "--settle-timeout-sec",
        type=float,
        default=0.05,
        help="Bridge settle timeout in seconds.",
    )
    parser.add_argument(
        "--max-rx-bytes",
        type=int,
        default=4096,
        help="Maximum receive bytes retained by the bridge.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def resolve_output_dir(raw: str) -> Path:
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path
    path = PROJECT_ROOT / "session_bootstrap/reports" / f"openamp_wrong_sha_fit_{now_stamp()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def load_remote_login(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        raise SystemExit(f"ERROR: remote env file not found: {env_file}")
    command = [
        "bash",
        "-lc",
        textwrap.dedent(
            """
            set -euo pipefail
            set -a
            source "$1"
            set +a
            printf '%s\n' "${PHYTIUM_PI_HOST:-${REMOTE_HOST:-}}"
            printf '%s\n' "${PHYTIUM_PI_USER:-${REMOTE_USER:-}}"
            printf '%s\n' "${PHYTIUM_PI_PASSWORD:-${REMOTE_PASS:-}}"
            printf '%s\n' "${PHYTIUM_PI_PORT:-${REMOTE_SSH_PORT:-22}}"
            """
        ),
        "--",
        str(env_file),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    values = result.stdout.splitlines()
    if len(values) < 4:
        raise SystemExit(f"ERROR: failed to parse remote login values from {env_file}")
    host, user, password, port = values[:4]
    if not host or not user:
        raise SystemExit(f"ERROR: remote env file {env_file} did not yield host/user.")
    return {
        "host": host,
        "user": user,
        "password": password,
        "port": port or "22",
        "env_file": str(env_file),
    }


def redact_ssh_command(login: dict[str, str], remote_cmd: str) -> str:
    return shlex.join(
        [
            "bash",
            str(SSH_HELPER),
            "--host",
            login["host"],
            "--user",
            login["user"],
            "--pass",
            "***",
            "--port",
            login["port"],
            "--",
            remote_cmd,
        ]
    )


def run_ssh(
    *,
    login: dict[str, str],
    remote_cmd: str,
    timeout_sec: float,
    text_mode: bool = True,
) -> subprocess.CompletedProcess[Any]:
    command = [
        "bash",
        str(SSH_HELPER),
        "--host",
        login["host"],
        "--user",
        login["user"],
        "--pass",
        login["password"],
        "--port",
        login["port"],
        "--",
        remote_cmd,
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=text_mode,
        check=False,
        timeout=timeout_sec,
    )


def build_remote_paths(args: argparse.Namespace, output_dir: Path) -> dict[str, str]:
    run_id = output_dir.name
    remote_output_dir = f"{args.remote_output_root.rstrip('/')}/{run_id}"
    return {
        "run_id": run_id,
        "remote_output_dir": remote_output_dir,
        "remote_wrapper_runner_path": f"{remote_output_dir}/wrapper/runner_should_not_run.txt",
    }


def build_remote_commands(args: argparse.Namespace, remote_paths: dict[str, str]) -> dict[str, str]:
    remote_output_dir = remote_paths["remote_output_dir"]
    runner_cmd = f"touch {shlex.quote(remote_paths['remote_wrapper_runner_path'])}"
    pre_status_cmd = " ".join(
        [
            "python3",
            "./session_bootstrap/scripts/openamp_rpmsg_bridge.py",
            "--phase",
            "STATUS_REQ",
            "--job-id",
            str(args.job_id),
            "--rpmsg-ctrl",
            shlex.quote(args.rpmsg_ctrl),
            "--rpmsg-dev",
            shlex.quote(args.rpmsg_dev),
            "--output-dir",
            shlex.quote(f"{remote_output_dir}/pre_status"),
            "--response-timeout-sec",
            str(args.response_timeout_sec),
            "--settle-timeout-sec",
            str(args.settle_timeout_sec),
            "--max-rx-bytes",
            str(args.max_rx_bytes),
        ]
    )
    hook_cmd = (
        "python3 ./session_bootstrap/scripts/openamp_wrong_sha_fit_hook.py "
        f"--output-root {shlex.quote(f'{remote_output_dir}/hook')} "
        f"--rpmsg-ctrl {shlex.quote(args.rpmsg_ctrl)} "
        f"--rpmsg-dev {shlex.quote(args.rpmsg_dev)} "
        f"--response-timeout-sec {args.response_timeout_sec} "
        f"--settle-timeout-sec {args.settle_timeout_sec} "
        f"--max-rx-bytes {args.max_rx_bytes}"
    )
    wrapper_cmd = " ".join(
        [
            "python3",
            "./session_bootstrap/scripts/openamp_control_wrapper.py",
            "--job-id",
            str(args.job_id),
            "--variant",
            "wrong_sha_fit",
            "--runner-cmd",
            shlex.quote(runner_cmd),
            "--expected-sha256",
            args.wrong_sha,
            "--deadline-ms",
            "60000",
            "--expected-outputs",
            "1",
            "--job-flags",
            "smoke",
            "--output-dir",
            shlex.quote(f"{remote_output_dir}/wrapper"),
            "--transport",
            "hook",
            "--control-hook-cmd",
            shlex.quote(hook_cmd),
        ]
    )
    post_status_cmd = " ".join(
        [
            "python3",
            "./session_bootstrap/scripts/openamp_rpmsg_bridge.py",
            "--phase",
            "STATUS_REQ",
            "--job-id",
            str(args.job_id),
            "--seq",
            "2",
            "--rpmsg-ctrl",
            shlex.quote(args.rpmsg_ctrl),
            "--rpmsg-dev",
            shlex.quote(args.rpmsg_dev),
            "--output-dir",
            shlex.quote(f"{remote_output_dir}/post_status"),
            "--response-timeout-sec",
            str(args.response_timeout_sec),
            "--settle-timeout-sec",
            str(args.settle_timeout_sec),
            "--max-rx-bytes",
            str(args.max_rx_bytes),
        ]
    )
    combined = textwrap.dedent(
        f"""
        set -euo pipefail
        cd {shlex.quote(args.remote_project_root)}
        OUT={shlex.quote(remote_output_dir)}
        mkdir -p "$OUT"
        {pre_status_cmd}
        WRAPPER_RC=0
        {wrapper_cmd} || WRAPPER_RC=$?
        mkdir -p "$OUT/wrapper"
        printf '%s\\n' "$WRAPPER_RC" > "$OUT/wrapper/wrapper_exit_code.txt"
        {post_status_cmd}
        """
    ).strip()
    return {
        "pre_status": pre_status_cmd,
        "hook": hook_cmd,
        "runner": runner_cmd,
        "wrapper": wrapper_cmd,
        "post_status": post_status_cmd,
        "combined": combined,
    }


def write_planned_board_commands(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    remote_commands: dict[str, str],
    remote_paths: dict[str, str],
    login: dict[str, str],
) -> Path:
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        # Prepared on {now_iso()} from {PROJECT_ROOT}
        export REMOTE_HOST={shlex.quote(login['host'])}
        export REMOTE_USER={shlex.quote(login['user'])}
        export REMOTE_PORT={shlex.quote(login['port'])}
        export REMOTE_PROJECT_ROOT={shlex.quote(args.remote_project_root)}
        export REMOTE_OUTPUT_DIR={shlex.quote(remote_paths['remote_output_dir'])}
        export JOB_ID={args.job_id}
        export TRUSTED_SHA={args.trusted_current_sha}
        export WRONG_SHA={args.wrong_sha}

        cd "$REMOTE_PROJECT_ROOT"
        OUT="$REMOTE_OUTPUT_DIR"

        {remote_commands['pre_status']}
        {remote_commands['wrapper']}
        {remote_commands['post_status']}
        """
    )
    path = output_dir / "planned_board_commands.sh"
    write_text(path, script)
    path.chmod(0o755)
    return path


def build_run_manifest(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    remote_paths: dict[str, str],
    remote_commands: dict[str, str],
    login: dict[str, str],
) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "fit_id": FIT_ID,
        "tc_id": TC_ID,
        "run_id": output_dir.name,
        "scenario": SCENARIO,
        "risk_item": RISK_ITEM,
        "job_id": args.job_id,
        "trusted_current_sha": args.trusted_current_sha,
        "wrong_sha": args.wrong_sha,
        "expected_firmware_outcome": {
            "decision": "DENY",
            "fault_code": 1,
            "fault_name": "ARTIFACT_SHA_MISMATCH",
            "guard_state": "READY",
        },
        "expected_wrapper_outcome": {
            "result": "denied_by_control_hook",
            "runner_exit_code": None,
            "runner_should_not_run_path": remote_paths["remote_wrapper_runner_path"],
        },
        "board_access": {
            "mode": "ssh",
            "host": login["host"],
            "user": login["user"],
            "port": login["port"],
            "env_file": login["env_file"],
            "remote_project_root": args.remote_project_root,
            "remote_output_dir": remote_paths["remote_output_dir"],
        },
        "local_output_dir": str(output_dir),
        "planned_remote_commands": {
            "pre_status": remote_commands["pre_status"],
            "wrapper": remote_commands["wrapper"],
            "post_status": remote_commands["post_status"],
            "ssh_combined_redacted": redact_ssh_command(login, remote_commands["combined"]),
        },
        "boundary_note": (
            "FIT-01 only mutates JOB_REQ.expected_sha256; it does not alter the firmware baseline. "
            "If SSH is unavailable, the bundle must remain explicitly blocked rather than simulating board success."
        ),
    }


def write_probe_artifacts(
    *,
    output_dir: Path,
    login: dict[str, str],
    probe_result: subprocess.CompletedProcess[str],
    probe_command: str,
) -> dict[str, Any]:
    probe_dir = output_dir / "ssh_probe"
    stdout_path = probe_dir / "stdout.log"
    stderr_path = probe_dir / "stderr.log"
    command_path = probe_dir / "command.txt"
    write_text(stdout_path, probe_result.stdout or "")
    write_text(stderr_path, probe_result.stderr or "")
    write_text(command_path, probe_command + "\n")
    payload = {
        "captured_at": now_iso(),
        "host": login["host"],
        "user": login["user"],
        "port": login["port"],
        "probe_command_redacted": probe_command,
        "returncode": probe_result.returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "reachable": probe_result.returncode == 0,
        "stderr_excerpt": (probe_result.stderr or "").strip(),
    }
    write_json(probe_dir / "connect_probe.json", payload)
    return payload


def write_status_snapshot(
    *,
    output_dir: Path,
    phase_name: str,
    summary: dict[str, Any] | None,
    planned_command: str,
    blocked_reason: str | None = None,
) -> Path:
    status_dir = output_dir / phase_name
    snapshot_path = status_dir / "status_snapshot.json"
    if summary is None:
        snapshot = {
            "captured_at": now_iso(),
            "phase": phase_name,
            "status": "blocked_not_run",
            "expected_transport_status": "status_resp_received",
            "expected_guard_state": "READY",
            "expected_active_job_id": 0,
            "planned_remote_command": planned_command,
            "blocked_reason": blocked_reason,
        }
    else:
        status_payload = {}
        rx_frame = summary.get("rx_frame")
        if isinstance(rx_frame, dict) and isinstance(rx_frame.get("status_resp"), dict):
            status_payload = rx_frame["status_resp"]
        snapshot = {
            "captured_at": now_iso(),
            "phase": phase_name,
            "status": "captured",
            "transport_status": summary.get("transport_status"),
            "protocol_semantics": summary.get("protocol_semantics"),
            "source": summary.get("source"),
            "guard_state": status_payload.get("guard_state"),
            "guard_state_name": status_payload.get("guard_state_name"),
            "active_job_id": status_payload.get("active_job_id"),
            "last_fault_code": status_payload.get("last_fault_code"),
            "last_fault_name": status_payload.get("last_fault_name"),
            "heartbeat_ok": status_payload.get("heartbeat_ok"),
            "sticky_fault": status_payload.get("sticky_fault"),
            "total_fault_count": status_payload.get("total_fault_count"),
            "bridge_summary_path": str(status_dir / "bridge_summary.json"),
        }
    write_json(snapshot_path, snapshot)
    return snapshot_path


def build_wrapper_manifest(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    remote_paths: dict[str, str],
    remote_commands: dict[str, str],
    state: str,
) -> dict[str, Any]:
    wrapper_dir = output_dir / "wrapper"
    manifest = {
        "created_at": now_iso(),
        "fit_id": FIT_ID,
        "scenario": SCENARIO,
        "job_id": args.job_id,
        "variant": "wrong_sha_fit",
        "job_flags": "smoke",
        "runner_cmd": remote_commands["runner"],
        "runner_cmd_shell_quoted": shlex.join(["bash", "-lc", remote_commands["runner"]]),
        "expected_sha256": args.wrong_sha,
        "expected_outputs": 1,
        "deadline_ms": 60000,
        "heartbeat_interval_sec": 5.0,
        "runner_timeout_sec": 0.0,
        "transport": "hook",
        "control_hook_cmd": remote_commands["hook"],
        "dry_run": False,
        "output_dir": str(wrapper_dir),
        "trusted_current_sha": args.trusted_current_sha,
        "execution_state": state,
        "boundary_note": "Prepared for firmware-backed wrong-SHA admission denial evidence.",
    }
    return manifest


def build_blocked_trace(
    *,
    args: argparse.Namespace,
    remote_commands: dict[str, str],
    probe_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    blocker = probe_payload["stderr_excerpt"] or "ssh connect failed before board execution"
    return [
        {
            "at": now_iso(),
            "phase": "SSH_CONNECT_PROBE",
            "payload": {
                "host": probe_payload["host"],
                "user": probe_payload["user"],
                "port": probe_payload["port"],
            },
            "result": {
                "reachable": probe_payload["reachable"],
                "returncode": probe_payload["returncode"],
                "stderr_excerpt": blocker,
            },
        },
        {
            "at": now_iso(),
            "phase": "STATUS_REQ",
            "payload": {"job_id": args.job_id, "expected_baseline": "READY/active_job_id=0"},
            "result": {
                "status": "not_sent",
                "blocked_by": "ssh_connect_failed",
                "planned_remote_command": remote_commands["pre_status"],
            },
        },
        {
            "at": now_iso(),
            "phase": "JOB_REQ",
            "payload": {
                "job_id": args.job_id,
                "expected_sha256": args.wrong_sha,
                "deadline_ms": 60000,
                "expected_outputs": 1,
                "job_flags": "smoke",
            },
            "result": {
                "status": "not_sent",
                "blocked_by": "ssh_connect_failed",
                "planned_remote_command": remote_commands["wrapper"],
            },
        },
        {
            "at": now_iso(),
            "phase": "FIT_RUN_BLOCKED",
            "payload": {
                "fit_id": FIT_ID,
                "tc_id": TC_ID,
                "expected_decision": "DENY",
                "expected_fault_code": 1,
            },
            "result": {
                "status": "blocked_before_board_execution",
                "blocker": blocker,
            },
        },
    ]


def build_blocked_wrapper_summary(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    probe_payload: dict[str, Any],
) -> dict[str, Any]:
    blocker = probe_payload["stderr_excerpt"] or "ssh connect failed before board execution"
    wrapper_dir = output_dir / "wrapper"
    return {
        "finished_at": now_iso(),
        "job_id": args.job_id,
        "result": "blocked_remote_access",
        "status_response": {
            "source": "local_execution_guard",
            "transport_status": "not_attempted",
            "protocol_semantics": "not_attempted",
            "note": "pre STATUS_REQ was not sent because SSH could not reach the board.",
        },
        "job_req_response": {
            "source": "local_execution_guard",
            "transport_status": "not_attempted",
            "protocol_semantics": "not_attempted",
            "note": blocker,
        },
        "runner_exit_code": None,
        "runner_log": str(wrapper_dir / "runner.log"),
        "manifest_path": str(wrapper_dir / "job_manifest.json"),
        "control_trace_path": str(wrapper_dir / "control_trace.jsonl"),
        "blocker": {
            "kind": "ssh_connect_failed",
            "host": probe_payload["host"],
            "port": probe_payload["port"],
            "returncode": probe_payload["returncode"],
            "stderr_excerpt": blocker,
            "ssh_probe": str(output_dir / "ssh_probe" / "connect_probe.json"),
        },
    }


def extract_remote_bundle(
    *,
    output_dir: Path,
    login: dict[str, str],
    remote_output_dir: str,
    timeout_sec: float,
) -> dict[str, Any]:
    remote_cmd = f"tar -C {shlex.quote(remote_output_dir)} -czf - ."
    fetch_result = run_ssh(
        login=login,
        remote_cmd=remote_cmd,
        timeout_sec=timeout_sec,
        text_mode=False,
    )
    remote_tar_path = output_dir / "remote_bundle.tar.gz"
    if fetch_result.stdout:
        remote_tar_path.write_bytes(fetch_result.stdout)
    fetch_payload = {
        "captured_at": now_iso(),
        "remote_output_dir": remote_output_dir,
        "returncode": fetch_result.returncode,
        "stdout_tar_path": str(remote_tar_path) if fetch_result.stdout else None,
        "stderr": fetch_result.stderr.decode("utf-8", errors="replace") if fetch_result.stderr else "",
    }
    write_json(output_dir / "fetch_remote_bundle.json", fetch_payload)
    if fetch_result.returncode != 0:
        return fetch_payload
    with tarfile.open(fileobj=io.BytesIO(fetch_result.stdout), mode="r:gz") as archive:
        archive.extractall(output_dir)
    return fetch_payload


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def normalize_actual_outcome(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    remote_commands: dict[str, str],
    probe_payload: dict[str, Any],
) -> dict[str, Any]:
    pre_summary = load_json_if_exists(output_dir / "pre_status" / "bridge_summary.json")
    post_summary = load_json_if_exists(output_dir / "post_status" / "bridge_summary.json")
    hook_summary = load_json_if_exists(output_dir / "hook" / "job_req" / "bridge_summary.json")
    wrapper_summary = load_json_if_exists(output_dir / "wrapper" / "wrapper_summary.json")

    write_status_snapshot(
        output_dir=output_dir,
        phase_name="pre_status",
        summary=pre_summary,
        planned_command=remote_commands["pre_status"],
        blocked_reason=None,
    )
    write_status_snapshot(
        output_dir=output_dir,
        phase_name="post_status",
        summary=post_summary,
        planned_command=remote_commands["post_status"],
        blocked_reason=None,
    )

    if not wrapper_summary:
        wrapper_summary = build_blocked_wrapper_summary(
            output_dir=output_dir,
            args=args,
            probe_payload=probe_payload,
        )
        write_json(output_dir / "wrapper" / "wrapper_summary.json", wrapper_summary)

    fit_status = "FAIL"
    decision = None
    last_fault = None
    guard_final = None
    wrapper_result = wrapper_summary.get("result")
    runner_started = not (output_dir / "wrapper" / "runner_should_not_run.txt").exists()

    if hook_summary:
        decision = hook_summary.get("decision")
        last_fault = hook_summary.get("fault_name") or hook_summary.get("fault_code")
    if post_summary:
        post_snapshot = load_json_if_exists(output_dir / "post_status" / "status_snapshot.json") or {}
        guard_final = post_snapshot.get("guard_state_name") or post_snapshot.get("guard_state")
        last_fault = post_snapshot.get("last_fault_name") or post_snapshot.get("last_fault_code") or last_fault

    if (
        hook_summary
        and pre_summary
        and post_summary
        and wrapper_result == "denied_by_control_hook"
        and decision == "DENY"
        and (hook_summary.get("fault_code") == 1 or hook_summary.get("fault_name") == "ARTIFACT_SHA_MISMATCH")
    ):
        fit_status = "PASS"

    if not runner_started:
        fit_status = "FAIL"

    return {
        "status": fit_status,
        "decision": decision,
        "last_fault": last_fault,
        "guard_final": guard_final,
        "wrapper_result": wrapper_result,
        "pre_summary": pre_summary,
        "post_summary": post_summary,
        "hook_summary": hook_summary,
        "wrapper_summary": wrapper_summary,
    }


def write_fit_summary(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    login: dict[str, str],
    probe_payload: dict[str, Any],
    actual_outcome: dict[str, Any],
) -> dict[str, Any]:
    blocked = actual_outcome["status"] == "BLOCKED"
    fit_summary = {
        "generated_at": now_iso(),
        "fit_id": FIT_ID,
        "tc_id": TC_ID,
        "run_id": output_dir.name,
        "scenario": SCENARIO,
        "risk_item": RISK_ITEM,
        "status": actual_outcome["status"],
        "trusted_current_sha": args.trusted_current_sha,
        "wrong_sha": args.wrong_sha,
        "board_access": {
            "mode": "ssh",
            "host": login["host"],
            "port": login["port"],
            "reachable": probe_payload["reachable"],
            "ssh_probe": str(output_dir / "ssh_probe" / "connect_probe.json"),
            "blocker": probe_payload["stderr_excerpt"] if blocked else None,
        },
        "expected_result": {
            "decision": "DENY",
            "fault_code": 1,
            "fault_name": "ARTIFACT_SHA_MISMATCH",
            "guard_state": "READY",
            "runner_should_not_start": True,
        },
        "observed_result": {
            "decision": actual_outcome.get("decision"),
            "last_fault": actual_outcome.get("last_fault"),
            "guard_final": actual_outcome.get("guard_final"),
            "wrapper_result": actual_outcome.get("wrapper_result"),
        },
        "evidence_bundle": {
            "run_manifest": str(output_dir / "run_manifest.json"),
            "pre_status_snapshot": str(output_dir / "pre_status" / "status_snapshot.json"),
            "wrapper_manifest": str(output_dir / "wrapper" / "job_manifest.json"),
            "wrapper_trace": str(output_dir / "wrapper" / "control_trace.jsonl"),
            "wrapper_summary": str(output_dir / "wrapper" / "wrapper_summary.json"),
            "post_status_snapshot": str(output_dir / "post_status" / "status_snapshot.json"),
            "fit_report": str(output_dir / f"fit_report_{FIT_ID}.md"),
            "coverage_matrix": str(output_dir / "coverage_matrix.md"),
        },
    }
    write_json(output_dir / "fit_summary.json", fit_summary)
    return fit_summary


def write_fit_report(
    *,
    output_dir: Path,
    actual_outcome: dict[str, Any],
) -> Path:
    if actual_outcome["status"] == "BLOCKED":
        actual_result = "blocked_before_board_execution due to ssh connect failure; no STATUS_REQ or JOB_REQ reached the board."
    elif actual_outcome["status"] == "PASS":
        actual_result = (
            f"decision={actual_outcome.get('decision')}, wrapper={actual_outcome.get('wrapper_result')}, "
            f"guard_final={actual_outcome.get('guard_final')}, last_fault={actual_outcome.get('last_fault')}"
        )
    else:
        actual_result = (
            f"decision={actual_outcome.get('decision')}, wrapper={actual_outcome.get('wrapper_result')}, "
            f"guard_final={actual_outcome.get('guard_final')}, last_fault={actual_outcome.get('last_fault')}"
        )
    evidence_bundle = ", ".join(
        [
            "run_manifest.json",
            "ssh_probe/connect_probe.json",
            "pre_status/status_snapshot.json",
            "wrapper/job_manifest.json",
            "wrapper/control_trace.jsonl",
            "wrapper/wrapper_summary.json",
            "post_status/status_snapshot.json",
        ]
    )
    report = render_template(
        read_template(FIT_TEMPLATE),
        {
            "generated_at": now_iso(),
            "fit_id": FIT_ID,
            "run_id": output_dir.name,
            "scenario": SCENARIO,
            "tc_id": TC_ID,
            "injected_fault": "Mutate JOB_REQ.expected_sha256 to a valid but untrusted SHA-256 value.",
            "risk_item": RISK_ITEM,
            "expected_result": "Receive JOB_ACK(DENY, F001), keep guard in READY, and do not start the runner.",
            "actual_result": actual_result,
            "evidence_bundle": evidence_bundle,
        },
    )
    path = output_dir / f"fit_report_{FIT_ID}.md"
    write_text(path, report)
    return path


def write_coverage_matrix(*, output_dir: Path, actual_outcome: dict[str, Any], args: argparse.Namespace) -> Path:
    if actual_outcome["status"] == "PASS":
        row_fit1 = (
            f"| {TC_ID} | wrong expected_sha256 real-board denial | PASS | {actual_outcome.get('decision') or 'DENY'} "
            f"| {actual_outcome.get('wrapper_result') or 'denied_by_control_hook'} | "
            f"{actual_outcome.get('guard_final') or 'READY'} | {actual_outcome.get('last_fault') or 'ARTIFACT_SHA_MISMATCH'} | "
            f"`fit_report_{FIT_ID}.md` |"
        )
        covered_items = TC_ID
    elif actual_outcome["status"] == "BLOCKED":
        row_fit1 = (
            f"| {TC_ID} | wrong expected_sha256 real-board denial | BLOCKED | N/A | BLOCKED_REMOTE_ACCESS | N/A | N/A | "
            f"`fit_report_{FIT_ID}.md` |"
        )
        covered_items = "None; FIT-01 blocked before board execution."
    else:
        row_fit1 = (
            f"| {TC_ID} | wrong expected_sha256 real-board denial | FAIL | {actual_outcome.get('decision') or 'N/A'} | "
            f"{actual_outcome.get('wrapper_result') or 'N/A'} | {actual_outcome.get('guard_final') or 'N/A'} | "
            f"{actual_outcome.get('last_fault') or 'N/A'} | `fit_report_{FIT_ID}.md` |"
        )
        covered_items = "None; FIT-01 did not meet the acceptance criteria."
    coverage_rows = "\n".join(
        [
            row_fit1,
            "| TC-004 | invalid input contract real-board denial | TODO | N/A | N/A | N/A | N/A | pending |",
            "| TC-006 | heartbeat timeout real-board watchdog | TODO | N/A | N/A | N/A | N/A | pending |",
        ]
    )
    remaining_items = (
        "FIT-01 needs a real-board rerun when SSH works; FIT-02 and FIT-03 can reuse the same bundle layout."
    )
    coverage = render_template(
        read_template(COVERAGE_TEMPLATE),
        {
            "generated_at": now_iso(),
            "run_id": output_dir.name,
            "trusted_current_sha": args.trusted_current_sha,
            "coverage_rows": coverage_rows,
            "covered_items": covered_items,
            "remaining_items": remaining_items,
        },
    )
    path = output_dir / "coverage_matrix.md"
    write_text(path, coverage)
    return path


def write_blocked_report(*, output_dir: Path, probe_payload: dict[str, Any]) -> Path:
    text = "\n".join(
        [
            "# OpenAMP FIT-01 blocked report",
            "",
            f"- generated_at: `{now_iso()}`",
            "- status: `BLOCKED`",
            "- blocker_kind: `ssh_connect_failed`",
            f"- host: `{probe_payload['host']}:{probe_payload['port']}`",
            "",
            "## Exact blocker",
            "",
            "```text",
            probe_payload["stderr_excerpt"],
            "```",
            "",
            "## Meaning",
            "",
            "The run stopped before any board-side `STATUS_REQ` or `JOB_REQ` was sent. This is a workspace network restriction, not a firmware decision.",
            "",
            "## Next step",
            "",
            "Re-run `session_bootstrap/scripts/run_openamp_fit_wrong_sha.py` from an execution context that can open outbound SSH sockets to the Phytium Pi.",
            "",
        ]
    )
    path = output_dir / "blocked_report.md"
    write_text(path, text)
    return path


def main() -> int:
    args = parse_args()
    output_dir = resolve_output_dir(args.output_dir)
    remote_env_file = Path(args.remote_env_file)
    if not remote_env_file.is_absolute():
        remote_env_file = PROJECT_ROOT / remote_env_file
    login = load_remote_login(remote_env_file)
    remote_paths = build_remote_paths(args, output_dir)
    remote_commands = build_remote_commands(args, remote_paths)
    planned_path = write_planned_board_commands(
        output_dir=output_dir,
        args=args,
        remote_commands=remote_commands,
        remote_paths=remote_paths,
        login=login,
    )
    run_manifest = build_run_manifest(
        output_dir=output_dir,
        args=args,
        remote_paths=remote_paths,
        remote_commands=remote_commands,
        login=login,
    )
    run_manifest["planned_board_commands"] = str(planned_path)
    write_json(output_dir / "run_manifest.json", run_manifest)

    probe_remote_cmd = "hostname && whoami && uname -a"
    probe_command_redacted = redact_ssh_command(login, probe_remote_cmd)
    probe_result = run_ssh(
        login=login,
        remote_cmd=probe_remote_cmd,
        timeout_sec=args.ssh_timeout_sec,
        text_mode=True,
    )
    probe_payload = write_probe_artifacts(
        output_dir=output_dir,
        login=login,
        probe_result=probe_result,
        probe_command=probe_command_redacted,
    )

    wrapper_manifest = build_wrapper_manifest(
        output_dir=output_dir,
        args=args,
        remote_paths=remote_paths,
        remote_commands=remote_commands,
        state="blocked_before_remote_execution" if probe_result.returncode != 0 else "pending_remote_execution",
    )
    write_json(output_dir / "wrapper" / "job_manifest.json", wrapper_manifest)

    if probe_result.returncode != 0:
        blocked_trace = build_blocked_trace(
            args=args,
            remote_commands=remote_commands,
            probe_payload=probe_payload,
        )
        write_jsonl(output_dir / "wrapper" / "control_trace.jsonl", blocked_trace)
        wrapper_summary = build_blocked_wrapper_summary(
            output_dir=output_dir,
            args=args,
            probe_payload=probe_payload,
        )
        write_json(output_dir / "wrapper" / "wrapper_summary.json", wrapper_summary)
        write_status_snapshot(
            output_dir=output_dir,
            phase_name="pre_status",
            summary=None,
            planned_command=remote_commands["pre_status"],
            blocked_reason=probe_payload["stderr_excerpt"] or "ssh connect failed",
        )
        write_status_snapshot(
            output_dir=output_dir,
            phase_name="post_status",
            summary=None,
            planned_command=remote_commands["post_status"],
            blocked_reason=probe_payload["stderr_excerpt"] or "ssh connect failed",
        )
        actual_outcome = {
            "status": "BLOCKED",
            "decision": None,
            "last_fault": None,
            "guard_final": None,
            "wrapper_result": wrapper_summary["result"],
        }
        write_blocked_report(output_dir=output_dir, probe_payload=probe_payload)
    else:
        remote_exec = run_ssh(
            login=login,
            remote_cmd=remote_commands["combined"],
            timeout_sec=args.ssh_timeout_sec * 3,
            text_mode=True,
        )
        write_text(output_dir / "remote_execution_stdout.log", remote_exec.stdout or "")
        write_text(output_dir / "remote_execution_stderr.log", remote_exec.stderr or "")
        write_json(
            output_dir / "remote_execution.json",
            {
                "captured_at": now_iso(),
                "returncode": remote_exec.returncode,
                "command_redacted": redact_ssh_command(login, remote_commands["combined"]),
            },
        )
        extract_remote_bundle(
            output_dir=output_dir,
            login=login,
            remote_output_dir=remote_paths["remote_output_dir"],
            timeout_sec=args.ssh_timeout_sec,
        )
        actual_outcome = normalize_actual_outcome(
            output_dir=output_dir,
            args=args,
            remote_commands=remote_commands,
            probe_payload=probe_payload,
        )

    write_fit_report(output_dir=output_dir, actual_outcome=actual_outcome)
    write_coverage_matrix(output_dir=output_dir, actual_outcome=actual_outcome, args=args)
    write_fit_summary(
        output_dir=output_dir,
        args=args,
        login=login,
        probe_payload=probe_payload,
        actual_outcome=actual_outcome,
    )
    print(json.dumps({"output_dir": str(output_dir), "status": actual_outcome["status"]}, ensure_ascii=False))
    return 0 if actual_outcome["status"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
