from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from board_access import BoardAccessConfig  # noqa: E402
from fault_injector import query_live_status, run_fault_action, run_recover_action  # noqa: E402


def make_access() -> BoardAccessConfig:
    return BoardAccessConfig(
        host="demo-board",
        user="demo-user",
        password="demo-pass",
        port="22",
        env_file=None,
        env_values={},
        source_summary="unit test",
    )


def status_response(*, guard: str, last_fault: str, active_job_id: int = 0, total_fault_count: int = 0) -> str:
    return json.dumps(
        {
            "phase": "STATUS_REQ",
            "source": "firmware_status_resp",
            "transport_status": "status_resp_received",
            "protocol_semantics": "implemented",
            "note": "Received a decodable STATUS_RESP frame.",
            "rx_frame": {
                "status_resp": {
                    "guard_state_name": guard,
                    "active_job_id": active_job_id,
                    "last_fault_name": last_fault,
                    "heartbeat_ok": 0,
                    "sticky_fault": 0,
                    "total_fault_count": total_fault_count,
                }
            },
        },
        ensure_ascii=False,
    )


def job_ack_response(*, decision: str, fault_name: str, guard: str = "READY") -> str:
    return json.dumps(
        {
            "phase": "JOB_REQ",
            "decision": decision,
            "fault_code": 0 if fault_name == "NONE" else 1,
            "fault_name": fault_name,
            "guard_state": 1,
            "guard_state_name": guard,
            "source": "firmware_job_ack",
            "transport_status": "job_ack_received",
            "protocol_semantics": "implemented",
            "note": "Received a decodable JOB_ACK frame from firmware.",
        },
        ensure_ascii=False,
    )


def heartbeat_ack_response(*, guard: str = "JOB_ACTIVE", heartbeat_ok: int = 1) -> str:
    transport_status = "heartbeat_ack_received" if heartbeat_ok == 1 else "heartbeat_ack_received_negative"
    return json.dumps(
        {
            "phase": "HEARTBEAT",
            "acknowledged": heartbeat_ok == 1,
            "heartbeat_ok": heartbeat_ok,
            "guard_state": 2,
            "guard_state_name": guard,
            "source": "firmware_heartbeat_ack",
            "transport_status": transport_status,
            "protocol_semantics": "implemented",
            "note": "Received a decodable HEARTBEAT_ACK frame from firmware.",
        },
        ensure_ascii=False,
    )


def safe_stop_response(*, last_fault: str, transport_status: str = "safe_stop_status_received") -> str:
    return json.dumps(
        {
            "phase": "SAFE_STOP",
            "acknowledged": transport_status == "safe_stop_status_received",
            "guard_state": 1,
            "guard_state_name": "READY",
            "active_job_id": 0,
            "last_fault_code": 10 if last_fault == "MANUAL_SAFE_STOP" else 3,
            "last_fault_name": last_fault,
            "heartbeat_ok": 0,
            "sticky_fault": 0,
            "total_fault_count": 1,
            "source": "firmware_safe_stop_status",
            "transport_status": transport_status,
            "protocol_semantics": "implemented",
            "note": "Received STATUS_RESP after SAFE_STOP.",
        },
        ensure_ascii=False,
    )


class RunFaultActionTest(unittest.TestCase):
    def test_auth_failure_maps_to_operator_message_with_diagnostics(self) -> None:
        access = make_access()
        completed = subprocess.CompletedProcess(
            ["python3", "openamp_remote_hook_proxy.py"],
            255,
            stdout="",
            stderr="Permission denied (publickey,password).\n",
        )

        with patch("fault_injector.subprocess.run", return_value=completed):
            payload = run_fault_action(access, fault_type="wrong_sha", trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "parse_error")
        self.assertEqual(payload["status_category"], "auth_error")
        self.assertIn("认证失败", payload["message"])
        self.assertNotIn("Permission denied", payload["message"])
        self.assertEqual(
            payload["diagnostics"],
            {
                "stderr": "Permission denied (publickey,password).",
                "error": "remote fault action produced no JSON payload",
                "returncode": 255,
                "phases": [{"phase": "STATUS_REQ", "status": "parse_error", "returncode": 255}],
            },
        )

    def test_socket_block_maps_to_host_env_error_with_honest_message(self) -> None:
        access = make_access()
        completed = subprocess.CompletedProcess(
            ["python3", "openamp_remote_hook_proxy.py"],
            255,
            stdout="",
            stderr="socket: Operation not permitted\nssh: connect to host demo-board port 22: failure\n",
        )

        with patch("fault_injector.subprocess.run", return_value=completed):
            payload = run_fault_action(access, fault_type="wrong_sha", trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "parse_error")
        self.assertEqual(payload["status_category"], "host_env_error")
        self.assertIn("当前主机环境禁止建立 SSH socket", payload["message"])
        self.assertNotIn("passwordless sudo", payload["message"])
        self.assertEqual(
            payload["diagnostics"],
            {
                "stderr": "socket: Operation not permitted\nssh: connect to host demo-board port 22: failure",
                "error": "remote fault action produced no JSON payload",
                "returncode": 255,
                "phases": [{"phase": "STATUS_REQ", "status": "parse_error", "returncode": 255}],
            },
        )

    def test_query_live_status_reuses_proxy_bridge_and_extracts_status_fields(self) -> None:
        access = make_access()
        completed = subprocess.CompletedProcess(
            ["python3", "openamp_remote_hook_proxy.py"],
            0,
            stdout=status_response(guard="READY", last_fault="NONE") + "\n",
            stderr="",
        )

        with patch("fault_injector.subprocess.run", return_value=completed):
            payload = query_live_status(access, trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["guard_state"], "READY")
        self.assertEqual(payload["last_fault_code"], "NONE")
        self.assertEqual(payload["active_job_id"], 0)
        self.assertEqual(payload["total_fault_count"], 0)

    def test_fault_action_treats_bridge_launch_failure_as_error_even_with_json_stdout(self) -> None:
        access = make_access()
        completed = subprocess.CompletedProcess(
            ["python3", "openamp_remote_hook_proxy.py"],
            255,
            stdout=(
                json.dumps(
                    {
                        "phase": "STATUS_REQ",
                        "source": "openamp_demo_remote_hook_proxy",
                        "transport_status": "ssh_bridge_launch_failed",
                        "protocol_semantics": "not_verified",
                        "note": "远端 bridge 启动失败，rc=255。",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ),
            stderr="socket: Operation not permitted\nssh: connect to host demo-board port 22: failure\n",
        )

        with patch("fault_injector.subprocess.run", return_value=completed):
            payload = run_fault_action(access, fault_type="wrong_sha", trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["status_category"], "host_env_error")
        self.assertEqual(payload["execution_mode"], "error")
        self.assertIn("当前主机环境禁止建立 SSH socket", payload["message"])
        self.assertEqual(payload["diagnostics"]["phases"][0]["transport_status"], "ssh_bridge_launch_failed")

    def test_wrong_sha_fault_requires_expected_job_ack_and_post_status(self) -> None:
        access = make_access()
        completed = [
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="NONE") + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                2,
                stdout=job_ack_response(decision="DENY", fault_name="ARTIFACT_SHA_MISMATCH") + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="ARTIFACT_SHA_MISMATCH", total_fault_count=1) + "\n",
                stderr="",
            ),
        ]

        with patch("fault_injector.subprocess.run", side_effect=completed):
            payload = run_fault_action(
                access,
                fault_type="wrong_sha",
                trusted_sha="6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
                timeout_sec=8.0,
            )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["board_response"]["decision"], "DENY")
        self.assertEqual(payload["board_response"]["fault_code"], "ARTIFACT_SHA_MISMATCH")
        self.assertEqual(payload["guard_state"], "READY")
        self.assertEqual(payload["last_fault_code"], "ARTIFACT_SHA_MISMATCH")
        self.assertEqual(payload["total_fault_count"], 1)

    def test_heartbeat_timeout_requires_watchdog_status_and_cleanup_confirmation(self) -> None:
        access = make_access()
        completed = [
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="NONE") + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=job_ack_response(decision="ALLOW", fault_name="NONE", guard="JOB_ACTIVE") + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=heartbeat_ack_response() + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="HEARTBEAT_TIMEOUT", total_fault_count=1) + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=safe_stop_response(last_fault="MANUAL_SAFE_STOP") + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="MANUAL_SAFE_STOP", total_fault_count=1) + "\n",
                stderr="",
            ),
        ]

        with (
            patch("fault_injector.subprocess.run", side_effect=completed),
            patch("fault_injector.time.sleep", return_value=None),
        ):
            payload = run_fault_action(
                access,
                fault_type="heartbeat_timeout",
                trusted_sha="6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
                timeout_sec=12.0,
            )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["board_response"]["decision"], "ALLOW")
        self.assertEqual(payload["last_fault_code"], "HEARTBEAT_TIMEOUT")
        self.assertEqual(payload["cleanup_last_fault_code"], "MANUAL_SAFE_STOP")

    def test_recover_accepts_ready_status_even_when_fault_code_is_retained(self) -> None:
        access = make_access()
        completed = [
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(
                    guard="JOB_ACTIVE",
                    last_fault="HEARTBEAT_TIMEOUT",
                    active_job_id=4200192063,
                    total_fault_count=1,
                )
                + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                2,
                stdout=safe_stop_response(
                    last_fault="HEARTBEAT_TIMEOUT",
                    transport_status="safe_stop_status_received_not_applied",
                )
                + "\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["python3", "openamp_remote_hook_proxy.py"],
                0,
                stdout=status_response(guard="READY", last_fault="HEARTBEAT_TIMEOUT", total_fault_count=1) + "\n",
                stderr="",
            ),
        ]

        with patch("fault_injector.subprocess.run", side_effect=completed):
            payload = run_recover_action(
                access,
                trusted_sha="6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
                timeout_sec=8.0,
            )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["guard_state"], "READY")
        self.assertEqual(payload["last_fault_code"], "HEARTBEAT_TIMEOUT")
        self.assertEqual(payload["board_response"]["decision"], "ACK")

    def test_recover_targets_active_job_id_from_status_before_safe_stop(self) -> None:
        access = make_access()
        observed: list[dict[str, object]] = []

        def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
            event = json.loads(kwargs["input"])
            observed.append(event)
            phase = event["phase"]
            if phase == "STATUS_REQ" and len(observed) == 1:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=status_response(
                        guard="JOB_ACTIVE",
                        last_fault="NONE",
                        active_job_id=4200192063,
                        total_fault_count=0,
                    )
                    + "\n",
                    stderr="",
                )
            if phase == "SAFE_STOP":
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=safe_stop_response(last_fault="MANUAL_SAFE_STOP") + "\n",
                    stderr="",
                )
            if phase == "STATUS_REQ" and len(observed) == 3:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=status_response(
                        guard="READY",
                        last_fault="MANUAL_SAFE_STOP",
                        active_job_id=0,
                        total_fault_count=1,
                    )
                    + "\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected phase order: {phase}, observed={observed!r}")

        with patch("fault_injector.subprocess.run", side_effect=fake_run):
            payload = run_recover_action(access, trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "success")
        self.assertEqual([event["phase"] for event in observed], ["STATUS_REQ", "SAFE_STOP", "STATUS_REQ"])
        self.assertEqual(observed[1]["payload"]["job_id"], 4200192063)

    def test_recover_treats_bridge_launch_failure_as_error_even_with_json_stdout(self) -> None:
        access = make_access()
        completed = subprocess.CompletedProcess(
            ["python3", "openamp_remote_hook_proxy.py"],
            255,
            stdout=(
                json.dumps(
                    {
                        "phase": "SAFE_STOP",
                        "source": "openamp_demo_remote_hook_proxy",
                        "transport_status": "ssh_bridge_launch_failed",
                        "protocol_semantics": "not_verified",
                        "note": "远端 bridge 启动失败，rc=255。",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ),
            stderr="socket: Operation not permitted\nssh: connect to host demo-board port 22: failure\n",
        )

        with patch("fault_injector.subprocess.run", return_value=completed):
            payload = run_recover_action(access, trusted_sha="a" * 64, timeout_sec=8.0)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["status_category"], "host_env_error")
        self.assertEqual(payload["execution_mode"], "error")
        self.assertIn("当前主机环境禁止建立 SSH socket", payload["message"])
        self.assertEqual(payload["diagnostics"]["phases"][0]["transport_status"], "ssh_bridge_launch_failed")


if __name__ == "__main__":
    unittest.main()
