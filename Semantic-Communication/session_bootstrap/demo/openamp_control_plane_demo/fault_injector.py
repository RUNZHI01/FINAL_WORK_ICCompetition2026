from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any

from board_access import BoardAccessConfig
from remote_failure import build_diagnostics, build_operator_message, classify_status_category


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REMOTE_HOOK_PROXY_SCRIPT = Path(__file__).resolve().parent / "openamp_remote_hook_proxy.py"
DEFAULT_REMOTE_OUTPUT_ROOT = "/tmp/openamp_demo_fault"

FAULT_TYPE_TO_ACTION = {
    "wrong_sha": "wrong_sha",
    "illegal_param": "illegal_param",
    "heartbeat_timeout": "heartbeat_timeout",
    "recover": "recover",
    "status": "status",
}


def parse_json_stdout(raw: str) -> dict[str, Any]:
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            return payload
    raise ValueError("remote fault action produced no JSON payload")


def now_label() -> str:
    return time.strftime("%H:%M:%S")


def log(lines: list[str], text: str) -> None:
    lines.append(f"[{now_label()}] {text}")


def safe_nested(mapping: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = mapping or {}
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def int_or_default(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def response_error_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("phase", "source", "transport_status", "protocol_semantics", "note", "rpmsg_ctrl", "rpmsg_dev"):
        value = response.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def status_fields_from_response(response: dict[str, Any]) -> dict[str, Any]:
    status_resp = safe_nested(response, "rx_frame", "status_resp")
    if not isinstance(status_resp, dict):
        status_resp = response
    return {
        "guard_state": str(status_resp.get("guard_state_name") or status_resp.get("guard_state") or "UNKNOWN"),
        "active_job_id": int_or_default(status_resp.get("active_job_id"), 0),
        "last_fault_code": str(status_resp.get("last_fault_name") or status_resp.get("last_fault_code") or "UNKNOWN"),
        "heartbeat_ok": int_or_default(status_resp.get("heartbeat_ok"), 0),
        "sticky_fault": int_or_default(status_resp.get("sticky_fault"), 0),
        "total_fault_count": int_or_default(status_resp.get("total_fault_count"), 0),
    }


def build_proxy_command(access: BoardAccessConfig, remote_output_root: str) -> list[str]:
    values = access.build_env()
    command = [
        "python3",
        str(REMOTE_HOOK_PROXY_SCRIPT),
        "--host",
        access.host,
        "--user",
        access.user,
        "--password",
        access.password,
        "--port",
        access.port,
        "--remote-output-root",
        remote_output_root,
    ]
    remote_project_root = str(values.get("REMOTE_PROJECT_ROOT") or values.get("OPENAMP_REMOTE_PROJECT_ROOT") or "")
    remote_jscc_dir = str(values.get("REMOTE_JSCC_DIR") or "")
    if remote_project_root:
        command.extend(["--remote-project-root", remote_project_root])
    if remote_jscc_dir:
        command.extend(["--remote-jscc-dir", remote_jscc_dir])
    return command


def run_proxy_phase(
    access: BoardAccessConfig,
    *,
    phase: str,
    payload: dict[str, Any],
    timeout_sec: float,
    remote_output_root: str,
) -> dict[str, Any]:
    event = {"phase": phase, "payload": payload}
    command = build_proxy_command(access, remote_output_root)
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            input=json.dumps(event, ensure_ascii=False),
            capture_output=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "phase": phase,
            "payload": payload,
            "response": {},
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "error_text": "",
        }
    except OSError as exc:
        return {
            "status": "launch_error",
            "phase": phase,
            "payload": payload,
            "response": {},
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "error_text": str(exc),
        }

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    try:
        response = parse_json_stdout(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "parse_error",
            "phase": phase,
            "payload": payload,
            "response": {},
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "error_text": str(exc),
        }

    return {
        "status": "success",
        "phase": phase,
        "payload": payload,
        "response": response,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": result.returncode,
        "error_text": response_error_text(response),
    }


def collect_phase_diagnostics(phase_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for item in phase_results:
        response = item.get("response") if isinstance(item.get("response"), dict) else {}
        entry = {
            "phase": item.get("phase", ""),
            "status": item.get("status", ""),
        }
        if item.get("returncode") is not None:
            entry["returncode"] = item["returncode"]
        for key in ("source", "transport_status", "protocol_semantics", "note"):
            value = response.get(key)
            if value not in (None, ""):
                entry[key] = value
        diagnostics.append(entry)
    return diagnostics


def last_returncode(phase_results: list[dict[str, Any]]) -> int | None:
    for item in reversed(phase_results):
        value = item.get("returncode")
        if value is not None:
            return int(value)
    return None


def phase_failure_status(phase_result: dict[str, Any]) -> str:
    status = str(phase_result.get("status") or "error")
    return status if status != "success" else "error"


def build_action_failure(
    action: str,
    phase_results: list[dict[str, Any]],
    *,
    status: str,
    logs: list[str],
    note: str = "",
) -> dict[str, Any]:
    stdout = "\n".join(item.get("stdout", "") for item in phase_results if item.get("stdout"))
    stderr = "\n".join(item.get("stderr", "") for item in phase_results if item.get("stderr"))
    error_parts = [note] if note else []
    for item in phase_results:
        if item.get("status") != "success" and item.get("error_text"):
            error_parts.append(str(item["error_text"]))
            continue
        response = item.get("response") if isinstance(item.get("response"), dict) else {}
        text = response_error_text(response)
        if text:
            error_parts.append(text)
    error_text = "\n".join(part for part in error_parts if part)
    status_category = classify_status_category(status=status, stdout=stdout, stderr=stderr, error=error_text)
    diagnostics = build_diagnostics(
        stdout=stdout,
        stderr=stderr,
        error=error_text,
        returncode=last_returncode(phase_results),
    )
    phase_diagnostics = collect_phase_diagnostics(phase_results)
    if phase_diagnostics:
        diagnostics["phases"] = phase_diagnostics
    return {
        "status": status,
        "status_category": status_category,
        "action": action,
        "message": build_operator_message(action, status_category),
        "logs": logs,
        "diagnostics": diagnostics,
    }


def build_success_payload(
    action: str,
    *,
    logs: list[str],
    board_response: dict[str, Any],
    status_fields: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    payload = {
        "status": "success",
        "status_category": "success",
        "action": action,
        "message": message,
        "logs": logs,
        "diagnostics": {},
        "board_response": board_response,
    }
    payload.update(status_fields)
    return payload


def remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("deadline exhausted")
    return remaining


def wait_with_deadline(deadline: float, duration_sec: float) -> None:
    if duration_sec <= 0:
        return
    if remaining_timeout(deadline) < duration_sec:
        raise TimeoutError("deadline exhausted before wait_without_heartbeat_sec")
    time.sleep(duration_sec)


def make_status_payload(job_id: int, trusted_sha: str, job_flags: int) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "expected_sha256": trusted_sha,
        "job_flags": job_flags,
    }


def make_job_payload(
    *,
    job_id: int,
    expected_sha256: str,
    expected_outputs: int,
    deadline_ms: int,
    job_flags: int,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "expected_sha256": expected_sha256,
        "expected_outputs": expected_outputs,
        "deadline_ms": deadline_ms,
        "job_flags": job_flags,
    }


def make_heartbeat_payload(job_id: int, elapsed_ms: int) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "runtime_state": "RUNNING",
        "elapsed_ms": elapsed_ms,
        "completed_outputs": 0,
        "progress_x100": 100,
    }


def make_safe_stop_payload(job_id: int, reason: str) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "reason": reason,
    }


def status_phase_is_live(phase_result: dict[str, Any]) -> bool:
    response = phase_result.get("response") if isinstance(phase_result.get("response"), dict) else {}
    return (
        phase_result.get("status") == "success"
        and response.get("transport_status") == "status_resp_received"
        and response.get("protocol_semantics") == "implemented"
    )


def job_phase_matches(
    phase_result: dict[str, Any],
    *,
    decision: str,
    fault_name: str | None = None,
) -> bool:
    response = phase_result.get("response") if isinstance(phase_result.get("response"), dict) else {}
    if phase_result.get("status") != "success":
        return False
    if response.get("transport_status") != "job_ack_received" or response.get("protocol_semantics") != "implemented":
        return False
    if str(response.get("decision") or "").upper() != decision:
        return False
    if fault_name is not None and str(response.get("fault_name") or "").upper() != fault_name:
        return False
    return True


def heartbeat_phase_matches(phase_result: dict[str, Any]) -> bool:
    response = phase_result.get("response") if isinstance(phase_result.get("response"), dict) else {}
    return (
        phase_result.get("status") == "success"
        and response.get("transport_status") == "heartbeat_ack_received"
        and response.get("protocol_semantics") == "implemented"
        and bool(response.get("acknowledged"))
    )


def safe_stop_phase_is_live(phase_result: dict[str, Any]) -> bool:
    response = phase_result.get("response") if isinstance(phase_result.get("response"), dict) else {}
    fields = status_fields_from_response(response)
    return (
        phase_result.get("status") == "success"
        and str(response.get("transport_status") or "").startswith("safe_stop_status_received")
        and response.get("protocol_semantics") == "implemented"
        and fields["guard_state"] == "READY"
        and fields["active_job_id"] == 0
    )


def default_driver_config(action: str, trusted_sha: str) -> dict[str, Any]:
    return {
        "action": action,
        "job_id": int((time.time() * 1000) % 100000) + 9300,
        "trusted_sha": trusted_sha,
        "wrong_sha": f"{trusted_sha[:-1]}{'0' if trusted_sha[-1:] != '0' else '1'}" if trusted_sha else trusted_sha,
        "wait_without_heartbeat_sec": 5.0,
        "deadline_ms": 60000,
        "job_flags": 3,
    }


def query_live_status(access: BoardAccessConfig, *, trusted_sha: str, timeout_sec: float = 12.0) -> dict[str, Any]:
    config = default_driver_config("status", trusted_sha)
    deadline = time.monotonic() + timeout_sec
    logs: list[str] = []
    remote_output_root = f"{DEFAULT_REMOTE_OUTPUT_ROOT}/status"

    try:
        status_phase = run_proxy_phase(
            access,
            phase="STATUS_REQ",
            payload=make_status_payload(config["job_id"], trusted_sha, config["job_flags"]),
            timeout_sec=remaining_timeout(deadline),
            remote_output_root=remote_output_root,
        )
    except TimeoutError:
        status_phase = {"status": "timeout", "phase": "STATUS_REQ", "response": {}, "stdout": "", "stderr": "", "returncode": None}

    if not status_phase_is_live(status_phase):
        payload = build_action_failure("status", [status_phase], status=phase_failure_status(status_phase), logs=logs)
        payload["execution_mode"] = "error"
        return payload

    fields = status_fields_from_response(status_phase["response"])
    log(logs, f"▶ STATUS_REQ -> guard={fields['guard_state']} last_fault={fields['last_fault_code']}")
    payload = build_success_payload(
        "status",
        logs=logs,
        board_response={
            "decision": "STATUS_RESP",
            "fault_code": fields["last_fault_code"],
            "guard_state": fields["guard_state"],
        },
        status_fields=fields,
        message="已通过共享 RPMsg bridge 获取当前板端状态。",
    )
    payload["execution_mode"] = "live"
    return payload


def run_fault_action(
    access: BoardAccessConfig,
    *,
    fault_type: str,
    trusted_sha: str,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    action = FAULT_TYPE_TO_ACTION.get(fault_type, fault_type)
    config = default_driver_config(action, trusted_sha)
    deadline = time.monotonic() + timeout_sec
    logs: list[str] = []
    phase_results: list[dict[str, Any]] = []
    remote_output_root = f"{DEFAULT_REMOTE_OUTPUT_ROOT}/{action}"

    def run_phase(phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = run_proxy_phase(
            access,
            phase=phase,
            payload=payload,
            timeout_sec=remaining_timeout(deadline),
            remote_output_root=remote_output_root,
        )
        phase_results.append(result)
        return result

    try:
        pre_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
        if not status_phase_is_live(pre_status):
            payload = build_action_failure(action, phase_results, status=phase_failure_status(pre_status), logs=logs)
            payload["execution_mode"] = "error"
            return payload

        pre_fields = status_fields_from_response(pre_status["response"])
        log(logs, f"▶ STATUS_REQ: 初始 guard={pre_fields['guard_state']}")

        if action in {"wrong_sha", "illegal_param"}:
            expected_fault = "ARTIFACT_SHA_MISMATCH" if action == "wrong_sha" else "ILLEGAL_PARAM_RANGE"
            expected_outputs = 1 if action == "wrong_sha" else 2
            expected_sha = config["wrong_sha"] if action == "wrong_sha" else trusted_sha
            if action == "wrong_sha":
                log(logs, f"▶ 发送 JOB_REQ，expected_sha={expected_sha[:12]}...")
            else:
                log(logs, "▶ 发送 JOB_REQ，expected_outputs=2")

            job_phase = run_phase(
                "JOB_REQ",
                make_job_payload(
                    job_id=config["job_id"],
                    expected_sha256=expected_sha,
                    expected_outputs=expected_outputs,
                    deadline_ms=config["deadline_ms"],
                    job_flags=config["job_flags"],
                ),
            )
            job_response = job_phase.get("response") if isinstance(job_phase.get("response"), dict) else {}
            log(
                logs,
                f"◀ JOB_ACK: {job_response.get('decision', 'UNKNOWN')}，fault={job_response.get('fault_name', 'UNKNOWN')}",
            )
            if not job_phase_matches(job_phase, decision="DENY", fault_name=expected_fault):
                payload = build_action_failure(
                    action,
                    phase_results,
                    status="error",
                    logs=logs,
                    note=f"{action} live path did not return the expected JOB_ACK denial semantics.",
                )
                payload["execution_mode"] = "error"
                return payload

            post_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
            if not status_phase_is_live(post_status):
                payload = build_action_failure(action, phase_results, status=phase_failure_status(post_status), logs=logs)
                payload["execution_mode"] = "error"
                return payload

            post_fields = status_fields_from_response(post_status["response"])
            log(logs, f"◀ STATUS_RESP: guard={post_fields['guard_state']} last_fault={post_fields['last_fault_code']}")
            if post_fields["guard_state"] != "READY" or post_fields["last_fault_code"] != expected_fault:
                payload = build_action_failure(
                    action,
                    phase_results,
                    status="error",
                    logs=logs,
                    note=f"{action} live path did not land in the expected READY/{expected_fault} state.",
                )
                payload["execution_mode"] = "error"
                return payload

            payload = build_success_payload(
                action,
                logs=logs,
                board_response={
                    "decision": "DENY",
                    "fault_code": expected_fault,
                    "guard_state": post_fields["guard_state"],
                },
                status_fields=post_fields,
                message="已通过共享 RPMsg bridge 完成真机故障注入。",
            )
            payload["execution_mode"] = "live"
            return payload

        if action != "heartbeat_timeout":
            payload = build_action_failure(
                action,
                phase_results,
                status="error",
                logs=logs,
                note=f"unsupported action: {action}",
            )
            payload["execution_mode"] = "error"
            return payload

        job_phase = run_phase(
            "JOB_REQ",
            make_job_payload(
                job_id=config["job_id"],
                expected_sha256=trusted_sha,
                expected_outputs=1,
                deadline_ms=config["deadline_ms"],
                job_flags=config["job_flags"],
            ),
        )
        job_response = job_phase.get("response") if isinstance(job_phase.get("response"), dict) else {}
        log(logs, f"▶ JOB_REQ -> JOB_ACK({job_response.get('decision', 'UNKNOWN')})")
        if not job_phase_matches(job_phase, decision="ALLOW"):
            payload = build_action_failure(
                action,
                phase_results,
                status="error",
                logs=logs,
                note="heartbeat_timeout live path did not receive an ALLOW JOB_ACK.",
            )
            payload["execution_mode"] = "error"
            return payload

        heartbeat_phase = run_phase("HEARTBEAT", make_heartbeat_payload(config["job_id"], elapsed_ms=1234))
        heartbeat_response = heartbeat_phase.get("response") if isinstance(heartbeat_phase.get("response"), dict) else {}
        log(
            logs,
            "◀ HEARTBEAT_ACK: "
            f"guard={heartbeat_response.get('guard_state_name', 'UNKNOWN')} "
            f"ok={int_or_default(heartbeat_response.get('heartbeat_ok'), 0)}",
        )
        if not heartbeat_phase_matches(heartbeat_phase):
            payload = build_action_failure(
                action,
                phase_results,
                status="error",
                logs=logs,
                note="heartbeat_timeout live path did not receive a positive HEARTBEAT_ACK.",
            )
            payload["execution_mode"] = "error"
            return payload

        log(logs, f"⏳ 停发 heartbeat {config['wait_without_heartbeat_sec']:.1f} 秒，等待 FIT-03 watchdog 结果")
        wait_with_deadline(deadline, float(config["wait_without_heartbeat_sec"]))

        timeout_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
        if not status_phase_is_live(timeout_status):
            payload = build_action_failure(
                action,
                phase_results,
                status=phase_failure_status(timeout_status),
                logs=logs,
            )
            payload["execution_mode"] = "error"
            return payload

        timeout_fields = status_fields_from_response(timeout_status["response"])
        log(logs, f"◀ STATUS_RESP: guard={timeout_fields['guard_state']} last_fault={timeout_fields['last_fault_code']}")
        if timeout_fields["guard_state"] != "READY" or timeout_fields["last_fault_code"] != "HEARTBEAT_TIMEOUT":
            payload = build_action_failure(
                action,
                phase_results,
                status="error",
                logs=logs,
                note="heartbeat_timeout live path did not expose the expected READY/HEARTBEAT_TIMEOUT status.",
            )
            payload["execution_mode"] = "error"
            return payload

        cleanup_phase = run_phase("SAFE_STOP", make_safe_stop_payload(config["job_id"], "heartbeat_timeout_cleanup"))
        cleanup_fields = status_fields_from_response(cleanup_phase.get("response") if isinstance(cleanup_phase.get("response"), dict) else {})
        log(logs, f"▶ SAFE_STOP 清理，返回 guard={cleanup_fields['guard_state']}")
        if not safe_stop_phase_is_live(cleanup_phase):
            payload = build_action_failure(
                action,
                phase_results,
                status=phase_failure_status(cleanup_phase),
                logs=logs,
                note="heartbeat_timeout cleanup did not return an implemented READY safe-stop state.",
            )
            payload["execution_mode"] = "error"
            return payload

        final_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
        if not status_phase_is_live(final_status):
            payload = build_action_failure(
                action,
                phase_results,
                status=phase_failure_status(final_status),
                logs=logs,
            )
            payload["execution_mode"] = "error"
            return payload

        final_fields = status_fields_from_response(final_status["response"])
        log(logs, f"◀ 最终 STATUS_RESP: guard={final_fields['guard_state']} last_fault={final_fields['last_fault_code']}")
        if final_fields["guard_state"] != "READY" or final_fields["active_job_id"] != 0:
            payload = build_action_failure(
                action,
                phase_results,
                status="error",
                logs=logs,
                note="heartbeat_timeout cleanup did not leave the board in READY with active_job_id=0.",
            )
            payload["execution_mode"] = "error"
            return payload

        payload = build_success_payload(
            action,
            logs=logs,
            board_response={
                "decision": "ALLOW",
                "fault_code": timeout_fields["last_fault_code"],
                "guard_state": timeout_fields["guard_state"],
            },
            status_fields={
                **timeout_fields,
                "cleanup_last_fault_code": final_fields["last_fault_code"],
            },
            message="已通过共享 RPMsg bridge 完成心跳超时注入与清理确认。",
        )
        payload["execution_mode"] = "live"
        return payload
    except TimeoutError:
        payload = build_action_failure(action, phase_results, status="timeout", logs=logs)
        payload["execution_mode"] = "error"
        return payload


def run_recover_action(access: BoardAccessConfig, *, trusted_sha: str, timeout_sec: float = 12.0) -> dict[str, Any]:
    config = default_driver_config("recover", trusted_sha)
    deadline = time.monotonic() + timeout_sec
    logs: list[str] = []
    phase_results: list[dict[str, Any]] = []
    remote_output_root = f"{DEFAULT_REMOTE_OUTPUT_ROOT}/recover"

    def run_phase(phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = run_proxy_phase(
            access,
            phase=phase,
            payload=payload,
            timeout_sec=remaining_timeout(deadline),
            remote_output_root=remote_output_root,
        )
        phase_results.append(result)
        return result

    try:
        pre_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
        if not status_phase_is_live(pre_status):
            payload = build_action_failure(
                "recover",
                phase_results,
                status=phase_failure_status(pre_status),
                logs=logs,
            )
            payload["execution_mode"] = "error"
            return payload

        pre_fields = status_fields_from_response(pre_status["response"])
        log(logs, f"▶ STATUS_REQ: 初始 guard={pre_fields['guard_state']} active_job_id={pre_fields['active_job_id']}")
        target_job_id = config["job_id"]
        if pre_fields["guard_state"] == "JOB_ACTIVE" and pre_fields["active_job_id"] > 0:
            target_job_id = pre_fields["active_job_id"]

        cleanup_phase = run_phase("SAFE_STOP", make_safe_stop_payload(target_job_id, "manual_recover"))
        cleanup_fields = status_fields_from_response(cleanup_phase.get("response") if isinstance(cleanup_phase.get("response"), dict) else {})
        log(logs, f"▶ SAFE_STOP: guard={cleanup_fields['guard_state']} last_fault={cleanup_fields['last_fault_code']}")
        if not safe_stop_phase_is_live(cleanup_phase):
            payload = build_action_failure(
                "recover",
                phase_results,
                status=phase_failure_status(cleanup_phase),
                logs=logs,
                note="recover live path did not receive an implemented SAFE_STOP status response.",
            )
            payload["execution_mode"] = "error"
            return payload

        final_status = run_phase("STATUS_REQ", make_status_payload(config["job_id"], trusted_sha, config["job_flags"]))
        if not status_phase_is_live(final_status):
            payload = build_action_failure(
                "recover",
                phase_results,
                status=phase_failure_status(final_status),
                logs=logs,
            )
            payload["execution_mode"] = "error"
            return payload

        final_fields = status_fields_from_response(final_status["response"])
        log(logs, f"◀ STATUS_RESP: guard={final_fields['guard_state']} last_fault={final_fields['last_fault_code']}")
        if final_fields["guard_state"] != "READY" or final_fields["active_job_id"] != 0:
            payload = build_action_failure(
                "recover",
                phase_results,
                status="error",
                logs=logs,
                note="recover live path did not leave the board in READY with active_job_id=0.",
            )
            payload["execution_mode"] = "error"
            return payload

        payload = build_success_payload(
            "recover",
            logs=logs,
            board_response={
                "decision": "ACK",
                "fault_code": final_fields["last_fault_code"],
                "guard_state": final_fields["guard_state"],
            },
            status_fields=final_fields,
            message="已通过共享 RPMsg bridge 完成 SAFE_STOP 收口确认。",
        )
        payload["execution_mode"] = "live"
        return payload
    except TimeoutError:
        payload = build_action_failure("recover", phase_results, status="timeout", logs=logs)
        payload["execution_mode"] = "error"
        return payload
