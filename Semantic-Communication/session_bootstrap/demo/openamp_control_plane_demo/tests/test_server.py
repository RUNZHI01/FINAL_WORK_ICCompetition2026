from __future__ import annotations

from argparse import Namespace
import html
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote
import urllib.request


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

import server  # noqa: E402
from server import DashboardState, DemoRequestHandler  # noqa: E402
import usrp_runtime  # noqa: E402


REPO_ROOT = DEMO_ROOT.parents[2]


def test_transport_benchmark_exposes_iq_remote_pull_and_cleanup_metrics() -> None:
    benchmark = usrp_runtime._transport_benchmark_from_summary(
        {
            "pass_count": 1,
            "per_image_sec": 10.0,
            "payload_airtime_ms_mean": 100.0,
            "decode_total_wall_sec_mean": 2.0,
            "merge_wall_sec_mean": 0.3,
            "rx_pull_wall_sec_mean": 3.0,
            "remote_cleanup_wall_sec_mean": 0.7,
            "estimated_non_airtime_non_decode_non_merge_wall_sec_mean": 3.9,
        }
    )

    assert benchmark["rx_pull_ms"]["mean_ms"] == 3000.0
    assert benchmark["remote_cleanup_ms"]["mean_ms"] == 700.0
    assert benchmark["other_wall_ms"]["mean_ms"] == 3900.0


def test_transport_benchmark_prefers_iq_round_medians_over_outlier_means() -> None:
    benchmark = usrp_runtime._transport_benchmark_from_summary(
        {
            "pass_count": 3,
            "per_image_sec": 10.0,
            "payload_airtime_ms_mean": 9.58,
            "decode_total_wall_sec_mean": 5.0,
            "images": [
                {
                    "passed": True,
                    "round_records": [
                        {
                            "total_wall_sec": 0.20,
                            "detected_airtime_ms": 9.58,
                            "decode_wall_sec": 0.07,
                            "merge_wall_sec": 0.0,
                            "rx_pull_wall_sec": 0.0,
                            "remote_cleanup_wall_sec": 0.0,
                        }
                    ],
                },
                {
                    "passed": True,
                    "round_records": [
                        {
                            "total_wall_sec": 0.21,
                            "detected_airtime_ms": 9.58,
                            "decode_wall_sec": 0.08,
                            "merge_wall_sec": 0.0,
                            "rx_pull_wall_sec": 0.0,
                            "remote_cleanup_wall_sec": 0.0,
                        }
                    ],
                },
                {
                    "passed": True,
                    "round_records": [
                        {
                            "total_wall_sec": 7.0,
                            "detected_airtime_ms": 9.58,
                            "decode_wall_sec": 0.07,
                            "merge_wall_sec": 0.0,
                            "rx_pull_wall_sec": 0.0,
                            "remote_cleanup_wall_sec": 0.0,
                        }
                    ],
                },
            ],
        }
    )

    assert benchmark["total_ms"]["median_ms"] == 210.0
    assert benchmark["decode_ms"]["median_ms"] == 70.0
    assert benchmark["other_wall_ms"]["median_ms"] == 120.42
    assert benchmark["total_ms"]["mean_ms"] > benchmark["total_ms"]["median_ms"]


def test_crypto_status_exposes_iq_stage_benchmark_from_batch_state() -> None:
    state = DashboardState(None, 30.0, probe_cache_path=None)
    state._crypto_enabled = True
    state._crypto_status_cache = {
        "channel_state": "ready",
        "kem_backend": "mock-kem",
        "cipher_suite": "mock-cipher",
        "board_configured": True,
    }
    state._crypto_status_cache_ts = time.monotonic()
    state._batch_state = {
        "status": "done",
        "completed": 5,
        "total": 5,
        "iq_stage_benchmark": {
            "rx_arm_control_overhead_ms": {"n": 5, "median_ms": 21.0, "p95_ms": 45.0},
            "rx_wait_response_overhead_ms": {"n": 5, "median_ms": 1.4, "p95_ms": 126.0},
        },
    }

    status = state._get_crypto_status_core()

    assert status["batch_status"] == "done"
    assert status["batch_iq_stage_benchmark"]["rx_arm_control_overhead_ms"]["median_ms"] == 21.0
    assert status["batch_iq_stage_benchmark"]["rx_wait_response_overhead_ms"]["p95_ms"] == 126.0


def test_crypto_status_exposes_iq_tail_audit_from_batch_state() -> None:
    state = DashboardState(None, 30.0, probe_cache_path=None)
    state._crypto_enabled = True
    state._crypto_status_cache = {
        "channel_state": "ready",
        "kem_backend": "mock-kem",
        "cipher_suite": "mock-cipher",
        "board_configured": True,
    }
    state._crypto_status_cache_ts = time.monotonic()
    state._batch_state = {
        "status": "done",
        "completed": 5,
        "total": 5,
        "iq_tail_audit": {
            "record_count": 5,
            "over_reference_count": 2,
            "reference_ms": 244.45,
            "total_gt_250ms_count": 2,
            "rx_control_overhead_gt_50ms_count": 1,
        },
    }

    status = state._get_crypto_status_core()

    assert status["batch_iq_tail_audit"]["over_reference_count"] == 2
    assert status["batch_iq_tail_audit"]["rx_control_overhead_gt_50ms_count"] == 1


def test_clear_batch_state_only_clears_warmup_state() -> None:
    state = DashboardState(None, 30.0, probe_cache_path=None)
    state._batch_state = {
        "status": "done",
        "batch_job_id": "warmup-1",
        "warmup": True,
        "completed": 5,
        "total": 5,
    }

    cleared = state.clear_batch_state(warmup_only=True, batch_job_id="warmup-1")

    assert cleared["status"] == "ok"
    assert cleared["cleared"] is True
    assert state.get_batch_state() == {"status": "idle"}

    state._batch_state = {
        "status": "done",
        "batch_job_id": "batch-1",
        "completed": 300,
        "total": 300,
    }

    skipped = state.clear_batch_state(warmup_only=True)

    assert skipped["status"] == "ok"
    assert skipped["cleared"] is False
    assert state.get_batch_state()["batch_job_id"] == "batch-1"


def test_iq_tail_audit_from_summary_preserves_runner_counts() -> None:
    audit = usrp_runtime._iq_tail_audit_from_summary(
        {
            "iq_tail_audit": {
                "record_count": 300,
                "reference_ms": 244.45,
                "over_reference_count": 33,
                "total_gt_250ms_count": 30,
                "decode_gt_160ms_count": 17,
            }
        }
    )

    assert audit is not None
    assert audit["over_reference_count"] == 33
    assert audit["decode_gt_160ms_count"] == 17


def test_iq_stage_benchmark_exposes_control_decode_and_retry_metrics() -> None:
    benchmark = usrp_runtime._iq_stage_benchmark_from_summary(
        {
            "images": [
                {
                    "passed": True,
                    "round_records": [
                        {
                            "tx_wall_sec": 0.010,
                            "rx_arm_wall_sec": 0.003,
                            "rx_capture_wall_sec": 0.030,
                            "rx_wait_wall_sec": 0.017,
                            "decode_wall_sec": 0.060,
                            "remote_decode_reported_wall_sec": 0.041,
                            "remote_decode_restart_wall_sec": 0.0,
                            "remote_dir_publish_wall_sec": 0.004,
                            "retry_wait_wall_sec": 0.0,
                            "total_wall_sec": 0.120,
                        }
                    ],
                },
                {
                    "passed": True,
                    "round_records": [
                        {
                            "tx_wall_sec": 0.020,
                            "rx_arm_wall_sec": 0.004,
                            "rx_capture_wall_sec": 0.040,
                            "rx_wait_wall_sec": 0.026,
                            "decode_wall_sec": 0.070,
                            "remote_decode_reported_wall_sec": 0.042,
                            "remote_decode_restart_wall_sec": 0.030,
                            "remote_dir_publish_wall_sec": 0.005,
                            "retry_wait_wall_sec": 0.0,
                            "total_wall_sec": 0.140,
                        }
                    ],
                },
                {
                    "passed": True,
                    "round_records": [
                        {
                            "tx_wall_sec": 0.070,
                            "rx_arm_wall_sec": 0.009,
                            "rx_capture_wall_sec": 0.050,
                            "rx_wait_wall_sec": 0.031,
                            "decode_wall_sec": 0.080,
                            "remote_decode_reported_wall_sec": 0.043,
                            "remote_decode_restart_wall_sec": 0.0,
                            "remote_dir_publish_wall_sec": 0.006,
                            "retry_wait_wall_sec": 0.020,
                            "total_wall_sec": 0.240,
                        }
                    ],
                },
            ],
        }
    )

    assert benchmark is not None
    assert benchmark["tx_control_ms"]["median_ms"] == 20.0
    assert benchmark["tx_control_ms"]["p95_ms"] == 70.0
    assert benchmark["rx_arm_ms"]["median_ms"] == 4.0
    assert benchmark["rx_capture_ms"]["median_ms"] == 40.0
    assert benchmark["rx_wait_ms"]["median_ms"] == 26.0
    assert benchmark["remote_decode_ms"]["median_ms"] == 70.0
    assert benchmark["remote_decode_reported_ms"]["median_ms"] == 42.0
    assert benchmark["remote_decode_restart_ms"]["max_ms"] == 30.0
    assert benchmark["remote_dir_publish_ms"]["mean_ms"] == 5.0
    assert benchmark["retry_wait_ms"]["max_ms"] == 20.0
    assert benchmark["total_transport_ms"]["median_ms"] == 140.0


def test_usrp_remote_command_timeout_kills_windows_process_tree() -> None:
    access = usrp_runtime.BoardAccessConfig(
        host="demo-board",
        user="user",
        password="user",
        port="22",
        env_file=None,
        env_values={},
        source_summary="test",
    )

    class HangingPopen:
        pid = 12345
        returncode = None

        def __init__(self, command, **_kwargs):  # type: ignore[no-untyped-def]
            self.args = command

        def wait(self, timeout=None):  # type: ignore[no-untyped-def]
            raise subprocess.TimeoutExpired(self.args, timeout)

        def poll(self):  # type: ignore[no-untyped-def]
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    with (
        patch("usrp_runtime.os.name", "nt"),
        patch("usrp_runtime.resolve_bash_executable", return_value="bash"),
        patch("usrp_runtime.subprocess.Popen", side_effect=HangingPopen),
        patch("usrp_runtime.subprocess.run") as run_mock,
    ):
        result = usrp_runtime._run_remote_command(access, "sleep 999", timeout=1.0)

    assert result.returncode == 124
    assert b"TimeoutExpired: remote command timed out after 1.0s" in result.stderr
    run_mock.assert_called_once()
    assert run_mock.call_args.args[0][:4] == ["taskkill", "/F", "/T", "/PID"]
    assert run_mock.call_args.args[0][4] == "12345"


def test_usrp_remote_command_uses_paramiko_runner_from_board_access_env() -> None:
    access = usrp_runtime.BoardAccessConfig(
        host="demo-board",
        user="user",
        password="secret",
        port="2200",
        env_file=None,
        env_values={"OPENAMP_SSH_RUNNER": "paramiko"},
        source_summary="test",
    )
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeStdin:
        def __init__(self) -> None:
            self.data = b""
            self.closed = False

        def write(self, data: bytes) -> int:
            self.data += data
            return len(data)

        def close(self) -> None:
            self.closed = True

    class FakePopen:
        returncode = 0
        pid = 12345

        def __init__(self, command, **kwargs):  # type: ignore[no-untyped-def]
            self.args = list(command)
            self.stdin = FakeStdin() if kwargs.get("stdin") is subprocess.PIPE else None
            popen_calls.append((self.args, dict(kwargs)))

        def wait(self, timeout=None):  # type: ignore[no-untyped-def]
            return 0

    with (
        patch("usrp_runtime.PYTHON_SSH_HELPER", Path("ssh_with_password_paramiko.py")),
        patch("usrp_runtime.subprocess.Popen", side_effect=FakePopen),
    ):
        result = usrp_runtime._run_remote_command(access, "cat >/tmp/payload", timeout=9.0, input_data=b"payload")

    assert result.returncode == 0
    assert len(popen_calls) == 1
    cmd, kwargs = popen_calls[0]
    assert cmd[:3] == [sys.executable, "ssh_with_password_paramiko.py", "--host"]
    assert "--pass-env" in cmd
    assert kwargs["stdin"] is subprocess.PIPE
    env = kwargs["env"]
    assert isinstance(env, dict)
    assert env["OPENAMP_REMOTE_PASS"] == "secret"
    assert env["OPENAMP_SSH_TIMEOUT_SEC"] == "9.0"


def test_start_remote_rx_server_passes_arm_wait_ms(monkeypatch) -> None:
    access = usrp_runtime.BoardAccessConfig(
        host="demo-board",
        user="user",
        password="user",
        port="22",
        env_file=None,
        env_values={},
        source_summary="test",
    )
    commands: list[str] = []

    def fake_run_remote_command(_access, remote_command, *, timeout):  # type: ignore[no-untyped-def]
        commands.append(remote_command)
        return subprocess.CompletedProcess(args=remote_command, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(usrp_runtime, "_run_remote_command", fake_run_remote_command)

    result = usrp_runtime._start_remote_rx_server(
        access,
        {"RX_ARM_WAIT_MS": "50", "ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC": "8.0"},
        rx_port="29220",
        remote_run_root="/tmp/usrp292x_remote_runs",
        remote_project_root="/home/user",
    )

    assert result["status"] == "started"
    assert "ARM_WAIT_MS=50" in commands[0]
    assert "STOP_WAIT_MS=8000" in commands[0]


def live_probe_payload(requested_at: str, summary: str) -> dict[str, object]:
    return {
        "requested_at": requested_at,
        "reachable": True,
        "status": "success",
        "summary": summary,
        "error": "",
        "details": {
            "hostname": "phytium-demo",
            "remoteproc": [{"name": "remoteproc0", "state": "running"}],
            "firmware": {"sha256": "abcd" * 16},
        },
    }


def failed_probe_payload(requested_at: str, summary: str, error: str) -> dict[str, object]:
    return {
        "requested_at": requested_at,
        "reachable": False,
        "status": "error",
        "summary": summary,
        "error": error,
        "details": {},
    }


def live_progress_payload(label: str, state: str, percent: int, current_stage: str) -> dict[str, object]:
    expected_count = server.DEFAULT_MAX_INPUTS
    completed_count = max(0, round((percent / 100.0) * expected_count)) if state != "running" else percent
    return {
        "state": state,
        "label": label,
        "tone": "online" if label == "真实在线推进" else "degraded",
        "percent": percent,
        "phase_percent": 76 if state == "running" else 100,
        "completed_count": completed_count,
        "expected_count": expected_count,
        "remaining_count": expected_count - completed_count,
        "completion_ratio": completed_count / expected_count,
        "count_source": "runner_log.sample_latency_lines" if state == "running" else "runner_summary.processed_count",
        "count_label": f"{completed_count} / {expected_count}",
        "current_stage": current_stage,
        "stages": [
            {"key": "connected", "label": "已连接", "status": "done", "detail": "STATUS_RESP: READY / fault=NONE"},
            {"key": "dispatched", "label": "已下发", "status": "done", "detail": "已向 OpenAMP 控制面提交 JOB_REQ。"},
            {"key": "running", "label": "板端执行中", "status": "current" if state == "running" else "done", "detail": "JOB_ACK(ALLOW) / guard=JOB_ACTIVE"},
            {
                "key": "returned",
                "label": "已返回结果",
                "status": "pending" if state == "running" else ("done" if label == "真实在线推进" else "error"),
                "detail": "等待 JOB_DONE。" if state == "running" else "JOB_DONE 已回收，runner_exit=0 / result=0",
            },
        ],
        "event_log": [
            "[19:24:47] STATUS_REQ -> guard=READY / fault=NONE",
            "[19:24:48] JOB_REQ -> trusted_sha=1946b08e6cf2",
            "[19:24:48] JOB_ACK(ALLOW) -> guard=JOB_ACTIVE / fault=NONE",
        ],
    }


class FakeInferenceJob:
    def __init__(self, snapshots: list[dict[str, object]], *, job_id: str = "demo-job-001") -> None:
        self.job_id = job_id
        self._snapshots = [json.loads(json.dumps(item)) for item in snapshots]
        self._calls = 0

    def snapshot(self) -> dict[str, object]:
        index = min(self._calls, len(self._snapshots) - 1)
        self._calls += 1
        return json.loads(json.dumps(self._snapshots[index]))


class FakeTextStream:
    def __init__(self, lines: list[str] | None = None, *, read_text: str = "") -> None:
        self._lines = list(lines or [])
        self._read_text = read_text

    def __iter__(self):
        return iter(self._lines)

    def read(self) -> str:
        return self._read_text


class FakePopen:
    def __init__(self, stdout_lines: list[str] | None = None, *, stderr_text: str = "", returncode: int = 0) -> None:
        self.stdout = FakeTextStream(stdout_lines or [])
        self.stderr = FakeTextStream(read_text=stderr_text)
        self.returncode = returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


class KillableFakePopen(FakePopen):
    def __init__(self, stdout_lines: list[str] | None = None, *, stderr_text: str = "", returncode: int | None = None) -> None:
        super().__init__(stdout_lines=stdout_lines, stderr_text=stderr_text, returncode=returncode or 0)
        self.returncode = returncode
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = 124

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            time.sleep(0.01)
            return 124
        return self.returncode


class NonClosingBytesIO(io.BytesIO):
    def close(self) -> None:
        return


class FakeSocket:
    def __init__(self, request_bytes: bytes) -> None:
        self._rfile = io.BytesIO(request_bytes)
        self._wfile = NonClosingBytesIO()

    def makefile(self, mode: str, *args: object, **kwargs: object) -> io.BytesIO:
        if "r" in mode:
            return self._rfile
        if "w" in mode:
            return self._wfile
        raise ValueError(f"Unsupported mode: {mode}")

    def sendall(self, data: bytes) -> None:
        self._wfile.write(data)

    def close(self) -> None:
        return

    def response_bytes(self) -> bytes:
        return self._wfile.getvalue()


def request_response(
    state: DashboardState,
    method: str,
    path: str,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    payload = body or b""
    request_bytes = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "\r\n"
    ).encode("utf-8") + payload
    server = type("FakeServer", (), {"app_state": state})()
    sock = FakeSocket(request_bytes)
    DemoRequestHandler(sock, ("127.0.0.1", 12345), server)

    raw_response = sock.response_bytes()
    header_bytes, response_body = raw_response.split(b"\r\n\r\n", 1)
    header_lines = header_bytes.decode("iso-8859-1").split("\r\n")
    status = int(header_lines[0].split()[1])
    headers: dict[str, str] = {}
    for line in header_lines[1:]:
        if not line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return status, headers, response_body


def request_json(
    state: DashboardState,
    method: str,
    path: str,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], dict[str, object]]:
    status, headers, response_body = request_response(state, method, path, body)
    try:
        return status, headers, json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(response_body.decode("utf-8")) from exc


def request_text(
    state: DashboardState,
    method: str,
    path: str,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], str]:
    status, headers, response_body = request_response(state, method, path, body)
    return status, headers, response_body.decode("utf-8")


def archive_event(
    *,
    session_id: str,
    sequence: int,
    timestamp: str,
    event_type: str,
    message: str,
    plane: str = "control",
    source: str = "archive_test",
    job_id: str = "",
    mode_scope: str = server.CONTROL_MODE_SCOPE,
    data: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "event_id": f"{session_id}:{sequence:06d}",
        "sequence": sequence,
        "session_id": session_id,
        "timestamp": timestamp,
        "type": event_type,
        "job_id": job_id,
        "source": source,
        "plane": plane,
        "mode_scope": mode_scope,
        "message": message,
        "data": data or {},
    }


def write_archive_session(
    archive_root: str | Path,
    *,
    session_id: str,
    events: list[dict[str, object]] | None = None,
    snapshot: dict[str, object] | None = None,
) -> Path:
    session_dir = Path(archive_root) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    if events is not None:
        (session_dir / "events.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events),
            encoding="utf-8",
        )
    if snapshot is not None:
        (session_dir / "state_snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return session_dir


class DashboardStateTest(unittest.TestCase):
    def test_reconstruction_browser_uses_usrp_job_manifests(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={"REMOTE_OUTPUT_BASE": "/home/user/Downloads/jscc-test/jscc/infer_outputs"},
            source_summary="test",
        )
        with (
            patch.object(state, "_discover_default_local_usrp_image_dir", return_value=str(server.PACKAGE_ROOT)),
            patch.object(state._reconstruction_browser_manager, "open", return_value="http://127.0.0.1:8786/") as open_browser,
        ):
            state.open_reconstruction_browser()

        config = open_browser.call_args.args[0]
        self.assertEqual(config.manifest_root.name, "qpsk_batch_spool_arq_runs")
        self.assertEqual(config.default_source, "usrp-iq-direct")
        self.assertEqual(
            config.sources,
            (
                {
                    "id": "prerecorded-pytorch",
                    "label": "预录 PyTorch",
                    "remote_root": "/home/user/Downloads/jscc-test/jscc/infer_outputs",
                    "include_prefixes": ["pytorch_reference_reconstruction_"],
                    "exclude_prefixes": [],
                },
                {
                    "id": "prerecorded-tvm",
                    "label": "预录 TVM",
                    "remote_root": "/home/user/Downloads/jscc-test/jscc/infer_outputs",
                    "include_prefixes": [],
                    "exclude_prefixes": ["pytorch_reference_reconstruction_"],
                },
                {
                    "id": "prerecorded-mnn",
                    "label": "预录 MNN",
                    "remote_root": "/home/user/Downloads/jscc-test/mnn_benchmark_outputs",
                    "include_prefixes": [],
                    "exclude_prefixes": [],
                },
                {
                    "id": "usrp-qpsk",
                    "label": "USRP QPSK",
                    "remote_root": f"{server.DEFAULT_USRP_REMOTE_OUTPUT_ROOT}/qpsk/tvm",
                    "include_prefixes": [],
                    "exclude_prefixes": [],
                },
                {
                    "id": "usrp-iq-direct",
                    "label": "USRP IQ直传",
                    "remote_root": f"{server.DEFAULT_USRP_REMOTE_OUTPUT_ROOT}/iq-direct/tvm",
                    "include_prefixes": [],
                    "exclude_prefixes": [],
                },
            ),
        )

    def test_reconstruction_browser_route_returns_local_url(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        with patch.object(
            state,
            "open_reconstruction_browser",
            return_value={"status": "ok", "url": "http://127.0.0.1:8786/"},
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/reconstruction-browser/open",
                body=b"{}",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["url"], "http://127.0.0.1:8786/")

    def test_parse_json_stdout_payload_skips_trailing_non_json_lines(self) -> None:
        raw = "\n".join(
            [
                "[mnn-remote] startup",
                json.dumps({"status": "ok", "processed_count": 2}, ensure_ascii=False),
                "CPU Group: [ 0  1 ], 187500 - 1500000",
                "The device supports: i8sdot:0, fp16:0",
            ]
        )

        payload = server._parse_json_stdout_payload(raw)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["processed_count"], 2)

    def test_startup_uses_saved_successful_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "openamp_demo_live_probe_latest.json"
            payload = live_probe_payload("2026-03-15T12:00:00+0800", "saved probe summary")
            cache_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

            state = DashboardState(None, 30.0, cache_path)
            snapshot = state.current_snapshot()

        self.assertEqual(snapshot["mode"]["effective_label"], "在线读数可用")
        self.assertEqual(snapshot["board"]["current_status"]["label"], "保存的只读 SSH 探板")
        self.assertEqual(snapshot["board"]["current_status"]["requested_at"], payload["requested_at"])
        self.assertTrue(snapshot["board"]["current_status"]["reachable"])

    def test_failed_refresh_keeps_last_successful_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "openamp_demo_live_probe_latest.json"
            success = live_probe_payload("2026-03-15T12:00:00+0800", "first success")
            failure = {
                "requested_at": "2026-03-15T12:05:00+0800",
                "reachable": False,
                "status": "error",
                "summary": "probe failed",
                "error": "ssh timeout",
                "details": {},
            }

            state = DashboardState(None, 30.0, cache_path)

            with patch("server.run_live_probe", return_value=success):
                self.assertEqual(state.refresh_live_probe(), success)

            cached_after_success = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached_after_success["requested_at"], success["requested_at"])

            with patch("server.run_live_probe", return_value=failure):
                self.assertEqual(state.refresh_live_probe(), failure)

            snapshot = state.current_snapshot()
            cached_after_failure = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["board"]["current_status"]["requested_at"], success["requested_at"])
        self.assertTrue(snapshot["board"]["current_status"]["reachable"])
        self.assertEqual(cached_after_failure["requested_at"], success["requested_at"])

    def test_start_batch_inference_tracks_one_live_current_job(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        progress_calls: dict[str, int] = {}

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertEqual(max_inputs, 2)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "current-live-300",
                "live_progress": {
                    "completed_count": 0,
                    "expected_count": 2,
                },
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            calls = progress_calls.get(job_id, 0)
            progress_calls[job_id] = calls + 1
            if calls == 0:
                return {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": job_id,
                    "live_progress": {
                        "completed_count": 1,
                        "expected_count": 2,
                    },
                }
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "ML-KEM 安全协议就绪 + 真实在线推进 + 归档样例图",
                "message": "ML-KEM 安全协议已建立；Current 继续走板端本地 latent / 既有 live 数据面。",
                "artifact_sha": "sha-live",
                "sample": {"label": "sample-live"},
                "live_progress": {
                    "completed_count": 2,
                    "expected_count": 2,
                },
                "live_attempt": {
                    "security": {
                        "protocol": "mlkem_control",
                        "handshake_ms": 11.0,
                        "summary": "ML-KEM 安全协议已建立；Current 继续走板端本地 latent / 既有 live 数据面。",
                    },
                },
                "timings": {"payload_ms": 20.0, "total_ms": 31.0},
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=2)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"batch state did not finish: {state.get_batch_state()}")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["completed"], 2)
        self.assertEqual(final_state["success"], 2)
        self.assertEqual(final_state["fallback"], 0)
        self.assertEqual(final_state["sha_match"], 0)
        self.assertEqual(final_state["benchmark"]["handshake_ms"]["n"], 1)
        self.assertEqual(final_state["benchmark"]["handshake_ms"]["mean_ms"], 11.0)
        self.assertEqual(final_state["benchmark"]["total_ms"]["mean_ms"], 31.0)
        self.assertEqual(state._recent_inference_results["current"]["status"], "success")

    def test_start_batch_inference_publishes_live_current_result_into_system_status(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        progress_calls: dict[str, int] = {}

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            self.assertEqual(variant, "current")
            self.assertEqual(max_inputs, 3)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "current-live-publish-001",
                "live_progress": {
                    "completed_count": 0,
                    "expected_count": 3,
                },
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            calls = progress_calls.get(job_id, 0)
            progress_calls[job_id] = calls + 1
            if calls == 0:
                return {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": job_id,
                    "live_progress": {
                        "completed_count": 2,
                        "expected_count": 3,
                    },
                }
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "真实在线推进 + 归档样例图",
                "message": "Current live 结果已经回到页面。",
                "artifact_sha": "sha-current-live-result",
                "sample": {"label": "sample-live-publish"},
                "quality": {"psnr_db": 31.2, "ssim": 0.9412},
                "live_progress": {
                    "completed_count": 3,
                    "expected_count": 3,
                },
                "timings": {"payload_ms": 239.2, "total_ms": 251.7},
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=3)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"batch state did not finish: {state.get_batch_state()}")

            status, _, system_payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(system_payload["recent_results"]["current"]["execution_mode"], "live")
        self.assertEqual(system_payload["recent_results"]["current"]["status"], "success")
        self.assertEqual(system_payload["recent_results"]["current"]["artifact_sha"], "sha-current-live-result")
        self.assertEqual(system_payload["recent_results"]["current"]["timings"]["payload_ms"], 239.2)
        self.assertEqual(system_payload["recent_results"]["current"]["timings"]["total_ms"], 251.7)

    def test_compute_tvm_benchmark_accepts_big_little_wrapper_payload(self) -> None:
        benchmark = server._compute_tvm_benchmark(
            {
                "status": "ok",
                "runner": "run_big_little_pipeline.sh",
                "pipeline": {
                    "status": "ok",
                    "processed_count": 3,
                    "run_samples_ms": [243.717, 244.086, 246.424],
                    "run_median_ms": 244.086,
                    "run_mean_ms": 244.742,
                    "big_cores": [2],
                    "little_cores": [0, 1],
                },
            }
        )

        self.assertEqual(benchmark["inference_ms"]["n"], 3)
        self.assertEqual(benchmark["inference_ms"]["median_ms"], 244.09)
        self.assertEqual(benchmark["total_ms"]["mean_ms"], 244.74)

    def test_start_batch_inference_uses_runner_summary_for_tvm_benchmark(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            del allow_preflight_degraded
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertEqual(max_inputs, 3)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "current-biglittle-live-001",
                "live_progress": {"completed_count": 0, "expected_count": 3},
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "真实在线推进 + handwritten big.LITTLE",
                "message": "TVM big.LITTLE completed.",
                "artifact_sha": "sha-biglittle",
                "sample": {"label": "sample-biglittle"},
                "live_progress": {"completed_count": 3, "expected_count": 3},
                "timings": {"payload_ms": 999.0, "total_ms": 1001.0},
                "runner_summary": {
                    "status": "ok",
                    "run_id": "biglittle-run-001",
                    "runner": "run_big_little_pipeline.sh",
                    "pipeline": {
                        "status": "ok",
                        "processed_count": 3,
                        "execution_mode": "pipeline",
                        "run_samples_ms": [243.717, 244.086, 246.424],
                        "run_median_ms": 244.086,
                        "run_mean_ms": 244.742,
                        "big_cores": [2],
                        "little_cores": [0, 1],
                    },
                },
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=3)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"batch state did not finish: {state.get_batch_state()}")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["completed"], 3)
        self.assertEqual(final_state["benchmark"]["inference_ms"]["median_ms"], 244.09)
        self.assertEqual(final_state["benchmark"]["total_ms"]["mean_ms"], 244.74)
        self.assertEqual(final_state["runner_summary"]["pipeline"]["big_cores"], [2])
        status, _, system_payload = request_json(state, "GET", "/api/system-status")
        self.assertEqual(status, 200)
        current = system_payload["recent_results"]["current"]
        self.assertEqual(current["run_id"], "biglittle-run-001")
        self.assertEqual(current["processed_count"], 3)
        self.assertEqual(current["inference_benchmark"]["inference_ms"]["median_ms"], 244.09)
        self.assertEqual(current["benchmark"]["total_ms"]["mean_ms"], 244.74)
        self.assertEqual(current["runner_summary"]["pipeline"]["little_cores"], [0, 1])

    def test_start_batch_inference_publishes_prerecorded_tvm_summary_without_sample_payload(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            del allow_preflight_degraded
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertEqual(max_inputs, 3)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "current-prerecorded-biglittle-001",
                "live_progress": {"completed_count": 0, "expected_count": 3},
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "live_progress": {"completed_count": 3, "expected_count": 3},
                "runner_summary": {
                    "status": "ok",
                    "mode": "big_little_pipeline",
                    "execution_mode": "pipeline",
                    "processed_count": 3,
                    "input_count": 3,
                    "run_samples_ms": [240.1, 240.2, 240.3],
                    "run_median_ms": 240.2,
                    "run_mean_ms": 240.2,
                    "big_cores": [2],
                    "little_cores": [0, 1],
                },
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=3)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"batch state did not finish: {state.get_batch_state()}")

            status, _, system_payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(state.get_batch_state()["benchmark"]["inference_ms"]["median_ms"], 240.2)
        current = system_payload["recent_results"]["current"]
        self.assertEqual(current["status"], "success")
        self.assertEqual(current["execution_mode"], "live")
        self.assertEqual(current["source_label"], "预录输入 + TVM 板端推理 + 归档样例图")
        self.assertEqual(current["inference_benchmark"]["inference_ms"]["median_ms"], 240.2)
        self.assertEqual(system_payload["last_inference"]["status"], "success")

    def test_run_tvm_batch_accepts_complete_summary_from_stale_wrapper_process(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={
                "REMOTE_TVM_PYTHON": "/opt/tvm/bin/python",
                "REMOTE_INPUT_DIR": "/remote/input",
                "REMOTE_OUTPUT_BASE": "/remote/output",
                "REMOTE_SNR_CURRENT": "10",
                "REMOTE_BATCH_CURRENT": "1",
                "REMOTE_CURRENT_ARTIFACT": "/remote/model.so",
            },
            source_summary="test",
        )
        complete_summary = {
            "status": "ok",
            "processed_count": 1,
            "selected_input_count": 1,
            "run_samples_ms": [252.3],
            "run_median_ms": 252.3,
            "run_mean_ms": 252.3,
        }
        progress_seen: list[tuple[int, int]] = []

        with patch(
            "server.subprocess.Popen",
            return_value=KillableFakePopen(
                stdout_lines=[
                    json.dumps({"openamp_demo_progress": {"delta": 1, "completed_count": 1}}) + "\n",
                    json.dumps(complete_summary) + "\n",
                ],
                stderr_text="wrapper exited after remote result was written",
                returncode=124,
            ),
        ):
            payload = state._run_tvm_batch_with_access(
                access,
                count=1,
                progress_callback=lambda completed, total: progress_seen.append((completed, total)),
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["processed_count"], 1)
        self.assertEqual(payload["run_median_ms"], 252.3)
        self.assertEqual(progress_seen, [(1, 1)])

    def test_run_tvm_batch_marks_statusless_complete_summary_ok(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={
                "REMOTE_TVM_PYTHON": "/opt/tvm/bin/python",
                "REMOTE_INPUT_DIR": "/remote/input",
                "REMOTE_OUTPUT_BASE": "/remote/output",
                "REMOTE_SNR_CURRENT": "10",
                "REMOTE_BATCH_CURRENT": "1",
                "REMOTE_CURRENT_ARTIFACT": "/remote/model.so",
            },
            source_summary="test",
        )
        statusless_summary = {
            "processed_count": 1,
            "input_count": 1,
            "run_samples_ms": [608.835],
            "run_median_ms": 608.835,
            "run_mean_ms": 608.835,
        }

        with patch(
            "server.subprocess.Popen",
            return_value=FakePopen(
                stdout_lines=[json.dumps(statusless_summary) + "\n"],
                returncode=0,
            ),
        ):
            payload = state._run_tvm_batch_with_access(access, count=1)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["processed_count"], 1)
        self.assertEqual(payload["run_median_ms"], 608.835)

    def test_run_tvm_batch_decodes_subprocess_output_with_replacement(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={
                "REMOTE_TVM_PYTHON": "/opt/tvm/bin/python",
                "REMOTE_INPUT_DIR": "/remote/input",
                "REMOTE_OUTPUT_BASE": "/remote/output",
                "REMOTE_SNR_CURRENT": "10",
                "REMOTE_BATCH_CURRENT": "1",
                "REMOTE_CURRENT_ARTIFACT": "/remote/model.so",
            },
            source_summary="test",
        )
        statusless_summary = {
            "processed_count": 1,
            "input_count": 1,
            "run_samples_ms": [252.3],
            "run_median_ms": 252.3,
            "run_mean_ms": 252.3,
        }

        with patch(
            "server.subprocess.Popen",
            return_value=FakePopen(stdout_lines=[json.dumps(statusless_summary) + "\n"], returncode=0),
        ) as popen:
            state._run_tvm_batch_with_access(access, count=1)

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_run_tvm_batch_flattens_big_little_wrapper_summary(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={
                "REMOTE_TVM_PYTHON": "/opt/tvm/bin/python",
                "REMOTE_INPUT_DIR": "/remote/usrp-rx",
                "REMOTE_OUTPUT_BASE": "/remote/output",
                "REMOTE_SNR_CURRENT": "10",
                "REMOTE_BATCH_CURRENT": "1",
                "REMOTE_CURRENT_ARTIFACT": "/remote/model.so",
                "INFERENCE_CURRENT_CMD": "bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --max-inputs 300",
            },
            source_summary="test",
        )
        wrapper_summary = {
            "status": "ok",
            "runner": "run_big_little_pipeline.sh",
            "pipeline": {
                "status": "ok",
                "processed_count": 2,
                "input_count": 2,
                "run_samples_ms": [243.7, 244.1],
                "run_median_ms": 243.9,
                "run_mean_ms": 243.9,
                "big_cores": [2],
                "little_cores": [0, 1],
            },
        }

        with patch(
            "server.subprocess.Popen",
            return_value=FakePopen(stdout_lines=[json.dumps(wrapper_summary) + "\n"], returncode=0),
        ):
            payload = state._run_tvm_batch_with_access(access, count=2)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["runner"], "run_big_little_pipeline.sh")
        self.assertEqual(payload["processed_count"], 2)
        self.assertEqual(payload["run_median_ms"], 243.9)
        self.assertEqual(payload["big_cores"], [2])

    def test_run_tvm_batch_uses_big_little_script_when_current_command_selects_it(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        access = server.BoardAccessConfig(
            host="demo-board",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={
                "REMOTE_TVM_PYTHON": "/opt/tvm/bin/python",
                "REMOTE_INPUT_DIR": "/remote/usrp-rx",
                "REMOTE_OUTPUT_BASE": "/remote/output",
                "REMOTE_SNR_CURRENT": "10",
                "REMOTE_BATCH_CURRENT": "1",
                "REMOTE_CURRENT_ARTIFACT": "/remote/model.so",
                "INFERENCE_CURRENT_CMD": "bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --max-inputs 300",
            },
            source_summary="test",
        )
        captured: dict[str, object] = {}

        def fake_popen(command, *args, **kwargs):
            captured["command"] = list(command)
            captured["env"] = dict(kwargs.get("env") or {})
            return FakePopen(
                stdout_lines=[
                    json.dumps(
                        {
                            "status": "ok",
                            "runner": "run_big_little_pipeline.sh",
                            "pipeline": {
                                "status": "ok",
                                "processed_count": 2,
                                "input_count": 2,
                                "run_samples_ms": [244.0, 245.0],
                                "run_median_ms": 244.5,
                                "run_mean_ms": 244.5,
                            },
                        }
                    )
                    + "\n"
                ],
                returncode=0,
            )

        with patch("server.subprocess.Popen", side_effect=fake_popen):
            payload = state._run_tvm_batch_with_access(access, count=2)

        command = captured["command"]
        self.assertIn("run_big_little_pipeline.sh", str(command[1]))
        self.assertIn("--max-inputs", command)
        self.assertEqual(command[command.index("--max-inputs") + 1], "2")
        self.assertEqual(payload["processed_count"], 2)

    def test_runner_only_fallback_allows_host_env_error_preflight(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        self.assertTrue(
            state._can_launch_runner_only_fallback(
                board_access=Mock(connection_ready=True),
                status_payload={"status_category": "host_env_error"},
            )
        )

    def test_run_demo_inference_degraded_runner_only_skips_mlkem_helper_arm(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = Mock(configured=True, probe_ready=True, connection_ready=True)
        board_access.build_env.return_value = {}
        state._board_access = board_access
        live_access = Mock()
        live_access.missing_inference_fields.return_value = []
        fake_live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": "runner-only-live-001",
                    "control_transport": "none",
                    "live_progress": {"completed_count": 0, "expected_count": 3},
                }
            ],
            job_id="runner-only-live-001",
        )

        with (
            patch.object(state, "_live_board_access_for_variant", return_value=live_access),
            patch.object(state, "_nontrusted_current_requires_signed_admission", return_value=False),
            patch("server.expected_sha_for_variant", return_value="sha-current"),
            patch("server.describe_demo_variant_support", return_value={"mode": "legacy_sha"}),
            patch(
                "server.query_live_status",
                return_value={
                    "status": "error",
                    "status_category": "host_env_error",
                    "message": "host environment cannot open SSH socket",
                },
            ),
            patch.object(
                state,
                "_arm_mlkem_security_context",
                side_effect=AssertionError("runner-only degraded launch must not arm ML-KEM helper"),
            ),
            patch("server.launch_remote_reconstruction_job", return_value=fake_live_job) as launch_job,
        ):
            payload = state.run_demo_inference(
                variant="current",
                image_index=0,
                allow_preflight_degraded=True,
                max_inputs=3,
            )

        launch_job.assert_called_once()
        _, kwargs = launch_job.call_args
        self.assertEqual(kwargs["control_transport"], "none")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["job_id"], "runner-only-live-001")

    def test_start_batch_inference_usrp_tvm_does_not_reuse_archived_quality(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})
        progress_calls: dict[str, int] = {}

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            del allow_preflight_degraded
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertEqual(max_inputs, 5)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "usrp-tvm-live-001",
                "live_progress": {"completed_count": 0, "expected_count": 5},
                "live_attempt": {
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 0, "expected_count": 5, "state": "running"},
                        "transport": {"completed_count": 0, "expected_count": 5, "state": "pending"},
                        "inference": {"completed_count": 0, "expected_count": 5, "state": "pending"},
                    }
                },
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            calls = progress_calls.get(job_id, 0)
            progress_calls[job_id] = calls + 1
            if calls == 0:
                return {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": job_id,
                    "live_progress": {"completed_count": 0, "expected_count": 5},
                    "live_attempt": {
                        "stage_progress": {
                            "host_preprocess": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                            "transport": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                            "inference": {"completed_count": 2, "expected_count": 5, "state": "running"},
                        }
                    },
                }
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "USRP 混合链路在线推进 + 归档样例图",
                "message": "USRP TVM completed.",
                "artifact_sha": "sha-usrp-tvm",
                "sample": {"label": "airfield"},
                "quality": {"psnr_db": 37.0, "ssim": 0.97},
                "live_progress": {"completed_count": 5, "expected_count": 5},
                "timings": {"payload_ms": 121.0, "total_ms": 130.0},
                "wrapper_summary": {
                    "inference_engine": "tvm",
                    "iq_stage_benchmark": {
                        "tx_control_ms": {"n": 5, "median_ms": 18.0, "p95_ms": 29.0},
                        "remote_decode_ms": {"n": 5, "median_ms": 64.0, "p95_ms": 91.0},
                    },
                    "inference_summary": {
                        "status": "ok",
                        "processed_count": 5,
                        "selected_input_count": 5,
                        "run_samples_ms": [120.0, 121.0, 122.0, 123.0, 124.0],
                        "run_median_ms": 122.0,
                        "run_mean_ms": 122.0,
                    },
                },
                "live_attempt": {
                    "wrapper_summary": {
                        "inference_engine": "tvm",
                        "iq_stage_benchmark": {
                            "tx_control_ms": {"n": 5, "median_ms": 18.0, "p95_ms": 29.0},
                            "remote_decode_ms": {"n": 5, "median_ms": 64.0, "p95_ms": 91.0},
                        },
                        "inference_summary": {
                            "status": "ok",
                            "processed_count": 5,
                            "selected_input_count": 5,
                            "run_samples_ms": [120.0, 121.0, 122.0, 123.0, 124.0],
                            "run_median_ms": 122.0,
                            "run_mean_ms": 122.0,
                        },
                    },
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                        "transport": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                        "inference": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                    },
                },
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=5)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"usrp tvm batch did not finish: {state.get_batch_state()}")

            status, _, system_payload = request_json(state, "GET", "/api/system-status")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["engine"], "tvm")
        self.assertEqual(final_state["iq_stage_benchmark"]["tx_control_ms"]["median_ms"], 18.0)
        self.assertEqual(final_state["iq_stage_benchmark"]["remote_decode_ms"]["p95_ms"], 91.0)
        self.assertNotIn("quality", final_state)
        self.assertEqual(status, 200)
        self.assertEqual(system_payload["recent_results"]["current"]["execution_mode"], "live")
        self.assertNotIn("quality", system_payload["recent_results"]["current"])
        self.assertEqual(system_payload["recent_results"]["current"]["wrapper_summary"]["inference_engine"], "tvm")

    def test_start_batch_inference_marks_iq_remote_dir_images_decoded_while_transport_runs(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})
        allow_finish = threading.Event()

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            del allow_preflight_degraded
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertEqual(max_inputs, 3)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "usrp-stream-live-001",
                "live_progress": {"completed_count": 0, "expected_count": 3},
                "live_attempt": {
                    "wrapper_summary": {
                        "iq_remote_decode_manifest": {
                            "remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx",
                            "decode_manifest": {
                                "decoded_count": 1,
                                "files": ["/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz"],
                            },
                        }
                    },
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 3, "expected_count": 3, "state": "completed"},
                        "transport": {"completed_count": 1, "expected_count": 3, "state": "running"},
                        "inference": {"completed_count": 0, "expected_count": 3, "state": "pending"},
                    },
                },
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            self.assertEqual(job_id, "usrp-stream-live-001")
            allow_finish.wait(timeout=2.0)
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "USRP stream + handwritten TVM",
                "message": "USRP TVM completed.",
                "artifact_sha": "sha-usrp-stream",
                "sample": {"label": "airfield"},
                "quality": {"psnr_db": 37.0, "ssim": 0.97},
                "live_progress": {"completed_count": 3, "expected_count": 3},
                "timings": {"payload_ms": 121.0, "total_ms": 130.0},
                "wrapper_summary": {
                    "inference_engine": "tvm",
                    "iq_remote_decode_manifest": {
                        "remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx",
                        "decode_manifest": {
                            "decoded_count": 3,
                            "files": [
                                "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz",
                                "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000001.npz",
                                "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000002.npz",
                            ],
                        },
                    },
                    "inference_summary": {
                        "status": "ok",
                        "processed_count": 3,
                        "selected_input_count": 3,
                        "run_samples_ms": [120.0, 121.0, 122.0],
                        "run_median_ms": 121.0,
                        "run_mean_ms": 121.0,
                    },
                },
                "live_attempt": {
                    "wrapper_summary": {
                        "inference_engine": "tvm",
                        "iq_remote_decode_manifest": {
                            "remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx",
                            "decode_manifest": {
                                "decoded_count": 3,
                                "files": [
                                    "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz",
                                    "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000001.npz",
                                    "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000002.npz",
                                ],
                            },
                        },
                        "inference_summary": {
                            "status": "ok",
                            "processed_count": 3,
                            "selected_input_count": 3,
                            "run_samples_ms": [120.0, 121.0, 122.0],
                            "run_median_ms": 121.0,
                            "run_mean_ms": 121.0,
                        },
                    },
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 3, "expected_count": 3, "state": "completed"},
                        "transport": {"completed_count": 3, "expected_count": 3, "state": "completed"},
                        "inference": {"completed_count": 3, "expected_count": 3, "state": "completed"},
                    },
                },
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=3)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                images = current.get("iq_streaming_images") or []
                if images:
                    break
                time.sleep(0.01)
            else:
                self.fail(f"iq streaming state did not appear: {state.get_batch_state()}")

            self.assertEqual(images[0]["status"], "decoded")
            self.assertEqual(images[0]["remote_npz"], "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz")
            self.assertEqual(images[1]["status"], "pending")
            self.assertEqual(images[2]["status"], "pending")
            allow_finish.set()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"usrp stream batch did not finish: {state.get_batch_state()}")

        final_images = state.get_batch_state()["iq_streaming_images"]
        self.assertEqual([image["status"] for image in final_images], ["done", "done", "done"])

    def test_iq_streaming_images_prefers_npy_summary_files_over_npz_manifest_defaults(self) -> None:
        manifest = {
            "decode_manifest": {
                "images": [
                    {
                        "index": 0,
                        "remote_npz": "/home/user/cockpit_usrp_rx/run_rx/00000000.npz",
                    },
                    {
                        "index": 1,
                        "remote_npz": "/home/user/cockpit_usrp_rx/run_rx/00000001.npz",
                    },
                ],
                "files": [
                    "/home/user/cockpit_usrp_rx/run_rx/00000000.npy",
                    "/home/user/cockpit_usrp_rx/run_rx/00000001.npy",
                ],
            },
        }

        images = server._iq_streaming_images_from_manifest(
            manifest,
            total=2,
            inference_state="completed",
            final_success=True,
        )

        self.assertEqual([image["remote_npz"] for image in images], [
            "/home/user/cockpit_usrp_rx/run_rx/00000000.npy",
            "/home/user/cockpit_usrp_rx/run_rx/00000001.npy",
        ])
        self.assertEqual([image["status"] for image in images], ["done", "done"])

    def test_iq_partial_manifest_uses_configured_npy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            run_dir = Path(temp_dir_name)
            image_dir = run_dir / "image_0000"
            image_dir.mkdir()
            (image_dir / "decode_summary.json").write_text(
                json.dumps({"status": "ok", "frame_complete": True}),
                encoding="utf-8",
            )

            manifest = usrp_runtime._iq_remote_decode_stage_manifest_from_image_dirs(
                run_dir,
                "/home/user/cockpit_usrp_rx/run_rx",
                decoded_extension="npy",
            )

        self.assertIsNotNone(manifest)
        files = manifest["decode_manifest"]["files"]
        self.assertEqual(files, ["/home/user/cockpit_usrp_rx/run_rx/00000000.npy"])

    def test_start_batch_inference_marks_done_when_worker_raises(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.object(state, "run_demo_inference", side_effect=IndexError("invalid image_index")):
            payload = state.start_batch_inference(count=3)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["message"], "IndexError: invalid image_index")

        self.assertEqual(state.get_batch_state(), {"status": "idle"})

    def test_running_inference_job_record_refreshes_stale_snapshot(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        job = FakeInferenceJob(
            [
                {
                    "status": "success",
                    "request_state": "completed",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "completed on board",
                    "progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
                }
            ],
            job_id="stale-job-001",
        )
        state._inference_jobs[job.job_id] = {
            "job": job,
            "job_id": job.job_id,
            "variant": "current",
            "image_index": 0,
            "last_snapshot": {
                "status": "running",
                "request_state": "running",
                "execution_mode": "live",
                "variant": "current",
                "message": "stale local snapshot",
            },
        }

        self.assertIsNone(state._running_inference_job_record())
        self.assertEqual(state._inference_jobs[job.job_id]["last_snapshot"]["request_state"], "completed")

    def test_start_batch_inference_returns_blocked_without_running_batch_when_launch_falls_back(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.object(
            state,
            "run_demo_inference",
            return_value={
                "status": "fallback",
                "execution_mode": "prerecorded",
                "request_state": "completed",
                "status_category": "config_error",
                "source_label": "配置不完整，回退展示（归档样例）",
                "message": "远端推理配置不完整或不可用，请检查连接信息和推理环境参数。 当前已回退到预录结果。",
                "live_progress": {
                    "completed_count": 0,
                    "expected_count": 3,
                },
            },
        ) as run_demo_inference:
            payload = state.start_batch_inference(count=3)

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["status_category"], "config_error")
        self.assertEqual(payload["engine"], "tvm")
        self.assertEqual(payload["service_mode"], "FULL_FRAME")
        self.assertIn("远端推理配置不完整或不可用", payload["message"])
        batch_state = state.get_batch_state()
        self.assertEqual(batch_state["status"], "done")
        self.assertEqual(batch_state["completed"], 0)
        self.assertEqual(batch_state["fallback"], 3)
        self.assertEqual(batch_state["status_category"], "config_error")
        self.assertIn("远端推理配置不完整或不可用", batch_state["message"])
        run_demo_inference.assert_called_once()

    def test_start_batch_inference_uses_standard_runner_when_crypto_enabled(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True

        with (
            patch.object(
                state,
                "run_demo_inference",
                return_value={
                    "status": "fallback",
                    "execution_mode": "prerecorded",
                    "request_state": "completed",
                    "status_category": "config_error",
                    "source_label": "配置不完整，回退展示（归档样例）",
                    "message": "远端推理配置不完整或不可用，请检查连接信息和推理环境参数。 当前已回退到预录结果。",
                    "live_progress": {"completed_count": 0, "expected_count": 3},
                },
            ) as run_demo_inference,
            patch.object(state, "run_mlkem_inference", side_effect=AssertionError("legacy ML-KEM data path should not be used")),
        ):
            payload = state.start_batch_inference(count=3)

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["status_category"], "config_error")
        self.assertEqual(payload["engine"], "tvm")
        self.assertEqual(payload["service_mode"], "FULL_FRAME")
        batch_state = state.get_batch_state()
        self.assertEqual(batch_state["status"], "done")
        self.assertEqual(batch_state["completed"], 0)
        self.assertEqual(batch_state["fallback"], 3)
        self.assertEqual(batch_state["status_category"], "config_error")
        run_demo_inference.assert_called_once()

    def test_start_batch_inference_alert_mode_keeps_batch_state_accessible_and_completes(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state.set_link_director_profile({"profile_id": "flaky"})

        payload = state.start_batch_inference(count=3)
        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["service_mode"], "ALERT_ONLY")
        self.assertEqual(payload["total"], 3)

        # Batch mode should stay stable for the lifetime of this batch even if
        # the operator changes the staged profile afterwards.
        state.set_link_director_profile({"profile_id": "normal"})

        time.sleep(0.05)
        holder: dict[str, object] = {}

        def _read_batch_state() -> None:
            holder["state"] = state.get_batch_state()

        reader = threading.Thread(target=_read_batch_state, daemon=True)
        reader.start()
        reader.join(timeout=0.2)
        self.assertFalse(reader.is_alive(), "get_batch_state() blocked during ALERT_ONLY batch")

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            current = state.get_batch_state()
            if current.get("status") == "done":
                break
            time.sleep(0.02)
        else:
            self.fail(f"alert-mode batch did not finish: {state.get_batch_state()}")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["service_mode"], "ALERT_ONLY")
        self.assertEqual(final_state["completed"], 3)
        self.assertEqual(final_state["total"], 3)
        self.assertEqual(final_state["success"], 0)
        self.assertEqual(final_state["fallback"], 0)
        self.assertIsNone(final_state["benchmark"])

    def test_start_batch_inference_roi_mode_reduces_effective_count_and_completes(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state.set_link_director_profile({"profile_id": "lossy"})
        progress_calls: dict[str, int] = {}

        def fake_run_demo_inference(
            *,
            variant: str,
            image_index: int,
            allow_preflight_degraded: bool = False,
            max_inputs: int = server.DEFAULT_MAX_INPUTS,
        ) -> dict[str, object]:
            self.assertEqual(variant, "current")
            self.assertEqual(image_index, 0)
            self.assertTrue(allow_preflight_degraded)
            self.assertEqual(max_inputs, 3)
            return {
                "status": "running",
                "execution_mode": "live",
                "request_state": "running",
                "job_id": "roi-live-003",
                "live_progress": {
                    "completed_count": 0,
                    "expected_count": 3,
                },
            }

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            calls = progress_calls.get(job_id, 0)
            progress_calls[job_id] = calls + 1
            if calls == 0:
                return {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": job_id,
                    "live_progress": {
                        "completed_count": 1,
                        "expected_count": 3,
                    },
                }
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "source_label": "ROI_ONLY 降采样在线推进",
                "message": "ROI_ONLY 模式下按 3:1 降采样完成在线推进。",
                "artifact_sha": "sha-roi",
                "sample": {"label": "sample-roi"},
                "live_progress": {
                    "completed_count": 3,
                    "expected_count": 3,
                },
                "live_attempt": {
                    "security": {
                        "protocol": "mlkem_control",
                        "handshake_ms": 9.5,
                        "summary": "ROI_ONLY 降采样批量已完成。",
                    },
                },
                "timings": {"payload_ms": 12.0, "total_ms": 18.0},
            }

        with (
            patch.object(state, "run_demo_inference", side_effect=fake_run_demo_inference),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_batch_inference(count=9)
            self.assertEqual(payload["status"], "started")
            self.assertEqual(payload["service_mode"], "ROI_ONLY")
            self.assertEqual(payload["total"], 3)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"roi-only batch did not finish: {state.get_batch_state()}")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["service_mode"], "ROI_ONLY")
        self.assertEqual(final_state["completed"], 3)
        self.assertEqual(final_state["total"], 3)
        self.assertEqual(final_state["success"], 3)
        self.assertEqual(final_state["fallback"], 0)
        self.assertEqual(final_state["benchmark"]["handshake_ms"]["mean_ms"], 9.5)

    def test_start_mnn_batch_inference_tracks_300_image_run(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        mnn_summary = {
            "status": "ok",
            "variant": "current",
            "selected_input_count": 300,
            "processed_count": 300,
            "sample_stats": {
                "run_ms": {
                    "count": 300,
                    "min_ms": 120.0,
                    "max_ms": 220.0,
                    "mean_ms": 163.2,
                    "median_ms": 161.9,
                    "variance_ms2": 25.0,
                },
                "resize_ms": {
                    "count": 300,
                    "min_ms": 1.8,
                    "max_ms": 16.4,
                    "mean_ms": 8.4,
                    "median_ms": 8.0,
                    "variance_ms2": 3.0,
                },
                "total_ms": {
                    "count": 300,
                    "min_ms": 240.0,
                    "max_ms": 410.0,
                    "mean_ms": 331.0,
                    "median_ms": 329.6,
                    "variance_ms2": 42.0,
                },
            },
        }

        with patch.object(state, "_run_mnn_batch", return_value=mnn_summary):
            payload = state.start_mnn_batch_inference(count=300)
            self.assertEqual(payload["status"], "started")
            self.assertEqual(payload["engine"], "mnn")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"mnn batch did not finish: {state.get_batch_state()}")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["engine"], "mnn")
        self.assertEqual(final_state["completed"], 300)
        self.assertEqual(final_state["total"], 300)
        self.assertEqual(final_state["success"], 300)
        self.assertEqual(final_state["fallback"], 0)
        self.assertEqual(final_state["benchmark"]["inference_ms"]["mean_ms"], 163.2)
        self.assertEqual(final_state["benchmark"]["total_ms"]["mean_ms"], 331.0)

    def test_start_mnn_usrp_batch_hydrates_recent_current_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})
        progress_calls: dict[str, int] = {}

        def fake_register_live_job(*, live_job, variant: str, image_index: int, security_context=None):
            del security_context
            record = {"job": live_job, "job_id": live_job.job_id, "variant": variant, "image_index": image_index}
            return record, {"job_id": live_job.job_id}

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            calls = progress_calls.get(job_id, 0)
            progress_calls[job_id] = calls + 1
            if calls == 0:
                return {
                    "status": "running",
                    "execution_mode": "live",
                    "request_state": "running",
                    "job_id": job_id,
                    "live_progress": {"completed_count": 0, "expected_count": 5},
                    "live_attempt": {
                        "stage_progress": {
                            "host_preprocess": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                            "transport": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                            "inference": {"completed_count": 2, "expected_count": 5, "state": "running"},
                        }
                    },
                }
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "message": "USRP MNN completed.",
                "live_progress": {"completed_count": 5, "expected_count": 5},
                "live_attempt": {
                    "wrapper_summary": {
                        "inference_engine": "mnn",
                        "inference_summary": {
                            "status": "ok",
                            "processed_count": 5,
                            "selected_input_count": 5,
                            "sample_stats": {
                                "run_ms": {"count": 5, "mean_ms": 163.2, "median_ms": 161.9},
                                "total_ms": {"count": 5, "mean_ms": 331.0, "median_ms": 329.6},
                            },
                        },
                    },
                    "artifacts": {"remote_rx_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-001_rx"},
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                        "transport": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                        "inference": {"completed_count": 5, "expected_count": 5, "state": "completed"},
                    },
                },
            }

        fake_live_job = Mock(job_id="usrp-mnn-live-001")
        with (
            patch.object(state, "_arm_mlkem_security_context", return_value=(None, None)),
            patch("server.launch_local_usrp_reconstruction_job", return_value=fake_live_job),
            patch.object(state, "_register_live_job", side_effect=fake_register_live_job),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_mnn_batch_inference(count=5)
            self.assertEqual(payload["status"], "started")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"usrp mnn batch did not finish: {state.get_batch_state()}")

            status, _, system_payload = request_json(state, "GET", "/api/system-status")

        final_state = state.get_batch_state()
        self.assertEqual(final_state["engine"], "mnn")
        self.assertEqual(final_state["benchmark"]["total_ms"]["median_ms"], 329.6)
        self.assertNotIn("quality", final_state)
        self.assertEqual(status, 200)
        self.assertEqual(system_payload["recent_results"]["current"]["execution_mode"], "live")
        self.assertEqual(system_payload["recent_results"]["current"]["wrapper_summary"]["inference_engine"], "mnn")
        self.assertNotIn("quality", system_payload["recent_results"]["current"])

    def test_start_mnn_usrp_batch_arms_security_outside_state_lock(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})

        def fake_arm_security_context(**_kwargs):
            acquired = state._lock.acquire(timeout=0.05)
            self.assertTrue(acquired, "security arm called while DashboardState lock is held")
            state._lock.release()
            return None, None

        def fake_register_live_job(*, live_job, variant: str, image_index: int, security_context=None):
            del security_context
            record = {"job": live_job, "job_id": live_job.job_id, "variant": variant, "image_index": image_index}
            return record, {"job_id": live_job.job_id}

        def fake_peek_inference_progress(job_id: str) -> dict[str, object]:
            return {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "job_id": job_id,
                "live_progress": {"completed_count": 1, "expected_count": 1},
                "live_attempt": {
                    "wrapper_summary": {
                        "inference_engine": "mnn",
                        "inference_summary": {
                            "status": "ok",
                            "processed_count": 1,
                            "selected_input_count": 1,
                            "sample_stats": {
                                "run_ms": {"count": 1, "mean_ms": 10.0, "median_ms": 10.0},
                                "total_ms": {"count": 1, "mean_ms": 12.0, "median_ms": 12.0},
                            },
                        },
                    },
                    "stage_progress": {
                        "host_preprocess": {"completed_count": 1, "expected_count": 1, "state": "completed"},
                        "transport": {"completed_count": 1, "expected_count": 1, "state": "completed"},
                        "inference": {"completed_count": 1, "expected_count": 1, "state": "completed"},
                    },
                },
            }

        fake_live_job = Mock(job_id="usrp-mnn-lock-001")
        with (
            patch.object(state, "_arm_mlkem_security_context", side_effect=fake_arm_security_context),
            patch("server.launch_local_usrp_reconstruction_job", return_value=fake_live_job),
            patch.object(state, "_register_live_job", side_effect=fake_register_live_job),
            patch.object(state, "_peek_inference_progress", side_effect=fake_peek_inference_progress),
        ):
            payload = state.start_mnn_batch_inference(count=1)

        self.assertEqual(payload["status"], "started")

    def test_start_mnn_batch_inference_updates_progress_while_running(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        progress_seen = threading.Event()
        release_runner = threading.Event()

        mnn_summary = {
            "status": "ok",
            "variant": "current",
            "selected_input_count": 300,
            "processed_count": 300,
            "sample_stats": {
                "run_ms": {"count": 300, "min_ms": 100.0, "max_ms": 200.0, "mean_ms": 150.0, "median_ms": 149.0},
                "total_ms": {"count": 300, "min_ms": 220.0, "max_ms": 380.0, "mean_ms": 310.0, "median_ms": 308.0},
            },
        }

        def fake_run_mnn_batch(*, count: int = 300, progress_callback=None) -> dict[str, object]:
            self.assertEqual(count, 300)
            self.assertIsNotNone(progress_callback)
            progress_callback(120, 300)
            progress_seen.set()
            release_runner.wait(timeout=1.0)
            return mnn_summary

        with patch.object(state, "_run_mnn_batch", side_effect=fake_run_mnn_batch):
            payload = state.start_mnn_batch_inference(count=300)
            self.assertEqual(payload["status"], "started")
            self.assertTrue(progress_seen.wait(timeout=1.0), "mnn progress callback was not observed")
            mid_state = state.get_batch_state()
            self.assertEqual(mid_state["status"], "running")
            self.assertEqual(mid_state["engine"], "mnn")
            self.assertEqual(mid_state["completed"], 120)
            self.assertEqual(mid_state["total"], 300)
            release_runner.set()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                current = state.get_batch_state()
                if current.get("status") == "done":
                    break
                time.sleep(0.02)
            else:
                self.fail(f"mnn batch did not finish after progress update: {state.get_batch_state()}")

    def test_run_mnn_batch_does_not_leak_torch_pythonpath_without_explicit_mnn_override(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "mnn.env"
            env_path.write_text(
                "\n".join(
                    [
                        "REMOTE_HOST=100.121.87.73",
                        "REMOTE_USER=user",
                        "REMOTE_PASS=demo-pass",
                        "REMOTE_SSH_PORT=22",
                        "REMOTE_MNN_PYTHON=/home/user/anaconda3/envs/MNN/bin/python",
                        "REMOTE_INPUT_DIR=/home/user/Downloads/jscc-test/encoder_outputs",
                        "REMOTE_OUTPUT_BASE=/home/user/Downloads/jscc-test/mnn_benchmark_outputs",
                        "REMOTE_SNR_CURRENT=10",
                        "MNN_FP32_MODEL=/home/user/Downloads/MNNversion/origin/model1.mnn",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            captured_env: dict[str, str] = {}
            captured_cmd: list[str] = []

            def fake_popen(*args, **kwargs):
                if args:
                    captured_cmd.extend(list(args[0]))
                captured_env.update(kwargs.get("env") or {})
                return FakePopen(
                    stdout_lines=[
                        json.dumps(
                            {
                                "status": "ok",
                                "selected_input_count": 3,
                                "processed_count": 3,
                                "sample_stats": {},
                                "errors": [],
                            },
                            ensure_ascii=False,
                        )
                    ]
                )

            with (
                patch.object(server, "DEFAULT_MNN_BATCH_ENV_FILE", env_path),
                patch("server.resolve_bash_executable", return_value="bash"),
                patch("server.subprocess.Popen", side_effect=fake_popen),
            ):
                payload = state._run_mnn_batch(count=3)

        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("REMOTE_TORCH_PYTHONPATH", captured_env)
        self.assertNotIn("REMOTE_REAL_EXTRA_PYTHONPATH", captured_env)
        self.assertIn("--warmup-inputs", captured_cmd)
        self.assertEqual(captured_cmd[captured_cmd.index("--warmup-inputs") + 1], "0")

    def test_run_mnn_batch_uses_usrp_rx_dir_when_input_source_is_usrp(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides(
            {
                "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "mnn.env"
            env_path.write_text(
                "\n".join(
                    [
                        "REMOTE_HOST=100.121.87.73",
                        "REMOTE_USER=user",
                        "REMOTE_PASS=demo-pass",
                        "REMOTE_SSH_PORT=22",
                        "REMOTE_MNN_PYTHON=/home/user/anaconda3/envs/MNN/bin/python",
                        "REMOTE_INPUT_DIR=/home/user/Downloads/jscc-test/encoder_outputs",
                        "REMOTE_OUTPUT_BASE=/home/user/Downloads/jscc-test/mnn_benchmark_outputs",
                        "REMOTE_SNR_CURRENT=10",
                        "MNN_FP32_MODEL=/home/user/Downloads/MNNversion/origin/model1.mnn",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            captured_env: dict[str, str] = {}

            def fake_popen(*args, **kwargs):
                del args
                captured_env.update(kwargs.get("env") or {})
                return FakePopen(
                    stdout_lines=[
                        json.dumps(
                            {
                                "status": "ok",
                                "selected_input_count": 3,
                                "processed_count": 3,
                                "sample_stats": {},
                                "errors": [],
                            },
                            ensure_ascii=False,
                        )
                    ]
                )

            with (
                patch.object(server, "DEFAULT_MNN_BATCH_ENV_FILE", env_path),
                patch("server.resolve_bash_executable", return_value="bash"),
                patch("server.subprocess.Popen", side_effect=fake_popen),
            ):
                payload = state._run_mnn_batch(count=3)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(captured_env["OPENAMP_DEMO_INPUT_SOURCE_MODE"], "usrp")
        self.assertEqual(captured_env["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx")

    def test_prerecorded_mnn_batch_success_updates_recent_results(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        mnn_summary = {
            "status": "ok",
            "variant": "current",
            "selected_input_count": 2,
            "processed_count": 2,
            "sample_stats": {
                "run_ms": {"count": 2, "median_ms": 128.0, "mean_ms": 129.0},
                "total_ms": {"count": 2, "median_ms": 550.0, "mean_ms": 552.0},
            },
            "errors": [],
        }

        with patch.object(state, "_run_mnn_batch", return_value=mnn_summary):
            payload = state.start_mnn_batch_inference(count=2)

        self.assertEqual(payload["status"], "started")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            batch_state = state.get_batch_state()
            if batch_state.get("status") == "done":
                break
            time.sleep(0.02)
        else:
            self.fail(f"mnn batch did not finish: {state.get_batch_state()}")

        status, _, system_payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(system_payload["recent_results"]["mnn"]["job_id"], payload["batch_job_id"])
        self.assertEqual(system_payload["recent_results"]["current"]["job_id"], payload["batch_job_id"])
        self.assertEqual(system_payload["recent_results"]["mnn"]["wrapper_summary"]["inference_engine"], "mnn")
        self.assertEqual(system_payload["last_inference"]["variant"], "current")

    def test_usrp_stage_access_uses_qpsk_output_root(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        base_access = state._board_access.with_env_overrides(
            {
                "JSCC_LINK_MODE": "qpsk",
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                "REMOTE_OUTPUT_BASE": "/home/user/Downloads/jscc-test/jscc/infer_outputs",
                "INFERENCE_REAL_OUTPUT_PREFIX": "openamp3_handwritten_mean4_v7_direct",
            }
        )

        access = state._usrp_stage_access(
            base_access,
            {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx"},
        )
        env = access.build_env()

        self.assertEqual(env["OPENAMP_DEMO_INPUT_SOURCE_MODE"], "usrp")
        self.assertEqual(env["REMOTE_INPUT_SOURCE_MODE"], "usrp")
        self.assertEqual(env["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx")
        self.assertEqual(env["REMOTE_INPUT_DIR"], "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx")
        self.assertEqual(env["REMOTE_OUTPUT_BASE"], "/home/user/Downloads/jscc-test-usrp/qpsk/tvm")
        self.assertEqual(env["INFERENCE_REAL_OUTPUT_PREFIX"], "openamp3_usrp_123")
        self.assertEqual(env["BIG_LITTLE_OUTPUT_PREFIX"], "openamp3_usrp_123")
        self.assertEqual(env["BIG_LITTLE_REPORT_PREFIX"], "openamp3_usrp_123")

    def test_usrp_stage_access_uses_iq_direct_output_root(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        base_access = state._board_access.with_env_overrides({"JSCC_LINK_MODE": "iq-direct"})

        access = state._usrp_stage_access(
            base_access,
            {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx"},
        )

        self.assertEqual(
            access.build_env()["REMOTE_OUTPUT_BASE"],
            "/home/user/Downloads/jscc-test-usrp/iq-direct/tvm",
        )

    def test_usrp_tvm_stage_sets_big_little_input_wait_window(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        base_access = state._board_access.with_env_overrides(
            {
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                "JSCC_LINK_MODE": "iq-direct",
                "OPENAMP_IQ_STREAMING_TVM": "1",
                "OPENAMP_IQ_STREAMING_MIN_READY": "10",
                "OPENAMP_TVM_BATCH_RUNNER": "biglittle",
            }
        )
        captured: dict[str, str] = {}

        def fake_run_tvm(access, *, count, progress_callback):
            captured.update(access.build_env())
            progress_callback(count, count)
            return {"status": "ok", "processed_count": count, "selected_input_count": count}

        with patch.object(state, "_run_tvm_batch_with_access", side_effect=fake_run_tvm):
            callback = state._run_tvm_after_usrp_stage(base_access, count=300)
            result = callback(
                {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-789_rx"},
                lambda *_args: None,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["BIG_LITTLE_INPUT_WAIT_TIMEOUT_SEC"], "300.0")
        self.assertEqual(captured["BIG_LITTLE_INPUT_POLL_SEC"], "0.05")
        self.assertEqual(captured["BIG_LITTLE_INPUT_CHUNK_SIZE"], "10")

    def test_usrp_tvm_stage_clamps_iq_chunk_size_to_short_warmup_count(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        base_access = state._board_access.with_env_overrides(
            {
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                "JSCC_LINK_MODE": "iq-direct",
                "OPENAMP_IQ_STREAMING_TVM": "1",
                "OPENAMP_IQ_STREAMING_MIN_READY": "10",
                "BIG_LITTLE_INPUT_CHUNK_SIZE": "10",
                "OPENAMP_TVM_BATCH_RUNNER": "biglittle",
            }
        )
        captured: dict[str, str] = {}

        def fake_run_tvm(access, *, count, progress_callback):
            captured.update(access.build_env())
            progress_callback(count, count)
            return {"status": "ok", "processed_count": count, "selected_input_count": count}

        with patch.object(state, "_run_tvm_batch_with_access", side_effect=fake_run_tvm):
            callback = state._run_tvm_after_usrp_stage(base_access, count=5)
            result = callback(
                {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-789_rx"},
                lambda *_args: None,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["BIG_LITTLE_INPUT_CHUNK_SIZE"], "5")

    def test_usrp_stage_access_uses_separate_mnn_output_base(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        base_access = state._board_access.with_env_overrides(
            {
                "JSCC_LINK_MODE": "qpsk",
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                "REMOTE_OUTPUT_BASE": "/home/user/Downloads/jscc-test/mnn_benchmark_outputs",
            }
        )

        access = state._usrp_stage_access(
            base_access,
            {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-456_rx"},
            engine=server.INFERENCE_ENGINE_MNN,
        )
        env = access.build_env()

        self.assertEqual(env["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-456_rx")
        self.assertEqual(env["REMOTE_OUTPUT_BASE"], "/home/user/Downloads/jscc-test-usrp/qpsk/mnn")
        self.assertEqual(env["INFERENCE_REAL_OUTPUT_PREFIX"], "openamp3_usrp_456")

    def test_post_run_mnn_batch_uses_dashboard_state_entrypoint(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.object(
            state,
            "start_mnn_batch_inference",
            return_value={"status": "started", "batch_job_id": "mnn-demo-300", "total": 300, "engine": "mnn"},
        ) as start_mnn:
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-mnn-batch",
                body=json.dumps({"count": 300}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["engine"], "mnn")
        start_mnn.assert_called_once_with(count=300)

    def test_arm_mlkem_security_context_reuses_healthy_daemon_without_board_bootstrap(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        manager = Mock(is_alive=True, _handshake_ms=8.5)
        manager.ensure_alive.return_value = None
        manager.ping.return_value = {"status": "ok"}

        with (
            patch.object(state, "_get_mlkem_session_manager", return_value=manager),
            patch.object(
                state,
                "_ensure_board_tcp_server",
                side_effect=AssertionError("healthy daemon must skip board bootstrap"),
            ) as ensure_server,
        ):
            context, blocked = state._arm_mlkem_security_context(
                board_access=board_access,
                variant="current",
                image_index=0,
                expected_count=30,
            )

        ensure_server.assert_not_called()
        manager.ensure_alive.assert_called_once_with()
        manager.ping.assert_called_once_with()
        self.assertIsNone(blocked)
        self.assertEqual(context["protocol"], "mlkem_control")
        self.assertEqual(context["handshake_ms"], 8.5)

    def test_arm_mlkem_security_context_recovers_stale_daemon_with_board_bootstrap(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        stale_manager = Mock(is_alive=True, _handshake_ms=0.0)
        stale_manager.ensure_alive.side_effect = RuntimeError("stale channel")
        fresh_manager = Mock(is_alive=False, _handshake_ms=9.25)
        fresh_manager.ensure_alive.return_value = None
        fresh_manager.ping.return_value = {"status": "ok"}

        with (
            patch.object(
                state,
                "_get_mlkem_session_manager",
                side_effect=[stale_manager, fresh_manager],
            ),
            patch.object(state, "_close_mlkem_session_manager", return_value=True) as close_manager,
            patch.object(state, "_ensure_board_tcp_server", return_value=None) as ensure_server,
        ):
            context, blocked = state._arm_mlkem_security_context(
                board_access=board_access,
                variant="current",
                image_index=0,
                expected_count=30,
            )

        close_manager.assert_called_once_with()
        ensure_server.assert_called_once_with(board_access)
        fresh_manager.ensure_alive.assert_called_once_with()
        fresh_manager.ping.assert_called_once_with()
        self.assertIsNone(blocked)
        self.assertEqual(context["handshake_ms"], 9.25)

    def test_run_demo_inference_with_crypto_uses_standard_live_job_with_security_context(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = Mock(configured=True, probe_ready=False, connection_ready=True)

        fake_live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "control_transport": "hook",
                    "progress": {
                        "completed_count": 0,
                        "expected_count": 300,
                    },
                }
            ],
            job_id="live-job-001",
        )

        class FakeVariantAccess:
            def missing_inference_fields(self, variant: str) -> list[str]:
                del variant
                return []

        security_context = {
            "protocol": "mlkem_control",
            "handshake_ms": 12.3,
            "summary": "ML-KEM 安全协议已建立；Current 继续走板端本地 latent / 既有 live 数据面。",
            "channel_state": "ok",
        }

        with (
            patch.object(state, "_live_board_access_for_variant", return_value=FakeVariantAccess()),
            patch("server.expected_sha_for_variant", return_value="abcd" * 16),
            patch("server.describe_demo_variant_support", return_value={"mode": "signed_manifest_v1"}),
            patch.object(state, "_arm_mlkem_security_context", return_value=(security_context, None)),
            patch.object(state, "run_mlkem_inference", side_effect=AssertionError("legacy ML-KEM data path should not be used")),
            patch("server.launch_remote_reconstruction_job", return_value=fake_live_job) as launch_job,
        ):
            payload = state.run_demo_inference(variant="current", image_index=0)

        launch_job.assert_called_once()
        self.assertEqual(payload["job_id"], "live-job-001")
        self.assertEqual(payload["status"], "running")
        self.assertIn("ML-KEM 安全协议就绪", str(payload["source_label"]))
        self.assertIn("板端本地 latent", str(payload["message"]))
        security = payload.get("live_attempt", {}).get("security", {})
        self.assertEqual(security.get("protocol"), "mlkem_control")
        self.assertEqual(security.get("handshake_ms"), 12.3)

    def test_run_demo_inference_with_usrp_transport_uses_local_usrp_job_with_mlkem_control(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "transport_mode": "usrp"}).encode("utf-8"),
        )

        fake_live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "USRP 数据面 batch-spool 正在推进；界面继续使用归档样例图，无线链路指标来自当前 2922 运行时。",
                    "control_transport": "mlkem",
                    "data_transport": "usrp",
                    "control_handshake_complete": True,
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("USRP 混合链路在线推进", "running", 76, "USRP 数据面 76/300"),
                    "artifacts": {},
                }
            ],
            job_id="usrp-live-001",
        )
        security_context = {
            "protocol": "mlkem_control",
            "handshake_ms": 8.5,
            "summary": "ML-KEM 安全协议已建立；Current 继续走 USRP 数据面。",
            "channel_state": "ok",
        }

        with (
            patch.object(state, "_arm_mlkem_security_context", return_value=(security_context, None)),
            patch("server.launch_local_usrp_reconstruction_job", return_value=fake_live_job) as launch_usrp_job,
            patch("server.launch_remote_reconstruction_job", side_effect=AssertionError("OpenAMP live path should not be used in usrp mode")),
            patch("server.expected_sha_for_variant", side_effect=AssertionError("USRP mode should not require OpenAMP artifact sha gate")),
            patch("server.describe_demo_variant_support", side_effect=AssertionError("USRP mode should not inspect OpenAMP variant support")),
        ):
            payload = state.run_demo_inference(variant="current", image_index=0)

        launch_usrp_job.assert_called_once()
        _, kwargs = launch_usrp_job.call_args
        self.assertEqual(kwargs["variant"], "current")
        self.assertEqual(kwargs["control_transport"], "mlkem")
        self.assertEqual(payload["job_id"], "usrp-live-001")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["live_attempt"]["data_transport"], "usrp")
        self.assertIn("USRP 混合链路", str(payload["source_label"]))
        self.assertIn("2922", str(payload["message"]))
        security = payload.get("live_attempt", {}).get("security", {})
        self.assertEqual(security.get("protocol"), "mlkem_control")
        self.assertEqual(security.get("handshake_ms"), 8.5)

    def test_run_demo_inference_with_usrp_transport_blocks_when_mlkem_control_unavailable(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "transport_mode": "usrp"}).encode("utf-8"),
        )
        blocked_payload = state._build_blocked_inference_payload(
            variant="current",
            image_index=0,
            status_category="crypto_unavailable",
            source_label="ML-KEM 安全协议未就绪，回退展示（归档样例）",
            message="ML-KEM 安全协议未建立，本次按安全策略不发起 Current live 重建。",
            detail="auth verification failed",
            diagnostics={"crypto_enabled": True},
            expected_count=300,
        )

        with (
            patch.object(state, "_arm_mlkem_security_context", return_value=(None, blocked_payload)) as arm_security,
            patch("server.launch_local_usrp_reconstruction_job", side_effect=AssertionError("USRP data plane must not start without ML-KEM gate")) as launch_usrp_job,
            patch("server.launch_remote_reconstruction_job", side_effect=AssertionError("OpenAMP fallback should not launch for USRP crypto block")),
            patch("server.expected_sha_for_variant", side_effect=AssertionError("USRP mode should not inspect OpenAMP artifact sha gate")),
            patch("server.describe_demo_variant_support", side_effect=AssertionError("USRP mode should not inspect OpenAMP variant support")),
        ):
            payload = state.run_demo_inference(variant="current", image_index=0)

        arm_security.assert_called_once()
        launch_usrp_job.assert_not_called()
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["request_state"], "completed")
        self.assertEqual(payload["status_category"], "crypto_unavailable")
        self.assertEqual(payload["live_attempt"]["status"], "blocked")
        self.assertIn("不发起 Current live 重建", str(payload["message"]))

    def test_run_baseline_in_usrp_mode_keeps_pytorch_prerecorded_reference(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "transport_mode": "usrp"}).encode("utf-8"),
        )

        with (
            patch.object(state, "_arm_mlkem_security_context", side_effect=AssertionError("PyTorch reference should not arm USRP security")),
            patch("server.launch_local_usrp_reconstruction_job", side_effect=AssertionError("PyTorch reference should not launch USRP transport")) as launch_usrp_job,
        ):
            payload = state.run_demo_inference(variant="baseline", image_index=0)

        launch_usrp_job.assert_not_called()
        self.assertEqual(payload["variant"], "baseline")
        self.assertEqual(payload["execution_mode"], "prerecorded")
        self.assertEqual(payload["data_transport"], "prerecorded")
        self.assertIn("不走 USRP", str(payload["source_label"]))

    def test_run_baseline_in_prerecorded_mode_launches_direct_pytorch_reference(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "demo-pass",
                    "port": "22",
                    "transport_mode": "tcp",
                }
            ).encode("utf-8"),
        )

        fake_live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "baseline",
                    "control_transport": "none",
                    "data_transport": "tcp",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线执行（控制面降级）", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ],
            job_id="pytorch-baseline-direct-001",
        )

        with (
            patch("server.query_live_status", side_effect=AssertionError("PyTorch baseline should not use OpenAMP admission")),
            patch.object(state, "_arm_mlkem_security_context", side_effect=AssertionError("PyTorch baseline should not arm ML-KEM control")),
            patch("server.launch_remote_reconstruction_job", return_value=fake_live_job) as launch_job,
        ):
            payload = state.run_demo_inference(variant="baseline", image_index=0, max_inputs=300)

        launch_job.assert_called_once()
        _, kwargs = launch_job.call_args
        self.assertEqual(kwargs["variant"], "baseline")
        self.assertEqual(kwargs["max_inputs"], 300)
        self.assertEqual(kwargs["control_transport"], "none")
        self.assertEqual(payload["job_id"], "pytorch-baseline-direct-001")
        self.assertEqual(payload["variant"], "baseline")
        self.assertEqual(payload["status"], "running")

    def test_run_demo_inference_blocks_nontrusted_current_when_admission_stays_legacy_sha(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = Mock(configured=True, probe_ready=False, connection_ready=True)
        state._trusted_current_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"

        class FakeVariantAccess:
            def missing_inference_fields(self, variant: str) -> list[str]:
                del variant
                return []

        with (
            patch.object(state, "_live_board_access_for_variant", return_value=FakeVariantAccess()),
            patch(
                "server.expected_sha_for_variant",
                return_value="bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb",
            ),
            patch(
                "server.describe_demo_variant_support",
                return_value={"mode": "legacy_sha", "label": "Current live 仍走 legacy SHA", "launch_allowed": True},
            ),
            patch("server.launch_remote_reconstruction_job") as launch_job,
            patch("server.query_live_status") as status_probe,
        ):
            payload = state.run_demo_inference(variant="current", image_index=0)

        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["status_category"], "config_error")
        self.assertIn("signed-manifest admission", str(payload["message"]))
        self.assertIn("legacy SHA allowlist", str(payload["message"]))
        launch_job.assert_not_called()
        status_probe.assert_not_called()

    def test_run_mlkem_inference_subprocess_failure_completes_as_fallback(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        preflight = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
            "logs": [],
        }

        with (
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=None),
            patch("server.query_live_status", return_value=preflight),
            patch(
                "server.resolve_local_crypto_client",
                return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")]),
            ),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={
                    "supports_daemon": True,
                    "supports_count": True,
                    "supports_json_summary": True,
                    "supports_output": True,
                    "supports_expect_result": False,
                    "supports_batch_summary": True,
                    "legacy_single_input_only": False,
                },
            ),
            patch(
                "server.build_local_crypto_client_command",
                return_value=(["fake-python", "tcp_client.py"], {}),
            ),
            patch(
                "server.subprocess.Popen",
                return_value=FakePopen(stderr_text="simulated subprocess failure", returncode=1),
            ),
        ):
            start_payload = state.run_mlkem_inference(variant="current", image_index=0, max_inputs=1)
            self.assertEqual(start_payload["request_state"], "running")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                progress = state.get_inference_progress(str(start_payload["job_id"]))
                if progress.get("request_state") == "completed":
                    break
                time.sleep(0.02)
            else:
                self.fail("ML-KEM subprocess failure path stayed in running state")

        self.assertEqual(progress["status"], "fallback")
        self.assertEqual(progress["request_state"], "completed")
        self.assertEqual(progress["live_progress"]["state"], "fallback")
        self.assertIn("ML-KEM 批量失败", progress["live_progress"]["event_log"][0])

    def test_run_mlkem_inference_daemon_fallback_preserves_completed_count(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        state._last_control_status = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
            "logs": [],
        }

        class FakeMgr:
            def __init__(self) -> None:
                self.is_alive = True
                self._host = "demo-board"
                self._client_script = Path("/tmp/tcp_client.py")
                self._handshake_ms = 9.0
                self._calls = 0

            def ensure_alive(self) -> None:
                return None

            def send_image(
                self,
                input_path: str,
                job_id: str,
                *,
                run_tvm: bool = False,
                expect_result: bool = False,
            ) -> dict[str, object]:
                del input_path, job_id, expect_result
                self.run_tvm = run_tvm
                self._calls += 1
                if self._calls == 1:
                    return {
                        "status": "ok",
                        "sha256_match": True,
                        "result_received": True,
                        "inference_ms": 5.0,
                        "total_ms": 8.0,
                    }
                raise RuntimeError("daemon link lost")

        fake_mgr = FakeMgr()

        with (
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=fake_mgr),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={
                    "supports_daemon": True,
                    "supports_count": True,
                    "supports_json_summary": True,
                    "supports_output": True,
                    "supports_expect_result": True,
                    "supports_batch_summary": True,
                    "legacy_single_input_only": False,
                },
            ),
            patch(
                "server.build_local_crypto_client_command",
                return_value=(["fake-python", "tcp_client.py"], {}),
            ),
            patch(
                "server.subprocess.Popen",
                return_value=FakePopen(
                    stdout_lines=[
                        "✓ remain-1\n",
                        "✓ remain-2\n",
                        '{"success": 2, "total": 2, "handshake_ms": 7.0, "per_image_ms": 11.0}\n',
                    ],
                    returncode=0,
                ),
            ) as popen_mock,
        ):
            start_payload = state.run_mlkem_inference(variant="current", image_index=0, max_inputs=3)
            self.assertEqual(start_payload["request_state"], "running")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                progress = state.get_inference_progress(str(start_payload["job_id"]))
                if progress.get("request_state") == "completed":
                    break
                time.sleep(0.02)
            else:
                self.fail("ML-KEM daemon fallback path did not finish")

        self.assertEqual(progress["status"], "success")
        self.assertEqual(progress["live_progress"]["completed_count"], 3)
        self.assertAlmostEqual(progress["timings"]["payload_ms"], 5.0)
        self.assertAlmostEqual(progress["timings"]["total_ms"], 18.0)
        popen_cmd = " ".join(popen_mock.call_args.args[0])
        self.assertIn("--run-tvm", popen_cmd)
        self.assertNotIn("--expect-result", popen_cmd)

    def test_run_mlkem_inference_daemon_requires_board_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        state._last_control_status = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
            "logs": [],
        }

        class FakeMgr:
            def __init__(self) -> None:
                self.is_alive = True
                self._host = "demo-board"
                self._client_script = Path("/tmp/tcp_client.py")
                self._handshake_ms = 9.0

            def ensure_alive(self) -> None:
                return None

            def send_image(
                self,
                input_path: str,
                job_id: str,
                *,
                run_tvm: bool = False,
                expect_result: bool = False,
            ) -> dict[str, object]:
                del input_path, job_id
                self.run_tvm = run_tvm
                self.expect_result = expect_result
                return {
                    "status": "ok",
                    "sha256_match": True,
                    "result_received": False,
                    "inference_ms": None,
                    "total_ms": 8.0,
                }

        fake_mgr = FakeMgr()

        with (
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=fake_mgr),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={
                    "supports_daemon": True,
                    "supports_count": True,
                    "supports_json_summary": True,
                    "supports_output": True,
                    "supports_expect_result": True,
                    "supports_batch_summary": True,
                    "legacy_single_input_only": False,
                },
            ),
        ):
            start_payload = state.run_mlkem_inference(variant="current", image_index=0, max_inputs=1)
            self.assertEqual(start_payload["request_state"], "running")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                progress = state.get_inference_progress(str(start_payload["job_id"]))
                if progress.get("request_state") == "completed":
                    break
                time.sleep(0.02)
            else:
                self.fail("ML-KEM daemon missing-result path did not finish")

        self.assertTrue(fake_mgr.run_tvm)
        self.assertTrue(fake_mgr.expect_result)
        self.assertEqual(progress["status"], "fallback")
        self.assertIn("未收到板端重建结果", progress["message"])

    def test_reset_crypto_channel_closes_session_and_schedules_remote_restart_for_tcp(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        fake_mgr = Mock()
        state._mlkem_session_mgr = fake_mgr
        state._crypto_status_cache = {"channel_state": "ok"}
        state._crypto_status_cache_ts = 123.0

        fake_thread = Mock()
        fake_thread.start = Mock()

        with patch("server.threading.Thread", return_value=fake_thread) as thread_ctor:
            payload = state.reset_crypto_channel()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["session_closed"])
        self.assertTrue(payload["remote_restart_scheduled"])
        fake_mgr.close.assert_called_once_with()
        self.assertIsNone(state._mlkem_session_mgr)
        self.assertIsNone(state._crypto_status_cache)
        self.assertEqual(state._crypto_status_cache_ts, 0.0)
        thread_ctor.assert_called_once()
        fake_thread.start.assert_called_once_with()

    def test_get_mlkem_session_manager_replaces_mismatched_existing_manager(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        env_values = {"MLKEM_TRANSPORT_MODE": "tcp"}
        old_mgr = Mock()
        old_mgr.matches_config.return_value = False
        state._mlkem_session_mgr = old_mgr
        new_mgr = Mock()

        with (
            patch("server.resolve_local_crypto_client", return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")])),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={"supports_daemon": True},
            ),
            patch("server.MlkemSessionManager", return_value=new_mgr) as mgr_ctor,
        ):
            mgr = state._get_mlkem_session_manager(board_access, env_values)

        self.assertIs(mgr, new_mgr)
        old_mgr.close.assert_called_once_with()
        mgr_ctor.assert_called_once_with(env_values, host="demo-board", client_script=Path("/tmp/tcp_client.py"))

    def test_crypto_reset_endpoint_calls_dashboard_state(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.object(
            state,
            "reset_crypto_channel",
            return_value={"status": "ok", "message": "reset ok"},
        ) as reset_crypto_channel:
            status, _, payload = request_json(
                state,
                "POST",
                "/api/crypto-reset",
                body=json.dumps({"restart_remote_server": False}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        reset_crypto_channel.assert_called_once_with(restart_remote_server=False)

    def test_run_mlkem_inference_legacy_client_compatibility_caps_single_launch(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        preflight = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
            "logs": [],
        }
        run_calls: list[list[str]] = []

        def fake_run(
            cmd: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: float,
            env: dict[str, str],
        ):
            del capture_output, text, timeout, env
            run_calls.append(list(cmd))
            self.assertNotIn("--daemon", cmd)
            self.assertNotIn("--count", cmd)
            self.assertNotIn("--json-summary", cmd)
            input_path = Path(cmd[cmd.index("--input") + 1])
            self.assertEqual(input_path.stat().st_size, 1 * 3 * 64 * 64 * 4)
            stdout = "\n".join(
                [
                    "密码套件:  SM4_GCM",
                    "KEM 后端:  mock-backend",
                    "握手完成: 9.0ms",
                    "加密发送: 49152B, 耗时 3.0ms",
                    "✓ 传输成功",
                    "  对端 SHA256 匹配: 是",
                    "  TVM 推理耗时: 21.0ms",
                    "  接收重建结果: 49152B, 耗时 4.0ms",
                ]
            )
            return server.subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

        with (
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch("server.query_live_status", return_value=preflight),
            patch(
                "server.resolve_local_crypto_client",
                return_value=(Path("/tmp/legacy_tcp_client.py"), [Path("/tmp/legacy_tcp_client.py")]),
            ),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={
                    "supports_daemon": False,
                    "supports_count": False,
                    "supports_json_summary": False,
                    "supports_output": True,
                    "supports_expect_result": False,
                    "supports_batch_summary": False,
                    "legacy_single_input_only": True,
                },
            ),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", "tcp_client.py", "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch("server.subprocess.run", side_effect=fake_run),
        ):
            start_payload = state.run_mlkem_inference(variant="current", image_index=0)
            self.assertEqual(start_payload["request_state"], "running")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                progress = state.get_inference_progress(str(start_payload["job_id"]))
                if progress.get("request_state") == "completed":
                    break
                time.sleep(0.02)
            else:
                self.fail("ML-KEM legacy compatibility path did not finish")

        self.assertEqual(len(run_calls), 1)
        self.assertEqual(progress["status"], "success")
        self.assertEqual(progress["live_progress"]["completed_count"], 1)
        self.assertEqual(progress["live_progress"]["expected_count"], 1)
        self.assertAlmostEqual(progress["timings"]["payload_ms"], 21.0)
        self.assertAlmostEqual(progress["timings"]["total_ms"], 37.0)

    def test_run_mlkem_inference_legacy_client_requires_reconstruction_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        preflight = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
            "logs": [],
        }

        def fake_run(
            cmd: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: float,
            env: dict[str, str],
        ):
            del capture_output, text, timeout, env
            self.assertIn("--expect-result", cmd)
            stdout = "\n".join(
                [
                    "密码套件:  SM4_GCM",
                    "KEM 后端:  mock-backend",
                    "握手完成: 9.0ms",
                    "加密发送: 49152B, 耗时 3.0ms",
                    "✓ 传输成功",
                    "  对端 SHA256 匹配: 是",
                    "  板端重建结果: 未回传",
                ]
            )
            return server.subprocess.CompletedProcess(cmd, 2, stdout=stdout, stderr="")

        with (
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch("server.query_live_status", return_value=preflight),
            patch(
                "server.resolve_local_crypto_client",
                return_value=(Path("/tmp/local_wrapper_tcp_client.py"), [Path("/tmp/local_wrapper_tcp_client.py")]),
            ),
            patch(
                "server.inspect_local_crypto_client_capabilities",
                return_value={
                    "supports_daemon": False,
                    "supports_count": False,
                    "supports_json_summary": False,
                    "supports_output": True,
                    "supports_expect_result": True,
                    "supports_batch_summary": False,
                    "legacy_single_input_only": True,
                },
            ),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", "tcp_client.py", "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch("server.subprocess.run", side_effect=fake_run),
        ):
            start_payload = state.run_mlkem_inference(variant="current", image_index=0)
            self.assertEqual(start_payload["request_state"], "running")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                progress = state.get_inference_progress(str(start_payload["job_id"]))
                if progress.get("request_state") == "completed":
                    break
                time.sleep(0.02)
            else:
                self.fail("ML-KEM legacy result-required path did not finish")

        self.assertEqual(progress["status"], "fallback")
        self.assertIn("板端重建结果: 未回传", progress["message"])
        self.assertEqual(progress["live_progress"]["expected_count"], 1)
        self.assertEqual(progress["live_progress"]["count_label"], "0 / 1")
        self.assertIsNone(progress["timings"]["payload_ms"])
        self.assertIsNone(progress["timings"]["total_ms"])
        self.assertEqual(progress["timings"]["stages"], [])

        status, _, system_payload = request_json(state, "GET", "/api/system-status")
        self.assertEqual(status, 200)
        self.assertIsNone(system_payload["recent_results"]["current"]["timings"]["payload_ms"])
        self.assertIsNone(system_payload["recent_results"]["current"]["timings"]["total_ms"])

    def test_ensure_board_aircraft_position_bridge_uploads_assets_and_enables_service(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "AIRCRAFT_POSITION_UPSTREAM_URL": "http://127.0.0.1:9000/gps",
                    "AIRCRAFT_POSITION_BACKEND_BASE_URL": "http://demo-host:8079",
                    "AIRCRAFT_POSITION_GROUND_SPEED_SCALE": "3.6",
                }
            ),
        )
        uploaded: dict[str, dict[str, object]] = {}

        def fake_write_remote_text_file(
            _board_access: server.BoardAccessConfig,
            *,
            remote_path: str,
            content: str,
            mode: int,
            timeout: float,
        ) -> None:
            del _board_access, timeout
            uploaded[remote_path] = {"content": content, "mode": mode}

        with (
            patch.object(state, "_write_remote_text_file", side_effect=fake_write_remote_text_file),
            patch(
                "server.run_ssh_command",
                return_value=server.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            ) as run_ssh,
        ):
            state._ensure_board_aircraft_position_bridge(board_access)

        remote_paths = server._aircraft_position_bridge_remote_paths(server.DEFAULT_AIRCRAFT_POSITION_REMOTE_ROOT)
        self.assertIn(remote_paths["env_file"], uploaded)
        self.assertIn(
            "AIRCRAFT_POSITION_UPSTREAM_URL=http://127.0.0.1:9000/gps",
            uploaded[remote_paths["env_file"]]["content"],
        )
        self.assertIn(
            "AIRCRAFT_POSITION_BACKEND_BASE_URL=http://demo-host:8079",
            uploaded[remote_paths["env_file"]]["content"],
        )
        self.assertEqual(uploaded[remote_paths["env_file"]]["mode"], 0o600)
        self.assertIn(remote_paths["user_service"], uploaded)
        self.assertIn(
            "systemctl --user enable --now aircraft-position-bridge.service",
            run_ssh.call_args.kwargs["remote_command"],
        )

    def test_ensure_board_position_api_service_uploads_assets_and_launches_service(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        uploaded: dict[str, dict[str, object]] = {}

        def fake_write_remote_text_file(
            _board_access: server.BoardAccessConfig,
            *,
            remote_path: str,
            content: str,
            mode: int,
            timeout: float,
        ) -> None:
            del _board_access, timeout
            uploaded[remote_path] = {"content": content, "mode": mode}

        with (
            patch.object(state, "_write_remote_text_file", side_effect=fake_write_remote_text_file),
            patch(
                "server.run_ssh_command",
                return_value=server.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            ) as run_ssh,
        ):
            state._ensure_board_position_api_service(board_access)

        remote_paths = server._board_position_api_remote_paths(server.DEFAULT_BOARD_POSITION_API_REMOTE_ROOT)
        self.assertIn(remote_paths["env_file"], uploaded)
        self.assertIn("BOARD_POSITION_API_BIND_HOST=127.0.0.1", uploaded[remote_paths["env_file"]]["content"])
        self.assertIn("BOARD_POSITION_API_PORT=9000", uploaded[remote_paths["env_file"]]["content"])
        self.assertIn(remote_paths["user_service"], uploaded)
        self.assertEqual(run_ssh.call_count, 1)
        self.assertIn("sudo -S -k bash -lc", run_ssh.call_args.kwargs["remote_command"])
        self.assertIn("nohup", run_ssh.call_args.kwargs["remote_command"])
        self.assertIn("run_board_position_api_service.sh", run_ssh.call_args.kwargs["remote_command"])
        self.assertIn("$PY -c", run_ssh.call_args.kwargs["remote_command"])
        self.assertIn("base64.b64decode", run_ssh.call_args.kwargs["remote_command"])

    def test_ensure_board_position_api_service_propagates_external_http_position_env(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        ).with_env_overrides(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
                "AIRCRAFT_POSITION_SOURCE_LABEL": "百度IP定位",
            }
        )
        uploaded: dict[str, str] = {}

        def fake_write_remote_text_file(
            _board_access: server.BoardAccessConfig,
            *,
            remote_path: str,
            content: str,
            mode: int,
            timeout: float,
        ) -> None:
            del _board_access, mode, timeout
            uploaded[remote_path] = content

        with (
            patch.object(state, "_write_remote_text_file", side_effect=fake_write_remote_text_file),
            patch(
                "server.run_ssh_command",
                return_value=server.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            ),
        ):
            state._ensure_board_position_api_service(board_access)

        remote_paths = server._board_position_api_remote_paths(server.DEFAULT_BOARD_POSITION_API_REMOTE_ROOT)
        env_content = uploaded[remote_paths["env_file"]]
        self.assertIn("export AIRCRAFT_POSITION_UPSTREAM_URL=", env_content)
        self.assertIn("api.map.baidu.com/location/ip", env_content)
        self.assertIn("export AIRCRAFT_POSITION_LATITUDE_PATH=content.point.y", env_content)
        self.assertIn("export AIRCRAFT_POSITION_LONGITUDE_PATH=content.point.x", env_content)
        self.assertIn("export BOARD_POSITION_API_SOURCE_ORDER=http,gpsd,nmea", env_content)

    def test_ensure_board_position_api_service_reports_launch_failure(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with (
            patch.object(state, "_write_remote_text_file", return_value=None),
            patch(
                "server.run_ssh_command",
                side_effect=[
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="sudo failed"),
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="systemd failed"),
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="fallback failed"),
                ],
            ) as run_ssh,
            patch("builtins.print") as print_mock,
        ):
            state._ensure_board_position_api_service(board_access)

        self.assertEqual(run_ssh.call_count, 3)
        self.assertIn("sudo -S -k bash -lc", run_ssh.call_args_list[0].kwargs["remote_command"])
        self.assertIn("nohup", run_ssh.call_args_list[1].kwargs["remote_command"])
        self.assertIn(
            "systemctl --user enable --now board-position-api.service",
            run_ssh.call_args_list[2].kwargs["remote_command"],
        )
        self.assertIn("$PY -c", run_ssh.call_args_list[2].kwargs["remote_command"])
        self.assertIn("base64.b64decode", run_ssh.call_args_list[2].kwargs["remote_command"])
        print_mock.assert_called()

    def test_ensure_board_position_api_service_falls_back_to_systemd_when_direct_launch_fails(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with (
            patch.object(state, "_write_remote_text_file", return_value=None),
            patch(
                "server.run_ssh_command",
                side_effect=[
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="root launch failed"),
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="direct launch failed"),
                    server.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                ],
            ) as run_ssh,
        ):
            state._ensure_board_position_api_service(board_access)

        self.assertEqual(run_ssh.call_count, 3)
        self.assertIn("sudo -S -k bash -lc", run_ssh.call_args_list[0].kwargs["remote_command"])
        self.assertIn("nohup", run_ssh.call_args_list[1].kwargs["remote_command"])
        self.assertIn(
            "systemctl --user enable --now board-position-api.service",
            run_ssh.call_args_list[2].kwargs["remote_command"],
        )

    def test_aircraft_bridge_runtime_auto_derives_backend_base_url_when_server_binds_publicly(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "AIRCRAFT_POSITION_UPSTREAM_URL": "http://127.0.0.1:9000/gps",
                }
            ),
        )

        with patch(
            "server._default_backend_base_url_for_board",
            return_value="http://100.116.93.120:8079",
        ):
            runtime = server._aircraft_position_bridge_runtime(
                board_access,
                bind_host=state._bind_host,
                bind_port=state._bind_port,
            )

        self.assertTrue(runtime["configured"])
        self.assertEqual(runtime["backend_base_url"], "http://100.116.93.120:8079")
        self.assertEqual(
            runtime["runtime_env"]["AIRCRAFT_POSITION_BACKEND_BASE_URL"],
            "http://100.116.93.120:8079",
        )

    def test_aircraft_bridge_runtime_uses_auto_discovered_upstream_url(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with patch(
            "server._default_backend_base_url_for_board",
            return_value="http://100.116.93.120:8079",
        ):
            runtime = server._aircraft_position_bridge_runtime(
                board_access,
                bind_host=state._bind_host,
                bind_port=state._bind_port,
                discovered_upstream_url="http://127.0.0.1:9527/api/v1/position",
            )

        self.assertTrue(runtime["configured"])
        self.assertEqual(runtime["upstream_url"], "http://127.0.0.1:9527/api/v1/position")
        self.assertEqual(runtime["upstream_url_source"], "auto_discovered")
        self.assertEqual(
            runtime["runtime_env"]["AIRCRAFT_POSITION_UPSTREAM_URL"],
            "http://127.0.0.1:9527/api/v1/position",
        )

    def test_autostart_board_aircraft_position_bridge_uses_discovered_upstream_url(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with (
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "detected",
                    "selected_url": "http://127.0.0.1:9527/api/v1/position",
                    "selected_source": "auto_discovered",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [],
                },
            ),
            patch(
                "server._default_backend_base_url_for_board",
                return_value="http://100.116.93.120:8079",
            ),
            patch.object(state, "_ensure_board_aircraft_position_bridge") as ensure_bridge,
        ):
            state._autostart_board_aircraft_position_bridge(board_access)

        effective_board_access = ensure_bridge.call_args.args[0]
        self.assertEqual(
            effective_board_access.build_env()["AIRCRAFT_POSITION_UPSTREAM_URL"],
            "http://127.0.0.1:9527/api/v1/position",
        )

    def test_autostart_board_aircraft_position_bridge_starts_board_position_api_first(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        order: list[str] = []

        with (
            patch.object(state, "_ensure_board_position_api_service", side_effect=lambda *_args, **_kwargs: order.append("position_api")),
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "detected",
                    "selected_url": "http://127.0.0.1:9000/api/v1/position",
                    "selected_source": "auto_discovered",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [],
                },
            ),
            patch(
                "server._default_backend_base_url_for_board",
                return_value="http://100.116.93.120:8079",
            ),
            patch.object(state, "_ensure_board_aircraft_position_bridge", side_effect=lambda *_args, **_kwargs: order.append("bridge")),
        ):
            state._autostart_board_aircraft_position_bridge(board_access)

        self.assertEqual(order, ["position_api", "bridge"])

    def test_ensure_board_aircraft_position_bridge_falls_back_to_nohup_when_systemd_user_fails(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "AIRCRAFT_POSITION_UPSTREAM_URL": "http://127.0.0.1:9000/gps",
                    "AIRCRAFT_POSITION_BACKEND_BASE_URL": "http://demo-host:8079",
                }
            ),
        )

        with (
            patch.object(state, "_write_remote_text_file", return_value=None),
            patch(
                "server.run_ssh_command",
                side_effect=[
                    server.subprocess.CompletedProcess([], 1, stdout="", stderr="systemd user bus unavailable"),
                    server.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                ],
            ) as run_ssh,
        ):
            state._ensure_board_aircraft_position_bridge(board_access)

        self.assertEqual(run_ssh.call_count, 2)
        self.assertIn(
            "systemctl --user enable --now aircraft-position-bridge.service",
            run_ssh.call_args_list[0].kwargs["remote_command"],
        )
        self.assertIn("nohup", run_ssh.call_args_list[1].kwargs["remote_command"])

    def test_ensure_board_tcp_server_uses_remote_home_tcp_server_when_mlkem_path_unspecified(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        captured: dict[str, object] = {}

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            if remote_command == 'printf %s "$HOME"':
                return server.subprocess.CompletedProcess([], 0, stdout="/home/demo-user", stderr="")
            captured.setdefault("commands", []).append(remote_command)
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def fake_build_remote_crypto_server_command(env_values: dict[str, str], *, local_server_script: Path | None = None) -> str:
            del local_server_script
            captured["env_values"] = dict(env_values)
            return "echo start-remote-server"

        with (
            patch("server.fetch_json_direct", side_effect=RuntimeError("status down")),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/ICCompetition2026/scripts/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", side_effect=fake_build_remote_crypto_server_command),
            patch("server.time.sleep", return_value=None),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertEqual(captured["env_values"]["MLKEM_REMOTE_SERVER_SCRIPT"], "/home/demo-user/tcp_server.py")
        self.assertIn("echo start-remote-server", captured["commands"])

    def test_ensure_board_tcp_server_strips_ansi_from_remote_home(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides({"MLKEM_STATUS_STARTUP_WAIT_SEC": "2"}),
        )
        captured: dict[str, object] = {}

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            if remote_command == 'printf %s "$HOME"':
                return server.subprocess.CompletedProcess(
                    [],
                    0,
                    stdout="/home/demo-user\x1b[?9001l\x1b[?1004l\n",
                    stderr="",
                )
            captured.setdefault("commands", []).append(remote_command)
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def fake_build_remote_crypto_server_command(env_values: dict[str, str], *, local_server_script: Path | None = None) -> str:
            del local_server_script
            captured["env_values"] = dict(env_values)
            return "echo start-remote-server"

        with (
            patch("server.fetch_json_direct", side_effect=RuntimeError("status down")),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/ICCompetition2026/scripts/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", side_effect=fake_build_remote_crypto_server_command),
            patch("server.time.sleep", return_value=None),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertEqual(captured["env_values"]["MLKEM_REMOTE_SERVER_SCRIPT"], "/home/demo-user/tcp_server.py")
        self.assertIn("echo start-remote-server", captured["commands"])

    def test_ensure_board_tcp_server_restarts_when_running_process_uses_shell_wrapped_tvm_python(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py",
                    "REMOTE_TVM_PYTHON": "env FOO=1 /opt/tvm/bin/python",
                }
            ),
        )
        captured: list[str] = []

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            captured.append(remote_command)
            if remote_command == "pgrep -af 'tcp_server.py' || true":
                return server.subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=(
                        "257019 /home/user/anaconda3/envs/mlkem/bin/python "
                        "/home/user/tcp_server.py --tvm --tvm-python env FOO=1 /opt/tvm/bin/python\n"
                    ),
                    stderr="",
                )
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with (
            patch(
                "server.fetch_json_direct",
                side_effect=[
                    {"cipher_suite": "sm4-gcm"},
                    {"cipher_suite": "sm4-gcm"},
                ],
            ),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", return_value="echo restart-remote-server"),
            patch("server.time.sleep", return_value=None),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertIn("pgrep -af 'tcp_server.py' || true", captured)
        self.assertIn("pkill -f 'tcp_server.py' || true", captured)
        self.assertIn("echo restart-remote-server", captured)

    def test_ensure_board_tcp_server_restarts_when_auth_status_mismatches(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py",
                    "MLKEM_AUTH_ENABLED": "1",
                    "MLKEM_AUTH_SIG_POLICY": "DUAL_REQUIRED",
                    "MLKEM_AUTH_SERVER_ID": "phytium-board",
                }
            ),
        )
        captured: list[str] = []

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            captured.append(remote_command)
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with (
            patch(
                "server.fetch_json_direct",
                side_effect=[
                    {
                        "cipher_suite": "sm4-gcm",
                        "auth_enabled": False,
                        "sig_policy": "",
                        "server_id": "",
                    },
                    {
                        "cipher_suite": "sm4-gcm",
                        "auth_enabled": True,
                        "sig_policy": "DUAL_REQUIRED",
                        "server_id": "phytium-board",
                    },
                ],
            ),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", return_value="echo restart-remote-server"),
            patch("server.time.sleep", return_value=None),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertIn("pkill -f 'tcp_server.py' || true", captured)
        self.assertIn("echo restart-remote-server", captured)

    def test_ensure_board_tcp_server_keeps_running_process_when_normalized_tvm_python_matches(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py",
                    "REMOTE_TVM_PYTHON": (
                        "env OMP_NUM_THREADS=3 TVM_NUM_THREADS=3 "
                        "/opt/tvm/bin/python"
                    ),
                }
            ),
        )
        captured: list[str] = []

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            captured.append(remote_command)
            if remote_command == "pgrep -af 'tcp_server.py' || true":
                return server.subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=(
                        "257019 /home/user/anaconda3/envs/mlkem/bin/python "
                        "/home/user/tcp_server.py --tvm --tvm-python /opt/tvm/bin/python\n"
                    ),
                    stderr="",
                )
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with (
            patch("server.fetch_json_direct", return_value={"cipher_suite": "sm4-gcm"}),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", return_value="echo restart-remote-server") as build_cmd,
            patch("server.time.sleep", return_value=None),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertIn("pgrep -af 'tcp_server.py' || true", captured)
        self.assertNotIn("pkill -f 'tcp_server.py' || true", captured)
        build_cmd.assert_not_called()

    def test_ensure_board_tcp_server_restarts_stale_process_when_status_port_down(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py",
                    "MLKEM_STATUS_STARTUP_WAIT_SEC": "2",
                }
            ),
        )
        captured: list[str] = []
        monotonic_value = {"value": 0.0}

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            captured.append(remote_command)
            if remote_command == "pgrep -af 'tcp_server.py' || true":
                return server.subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=(
                        "257019 /home/user/anaconda3/envs/mlkem/bin/python "
                        "/home/demo-user/tcp_server.py --status-port 8080\n"
                    ),
                    stderr="",
                )
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def fake_fetch_json_direct(*args: object, **kwargs: object):
            del args, kwargs
            if any("echo restart-remote-server" in command for command in captured):
                return {"cipher_suite": "sm4-gcm"}
            raise RuntimeError("status down")

        def fake_monotonic() -> float:
            monotonic_value["value"] += 10.0
            return monotonic_value["value"]

        with (
            patch("server.fetch_json_direct", side_effect=fake_fetch_json_direct),
            patch("server.resolve_local_crypto_server", return_value=(Path("/tmp/tcp_server.py"), [])),
            patch.object(state, "_sync_remote_mlkem_server_assets", return_value={"updated": False}),
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.build_remote_crypto_server_command", return_value="echo restart-remote-server"),
            patch("server.time.sleep", return_value=None),
            patch("server.time.monotonic", side_effect=fake_monotonic),
        ):
            state._ensure_board_tcp_server(board_access)

        self.assertIn("pgrep -af 'tcp_server.py' || true", captured)
        self.assertIn("pkill -f 'tcp_server.py' || true", captured)
        self.assertIn("echo restart-remote-server", captured)

    def test_sync_remote_mlkem_server_assets_uploads_server_helper_and_mlkem_link_once(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            scripts_dir = project_dir / "scripts"
            scripts_dir.mkdir()
            package_dir = project_dir / "mlkem_link"
            package_dir.mkdir()
            local_server_script = scripts_dir / "tcp_server.py"
            local_helper_script = scripts_dir / "tvm_inference_helper.py"
            local_server_script.write_text("#!/usr/bin/env python3\nprint('server')\n", encoding="utf-8")
            local_helper_script.write_text("#!/usr/bin/env python3\nprint('helper')\n", encoding="utf-8")
            (scripts_dir / "latent_transport.py").write_text("HELPER = 'latent'\n", encoding="utf-8")
            (scripts_dir / "run_logger.py").write_text("HELPER = 'logger'\n", encoding="utf-8")
            (package_dir / "__init__.py").write_text("PACKAGE = True\n", encoding="utf-8")
            (package_dir / "kem.py").write_text("def demo():\n    return 'kem'\n", encoding="utf-8")
            uploads: list[str] = []

            def fake_write_remote_text_file(
                _board_access: server.BoardAccessConfig,
                *,
                remote_path: str,
                content: str,
                mode: int,
                timeout: float,
            ) -> None:
                del _board_access, content, mode, timeout
                uploads.append(remote_path)

            with patch.object(state, "_write_remote_text_file", side_effect=fake_write_remote_text_file):
                first = state._sync_remote_mlkem_server_assets(
                    board_access,
                    runtime_env_values={"MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py"},
                    local_server_script=local_server_script,
                )
                second = state._sync_remote_mlkem_server_assets(
                    board_access,
                    runtime_env_values={"MLKEM_REMOTE_SERVER_SCRIPT": "/home/demo-user/tcp_server.py"},
                    local_server_script=local_server_script,
                )

        self.assertTrue(first["updated"])
        self.assertFalse(second["updated"])
        self.assertEqual(
            uploads,
            [
                "/home/demo-user/tcp_server.py",
                "/home/demo-user/tvm_inference_helper.py",
                "/home/demo-user/latent_transport.py",
                "/home/demo-user/run_logger.py",
                "/home/demo-user/mlkem_link/__init__.py",
                "/home/demo-user/mlkem_link/kem.py",
            ],
        )

    def test_write_remote_text_file_uses_scp_instead_of_embedding_large_content(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        large_content = "PAYLOAD-CONTENT-" * 6000
        ssh_commands: list[str] = []
        scp_calls: list[dict[str, object]] = []

        def fake_run_ssh_command(*, remote_command: str, **kwargs: object):
            del kwargs
            ssh_commands.append(remote_command)
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def fake_run_scp_file(**kwargs: object):
            local_path = Path(str(kwargs["local_path"]))
            scp_calls.append({**kwargs, "uploaded_content": local_path.read_text(encoding="utf-8")})
            return server.subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with (
            patch("server.run_ssh_command", side_effect=fake_run_ssh_command),
            patch("server.run_scp_file", side_effect=fake_run_scp_file),
        ):
            state._write_remote_text_file(
                board_access,
                remote_path="/home/demo-user/tcp_server.py",
                content=large_content,
                mode=0o755,
                timeout=25.0,
            )

        self.assertEqual(len(scp_calls), 1)
        self.assertEqual(scp_calls[0]["uploaded_content"], large_content)
        self.assertTrue(str(scp_calls[0]["remote_path"]).startswith("/home/demo-user/.tcp_server.py."))
        self.assertEqual(len(ssh_commands), 2)
        self.assertLess(max(len(command) for command in ssh_commands), 2000)
        self.assertNotIn(large_content[:200], "\n".join(ssh_commands))

    def test_get_crypto_status_fetches_board_status_without_proxy(self) -> None:
        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return self._payload

        class FakeOpener:
            def __init__(self) -> None:
                self.seen_request = None
                self.seen_timeout = None

            def open(self, request, *, timeout: float):
                self.seen_request = request
                self.seen_timeout = timeout
                return FakeResponse(
                    json.dumps(
                        {
                            "channel_state": "ready",
                            "kem_backend": "tongsuo-ML-KEM-768",
                            "cipher_suite": "aes-256-gcm",
                        }
                    ).encode("utf-8")
                )

        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides({"MLKEM_STATUS_PORT": "18080"}),
        )
        state._crypto_enabled = True
        fake_opener = FakeOpener()

        with patch("server.build_opener", return_value=fake_opener) as build_opener:
            payload = state.get_crypto_status()

        build_opener.assert_called_once()
        self.assertEqual(fake_opener.seen_request.full_url, "http://100.121.87.73:18080/status")
        self.assertEqual(fake_opener.seen_timeout, 3)
        self.assertEqual(payload["channel_state"], "ready")
        self.assertEqual(payload["kem_backend"], "tongsuo-ML-KEM-768")
        self.assertEqual(payload["enabled"], True)
        self.assertEqual(payload["board_configured"], True)

    def test_get_crypto_status_reports_linked_service_mode_on_live(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        payload = state.get_crypto_status()

        self.assertIn("service_mode", payload)
        self.assertEqual(
            payload["service_mode"],
            {
                "available": True,
                "source": "live_linked",
                "current_mode": "FULL_FRAME",
                "allowed_mode": "FULL_FRAME",
                "payload_strategy": "Full Frame tensor",
                "mode_transitions": 1,
                "last_transition": "Link Director Event",
                "note": "上位机守护进程已通过 0x60/0x62 服务协议接管动态调度。",
            },
        )

    def test_get_crypto_status_preserves_old_control_summary_with_linked_service_mode(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.object(
            state,
            "_control_plane_summary",
            return_value={
                "control_guard_state": "READY",
                "control_last_fault_code": "NONE",
                "control_heartbeat_ok": 0,
                "control_total_fault_count": 3,
            },
        ):
            payload = state.get_crypto_status()

        self.assertEqual(payload["control_guard_state"], "READY")
        self.assertEqual(payload["control_last_fault_code"], "NONE")
        self.assertEqual(payload["control_heartbeat_ok"], 0)
        self.assertEqual(payload["control_total_fault_count"], 3)
        self.assertTrue(payload["service_mode"]["available"])
        self.assertEqual(payload["service_mode"]["current_mode"], "FULL_FRAME")

    def test_refresh_control_plane_status_caches_probe_error(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        with patch("server.query_live_status", side_effect=RuntimeError("rpmsg bridge unavailable")):
            payload = state._refresh_control_plane_status(
                board_access,
                source="unit_test_probe",
            )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["message"], "rpmsg bridge unavailable")
        self.assertEqual(state._last_control_probe_error["status_source"], "probe_error")
        self.assertEqual(state._last_control_probe_error["message"], "rpmsg bridge unavailable")

    def test_get_crypto_status_does_not_auto_probe_control_when_status_endpoint_fails(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides({"MLKEM_STATUS_PORT": "18080"}),
        )

        with (
            patch("server.fetch_json_direct", side_effect=server.URLError("[Errno 111] Connection refused")),
            patch.object(state, "_refresh_control_plane_status") as refresh_mock,
        ):
            payload = state.get_crypto_status()

        refresh_mock.assert_not_called()
        self.assertEqual(payload["control_guard_state"], "NOT_PROBED")
        self.assertEqual(payload["control_last_fault_code"], "NOT_PROBED")
        self.assertEqual(payload["status_source"], "not_probed")
        self.assertEqual(payload["channel_state"], "idle")
        self.assertTrue(payload["board_configured"])

    def test_get_crypto_status_ignores_control_probe_error_until_explicit_probe(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        state._last_control_probe_error = {
            "status": "error",
            "status_source": "probe_error",
            "message": "rpmsg unavailable",
            "guard_state": "PROBE_ERROR",
            "last_fault_code": "PROBE_ERROR",
        }

        with patch("server.fetch_json_direct", side_effect=server.URLError("[Errno 111] Connection refused")):
            payload = state.get_crypto_status()

        self.assertEqual(payload["control_guard_state"], "PROBE_ERROR")
        self.assertEqual(payload["control_last_fault_code"], "PROBE_ERROR")
        self.assertEqual(payload["status_source"], "probe_error")
        self.assertEqual(payload["status_note"], "rpmsg unavailable")

    def test_get_crypto_status_uses_board_access_auth_over_status_endpoint_stale_value(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_AUTH_ENABLED": "1",
                    "MLKEM_AUTH_SIG_POLICY": "DUAL_REQUIRED",
                    "MLKEM_AUTH_SERVER_ID": "phytium-board",
                }
            ),
        )

        stale_status = {
            "channel_state": "idle",
            "kem_backend": "mock-backend",
            "cipher_suite": "sm4-gcm",
            "auth_enabled": False,
            "sig_policy": "",
            "server_id": "",
        }
        with patch("server.fetch_json_direct", return_value=stale_status):
            payload = state.get_crypto_status()

        self.assertEqual(payload["auth_enabled"], True)
        self.assertEqual(payload["sig_policy"], "DUAL_REQUIRED")
        self.assertEqual(payload["server_id"], "phytium-board")

    def test_get_crypto_status_marks_usrp_security_as_control_gate(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_TRANSPORT_MODE": "usrp",
                    "MLKEM_AUTH_ENABLED": "1",
                }
            ),
        )

        live_status = {
            "channel_state": "ready",
            "kem_backend": "tongsuo-ML-KEM-768",
            "cipher_suite": "sm4-gcm",
            "bytes_sent": 1024,
            "bytes_received": 2048,
        }

        with patch("server.fetch_json_direct", return_value=live_status):
            payload = state.get_crypto_status()

        self.assertEqual(payload["security_scope"], "control_gate")
        self.assertEqual(payload["security_scope_label"], "控制/认证面准入")
        self.assertTrue(payload["control_plane_protected"])
        self.assertFalse(payload["data_plane_encrypted"])
        self.assertFalse(payload["tcp_payload_encrypted"])
        self.assertFalse(payload["usrp_payload_encrypted"])
        self.assertIn("USRP IQ", payload["security_scope_note"])

    def test_get_crypto_status_marks_tcp_security_as_payload_encryption(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_TRANSPORT_MODE": "tcp",
                    "MLKEM_AUTH_ENABLED": "1",
                }
            ),
        )

        live_status = {
            "channel_state": "ready",
            "kem_backend": "tongsuo-ML-KEM-768",
            "cipher_suite": "sm4-gcm",
            "bytes_sent": 1024,
            "bytes_received": 2048,
        }

        with patch("server.fetch_json_direct", return_value=live_status):
            payload = state.get_crypto_status()

        self.assertEqual(payload["security_scope"], "tcp_payload")
        self.assertEqual(payload["security_scope_label"], "TCP 数据面加密")
        self.assertTrue(payload["control_plane_protected"])
        self.assertTrue(payload["data_plane_encrypted"])
        self.assertTrue(payload["tcp_payload_encrypted"])
        self.assertFalse(payload["usrp_payload_encrypted"])
        self.assertIn("latent", payload["security_scope_note"])

    def test_run_crypto_test_updates_status_cache_from_subprocess_metrics(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )

        stdout = "\n".join(
            [
                "密码套件:  SM4_GCM",
                "KEM 后端:  mock-backend",
                "握手完成: 9.0ms",
                "身份认证:  已启用 (DUAL_REQUIRED)",
                "服务端标识: phytium-board",
                "加密发送: 49152B, 耗时 3.0ms",
                "✓ 传输成功",
                "  对端 SHA256 匹配: 是",
                "  TVM 推理耗时: 21.0ms",
                "  接收重建结果: 65536B, 耗时 4.0ms",
            ]
        )
        control_probe = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "heartbeat_ok": 1,
            "total_fault_count": 0,
        }

        with (
            patch("server.resolve_local_crypto_client", return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")])),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", str(client_script), "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=None),
            patch(
                "server.subprocess.run",
                return_value=server.subprocess.CompletedProcess(
                    ["fake-python", "tcp_client.py"],
                    0,
                    stdout=stdout,
                    stderr="",
                ),
            ),
            patch("server.query_live_status", return_value=control_probe) as query_status,
        ):
            result = state.run_crypto_test()

        self.assertEqual(result["status"], "ok")
        query_status.assert_called_once()
        payload = state.get_crypto_status()
        self.assertEqual(payload["channel_state"], "idle")
        self.assertEqual(payload["kem_backend"], "mock-backend")
        self.assertEqual(payload["cipher_suite"], "sm4-gcm")
        self.assertEqual(payload["handshake_ms"], 9.0)
        self.assertEqual(payload["encrypt_ms"], 3.0)
        self.assertEqual(payload["decrypt_ms"], 4.0)
        self.assertEqual(payload["inference_ms"], 21.0)
        self.assertEqual(payload["bytes_sent"], 49152)
        self.assertEqual(payload["bytes_received"], 65536)
        self.assertEqual(payload["last_sha256_match"], True)
        self.assertEqual(payload["session_count"], 1)
        self.assertEqual(payload["auth_enabled"], True)
        self.assertEqual(payload["sig_policy"], "DUAL_REQUIRED")
        self.assertEqual(payload["server_id"], "phytium-board")
        self.assertEqual(payload["control_guard_state"], "READY")
        self.assertEqual(payload["control_last_fault_code"], "NONE")
        self.assertEqual(payload["control_heartbeat_ok"], 1)
        self.assertEqual(payload["control_total_fault_count"], 0)
        self.assertIsNone(payload["error"])

    def test_run_crypto_test_starts_control_tcp_server_in_usrp_transport_mode(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"}),
        )

        with (
            patch("server.resolve_local_crypto_client", return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")])),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", str(client_script), "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch.object(state, "_ensure_board_tcp_server", return_value=None) as ensure_server,
            patch.object(state, "_get_mlkem_session_manager", return_value=None),
            patch(
                "server.subprocess.run",
                return_value=server.subprocess.CompletedProcess(
                    ["fake-python", "tcp_client.py"],
                    0,
                    stdout="✓ 传输成功\n  对端 SHA256 匹配: 是\n",
                    stderr="",
                ),
            ),
            patch("server.query_live_status", return_value={}),
        ):
            result = state.run_crypto_test()

        self.assertEqual(result["status"], "ok")
        ensure_server.assert_called_once_with(state._board_access)

    def test_run_crypto_test_uses_utf8_replacement_for_local_client_output(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "demo-board",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access,
        )
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> server.subprocess.CompletedProcess[str]:
            captured.update(kwargs)
            return server.subprocess.CompletedProcess(
                args[0],
                0,
                stdout="✓ 传输成功\n  对端 SHA256 匹配: 是\n",
                stderr="",
            )

        with (
            patch("server.resolve_local_crypto_client", return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")])),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", str(client_script), "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=None),
            patch("server.subprocess.run", side_effect=fake_run),
            patch("server.query_live_status", return_value={}),
        ):
            result = state.run_crypto_test()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["encoding"], "utf-8")
        self.assertEqual(captured["errors"], "replace")

    def test_get_crypto_status_reuses_last_successful_crypto_test_when_status_probe_is_unreachable(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._crypto_enabled = True
        state._board_access = server.build_board_access_config(
            {
                "host": "100.121.87.73",
                "user": "demo-user",
                "password": "demo-pass",
                "port": "22",
            },
            fallback=state._board_access.with_env_overrides(
                {
                    "MLKEM_STATUS_PORT": "18080",
                    "TONGSUO_KEM_BRIDGE": "/tmp/libtongsuo_kem_bridge.so",
                    "MLKEM_CIPHER_SUITE": "SM4_GCM",
                }
            ),
        )

        class FakeMgr:
            def __init__(self) -> None:
                self._handshake_ms = 12.3

            def ensure_alive(self) -> None:
                return None

            def send_image(
                self,
                input_path: str,
                job_id: str,
                *,
                run_tvm: bool = False,
                expect_result: bool = False,
            ) -> dict[str, object]:
                del input_path, job_id, run_tvm, expect_result
                return {
                    "status": "ok",
                    "sha256_match": True,
                    "encrypt_ms": 7.0,
                    "decrypt_ms": None,
                    "inference_ms": None,
                }

        with (
            patch("server.resolve_local_crypto_client", return_value=(Path("/tmp/tcp_client.py"), [Path("/tmp/tcp_client.py")])),
            patch(
                "server.build_local_crypto_client_command",
                side_effect=lambda env_values, *, host, input_path, client_script: (
                    ["fake-python", str(client_script), "--host", host, "--input", str(input_path)],
                    {},
                ),
            ),
            patch.object(state, "_ensure_board_tcp_server", return_value=None),
            patch.object(state, "_get_mlkem_session_manager", return_value=FakeMgr()),
            patch("server.query_live_status", side_effect=RuntimeError("control probe failed")),
        ):
            result = state.run_crypto_test()

        self.assertEqual(result["status"], "ok")
        state._crypto_status_cache_ts = 0.0

        with patch("server.fetch_json_direct", side_effect=server.URLError("[Errno 111] Connection refused")):
            payload = state.get_crypto_status()

        self.assertEqual(payload["channel_state"], "ready")
        self.assertEqual(payload["kem_backend"], "tongsuo-ML-KEM-768")
        self.assertEqual(payload["cipher_suite"], "sm4-gcm")
        self.assertEqual(payload["handshake_ms"], 12.3)
        self.assertEqual(payload["encrypt_ms"], 7.0)
        self.assertTrue((payload["bytes_sent"] or 0) > 0)
        self.assertEqual(payload["last_sha256_match"], True)
        self.assertEqual(payload["session_count"], 1)
        self.assertIn("board status endpoint unavailable", str(payload["error"]))

    def test_set_board_access_applies_auth_policy_overrides(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        payload = state.set_board_access(
            {
                "password": "demo-pass",
                "auth_enabled": True,
                "auth_sig_policy": "MLDSA_ONLY",
            }
        )

        self.assertTrue(payload["has_password"])
        env = state._board_access.build_env()
        self.assertEqual(env.get("MLKEM_AUTH_ENABLED"), "1")
        self.assertEqual(env.get("MLKEM_AUTH_SIG_POLICY"), "MLDSA_ONLY")
        self.assertEqual(env.get("MLKEM_AUTH_SERVER_ID"), "phytium-board")
        self.assertEqual(env.get("MLKEM_AUTH_SERVER_SM2_KEY"), "/home/user/keys/server_sm2_identity.key")
        self.assertEqual(env.get("MLKEM_AUTH_SERVER_SM2_PUB"), "/home/user/keys/server_sm2_identity.pub")
        self.assertEqual(env.get("MLKEM_AUTH_SERVER_MLDSA_KEY"), "/home/user/keys/server_mldsa_identity.key")
        self.assertEqual(env.get("MLKEM_AUTH_SERVER_MLDSA_PUB"), "/home/user/keys/server_mldsa_identity.pub")
        self.assertEqual(env.get("MLKEM_AUTH_PEER_SM2_PUB"), str(server.PACKAGE_ROOT / "keys" / "server_sm2_identity.pub"))
        self.assertEqual(
            env.get("MLKEM_AUTH_PEER_MLDSA_PUB"),
            str(server.PACKAGE_ROOT / "keys" / "server_mldsa_identity.pub"),
        )
        self.assertEqual(env.get("MLKEM_REMOTE_TONGSUO_SIG_BRIDGE"), "/home/user/libtongsuo_sig_bridge.so")
        self.assertEqual(env.get("MLKEM_REMOTE_OQS_INSTALL_PATH"), "/home/user/liboqs-dist")

    def test_set_board_access_preserves_usrp_iq_runtime_env_from_process(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.dict(
            os.environ,
            {
                "ANALOG_REMOTE_DECODED_FORMAT": "npy",
                "ANALOG_REMOTE_DECODE_RESPONSE_MODE": "minimal",
                "ANALOG_PRECONNECT_CONTROL": "1",
                "ANALOG_RX_BATCH_SESSION_CONTROL": "1",
                "ANALOG_RX_BATCH_SESSION_MAX_IMAGES": "10",
                "ANALOG_RX_HEALTH_RESET_ON_STALL": "1",
                "ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC": "0.75",
                "ANALOG_PIPELINE_DEPTH": "2",
                "ANALOG_PIPELINE_RF_DECODE_OVERLAP": "1",
                "OPENAMP_IQ_STREAMING_TVM": "1",
                "OPENAMP_IQ_STREAMING_MIN_READY": "10",
                "BIG_LITTLE_INPUT_CHUNK_SIZE": "10",
                "ANALOG_REMOTE_DECODE_WORKER_PREFIX": "taskset -c 0,1",
            },
            clear=False,
        ):
            state.set_board_access(
                {
                    "host": "100.121.87.73",
                    "user": "user",
                    "password": "user",
                    "transport_mode": "usrp",
                    "remote_usrp_rx_dir": "/home/user/cockpit_usrp_rx",
                }
            )

        env = state._board_access.build_env()
        self.assertEqual(env.get("ANALOG_REMOTE_DECODED_FORMAT"), "npy")
        self.assertEqual(env.get("ANALOG_REMOTE_DECODE_RESPONSE_MODE"), "minimal")
        self.assertEqual(env.get("ANALOG_PRECONNECT_CONTROL"), "1")
        self.assertEqual(env.get("ANALOG_RX_BATCH_SESSION_CONTROL"), "1")
        self.assertEqual(env.get("ANALOG_RX_BATCH_SESSION_MAX_IMAGES"), "10")
        self.assertEqual(env.get("ANALOG_RX_HEALTH_RESET_ON_STALL"), "1")
        self.assertEqual(env.get("ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC"), "0.75")
        self.assertEqual(env.get("ANALOG_PIPELINE_DEPTH"), "2")
        self.assertEqual(env.get("ANALOG_PIPELINE_RF_DECODE_OVERLAP"), "1")
        self.assertEqual(env.get("OPENAMP_IQ_STREAMING_TVM"), "1")
        self.assertEqual(env.get("OPENAMP_IQ_STREAMING_MIN_READY"), "10")
        self.assertEqual(env.get("BIG_LITTLE_INPUT_CHUNK_SIZE"), "10")
        self.assertEqual(env.get("ANALOG_REMOTE_DECODE_WORKER_PREFIX"), "taskset -c 0,1")

    def test_set_board_access_disables_iq_streaming_tvm_by_default(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.dict(os.environ, {}, clear=False):
            state.set_board_access(
                {
                    "host": "100.121.87.73",
                    "user": "user",
                    "password": "user",
                    "transport_mode": "usrp",
                    "jscc_link_mode": "iq-direct",
                    "remote_usrp_rx_dir": "/home/user/cockpit_usrp_rx",
                }
            )

        env = state._board_access.build_env()
        self.assertEqual(env.get("OPENAMP_IQ_STREAMING_TVM"), "0")
        self.assertEqual(env.get("OPENAMP_IQ_STREAMING_MIN_READY"), "10")
        self.assertEqual(env.get("BIG_LITTLE_INPUT_CHUNK_SIZE"), "10")

    def test_session_board_access_rejects_unsupported_auth_sig_policy(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "auth_enabled": True, "auth_sig_policy": "RSA_ONLY"}).encode("utf-8"),
        )

        self.assertEqual(status, 400)
        self.assertIn("unsupported auth_sig_policy", str(payload["message"]))


class ServerMainTest(unittest.TestCase):
    def test_server_script_help_runs_without_manual_pythonpath(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, str(DEMO_ROOT / "server.py"), "--help"],
            cwd=DEMO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("usage: server.py", result.stdout)

    def test_demo_startup_env_overrides_uses_default_baidu_position_config_without_env_file(self) -> None:
        args = Namespace(
            aircraft_position_env="",
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )

        with patch.dict(
            os.environ,
            {key: "" for key in server.AIRCRAFT_POSITION_RUNTIME_ENV_KEYS},
            clear=False,
        ):
            overrides = server.demo_startup_env_overrides(args)

        self.assertEqual(overrides["AIRCRAFT_POSITION_EXECUTION_MODE"], "local")
        self.assertEqual(
            overrides["AIRCRAFT_POSITION_UPSTREAM_URL"],
            server.DEFAULT_DEMO_AIRCRAFT_POSITION_LOCAL_OVERRIDES["AIRCRAFT_POSITION_UPSTREAM_URL"],
        )
        self.assertEqual(overrides["AIRCRAFT_POSITION_INTERVAL_SEC"], "30.0")
        self.assertEqual(overrides["AIRCRAFT_POSITION_LATITUDE_PATH"], "content.point.y")
        self.assertEqual(overrides["AIRCRAFT_POSITION_LONGITUDE_PATH"], "content.point.x")

    def test_demo_startup_env_overrides_loads_aircraft_position_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "aircraft_position.env"
            env_path.write_text(
                "\n".join(
                    [
                        "AIRCRAFT_POSITION_EXECUTION_MODE=local",
                        "AIRCRAFT_POSITION_UPSTREAM_URL=https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                        "AIRCRAFT_POSITION_LATITUDE_PATH=content.point.y",
                        "AIRCRAFT_POSITION_LONGITUDE_PATH=content.point.x",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                aircraft_position_env=str(env_path),
                demo_admission_mode="",
                signed_manifest_file="",
                signed_manifest_public_key="",
                baseline_admission_mode="",
                baseline_signed_manifest_file="",
                baseline_signed_manifest_public_key="",
            )

            overrides = server.demo_startup_env_overrides(args)

        self.assertEqual(overrides["AIRCRAFT_POSITION_EXECUTION_MODE"], "local")
        self.assertEqual(
            overrides["AIRCRAFT_POSITION_UPSTREAM_URL"],
            "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
        )
        self.assertEqual(overrides["AIRCRAFT_POSITION_LATITUDE_PATH"], "content.point.y")

    def test_demo_startup_env_overrides_forwards_board_connection_env(self) -> None:
        args = Namespace(
            aircraft_position_env="",
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )

        with patch.dict(
            os.environ,
            {
                "REMOTE_HOST": "192.168.50.23",
                "PHYTIUM_PI_HOST": "192.168.50.23",
                "REMOTE_USER": "user",
                "PHYTIUM_PI_USER": "user",
                "REMOTE_SSH_PORT": "2202",
                "PHYTIUM_PI_PORT": "2202",
            },
            clear=False,
        ):
            overrides = server.demo_startup_env_overrides(args)

        self.assertEqual(overrides["REMOTE_HOST"], "192.168.50.23")
        self.assertEqual(overrides["PHYTIUM_PI_HOST"], "192.168.50.23")
        self.assertEqual(overrides["REMOTE_USER"], "user")
        self.assertEqual(overrides["PHYTIUM_PI_USER"], "user")
        self.assertEqual(overrides["REMOTE_SSH_PORT"], "2202")
        self.assertEqual(overrides["PHYTIUM_PI_PORT"], "2202")

    def test_demo_startup_env_overrides_keeps_usrp_runtime_env(self) -> None:
        args = Namespace(
            aircraft_position_env="",
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )

        with patch.dict(
            os.environ,
            {
                "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                "MLKEM_TRANSPORT_MODE": "usrp",
                "MLKEM_USRP_MODE": "ota",
                "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                "OPENAMP_DEMO_LINK_MODE": "iq-direct",
                "OPENAMP_DEMO_LOCAL_LATENT_DIR": "/tmp/latents",
                "CHUNK_BYTES": "4096",
                "USRP_WIRE_PREPARE_WORKERS": "2",
                "USRP_WIRE_CACHE_ENABLED": "1",
                "ANALOG_REMOTE_DECODE_RESPONSE_MODE": "minimal",
                "ANALOG_REMOTE_DECODED_FORMAT": "npy",
                "ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY": "1",
                "ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC": "0.14",
                "ANALOG_REMOTE_DECODE_WORKER_PREFIX": "taskset -c 2",
                "ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS": "1",
                "ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK": "64",
                "ANALOG_RX_SC16_MMAP": "1",
                "ANALOG_RX_CLIPPING_DECIMATION": "8",
                "ANALOG_PRECONNECT_RX_CAPTURE_CONTROL": "1",
                "ANALOG_RX_SESSION_CONTROL": "1",
                "ANALOG_RX_BATCH_SESSION_CONTROL": "1",
                "ANALOG_RX_BATCH_SESSION_MAX_IMAGES": "16",
                "ANALOG_RX_HEALTH_RESET_ON_STALL": "1",
                "ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC": "0.75",
                "ANALOG_RX_ARM_STATUS_TIMEOUT_SEC": "0.75",
                "ANALOG_RX_ARM_STATUS_POLL_SEC": "0.025",
                "ANALOG_RX_WAIT_TIMEOUT_SEC": "1.0",
                "ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC": "1.0",
                "ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC": "0.0",
                "ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC": "2.5",
                "ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC": "8.0",
                "ANALOG_RX_STOP_DRAIN_POLL_SEC": "0.05",
                "ANALOG_PIPELINE_DEPTH": "1",
                "RX_ARM_WAIT_MS": "50",
                "RX_STOP_WAIT_MS": "8000",
                "OPENAMP_USRP_TX_RUNNER": "docker",
                "OPENAMP_USRP_TX_DOCKER_IMAGE": "iccomp-usrp-tx:latest",
                "OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET": "/host_workspace",
                "OPENAMP_SSH_RUNNER": "paramiko",
                "SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER": "1",
                "OPENAMP_TVM_BATCH_RUNNER": "biglittle",
            },
            clear=False,
        ):
            overrides = server.demo_startup_env_overrides(args)

        self.assertEqual(overrides["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx")
        self.assertEqual(overrides["MLKEM_TRANSPORT_MODE"], "usrp")
        self.assertEqual(overrides["MLKEM_USRP_MODE"], "ota")
        self.assertEqual(overrides["OPENAMP_DEMO_INPUT_SOURCE_MODE"], "usrp")
        self.assertEqual(overrides["OPENAMP_DEMO_LINK_MODE"], "iq-direct")
        self.assertEqual(overrides["OPENAMP_DEMO_LOCAL_LATENT_DIR"], "/tmp/latents")
        self.assertEqual(overrides["CHUNK_BYTES"], "4096")
        self.assertEqual(overrides["USRP_WIRE_PREPARE_WORKERS"], "2")
        self.assertEqual(overrides["USRP_WIRE_CACHE_ENABLED"], "1")
        self.assertEqual(overrides["ANALOG_REMOTE_DECODE_RESPONSE_MODE"], "minimal")
        self.assertEqual(overrides["ANALOG_REMOTE_DECODED_FORMAT"], "npy")
        self.assertEqual(overrides["ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY"], "1")
        self.assertEqual(overrides["ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC"], "0.14")
        self.assertEqual(overrides["ANALOG_REMOTE_DECODE_WORKER_PREFIX"], "taskset -c 2")
        self.assertEqual(overrides["ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS"], "1")
        self.assertEqual(overrides["ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK"], "64")
        self.assertEqual(overrides["ANALOG_RX_SC16_MMAP"], "1")
        self.assertEqual(overrides["ANALOG_RX_CLIPPING_DECIMATION"], "8")
        self.assertEqual(overrides["ANALOG_PRECONNECT_RX_CAPTURE_CONTROL"], "1")
        self.assertEqual(overrides["ANALOG_RX_SESSION_CONTROL"], "1")
        self.assertEqual(overrides["ANALOG_RX_BATCH_SESSION_CONTROL"], "1")
        self.assertEqual(overrides["ANALOG_RX_BATCH_SESSION_MAX_IMAGES"], "16")
        self.assertEqual(overrides["ANALOG_RX_HEALTH_RESET_ON_STALL"], "1")
        self.assertEqual(overrides["ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC"], "0.75")
        self.assertEqual(overrides["ANALOG_RX_ARM_STATUS_TIMEOUT_SEC"], "0.75")
        self.assertEqual(overrides["ANALOG_RX_ARM_STATUS_POLL_SEC"], "0.025")
        self.assertEqual(overrides["ANALOG_RX_WAIT_TIMEOUT_SEC"], "1.0")
        self.assertEqual(overrides["ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC"], "1.0")
        self.assertEqual(overrides["ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC"], "0.0")
        self.assertEqual(overrides["ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC"], "2.5")
        self.assertEqual(overrides["ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC"], "8.0")
        self.assertEqual(overrides["ANALOG_RX_STOP_DRAIN_POLL_SEC"], "0.05")
        self.assertEqual(overrides["ANALOG_PIPELINE_DEPTH"], "1")
        self.assertEqual(overrides["RX_ARM_WAIT_MS"], "50")
        self.assertEqual(overrides["RX_STOP_WAIT_MS"], "8000")
        self.assertEqual(overrides["OPENAMP_USRP_TX_RUNNER"], "docker")
        self.assertEqual(overrides["OPENAMP_USRP_TX_DOCKER_IMAGE"], "iccomp-usrp-tx:latest")
        self.assertEqual(overrides["OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET"], "/host_workspace")
        self.assertEqual(overrides["OPENAMP_SSH_RUNNER"], "paramiko")
        self.assertEqual(overrides["SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER"], "1")
        self.assertEqual(overrides["OPENAMP_TVM_BATCH_RUNNER"], "biglittle")

    def test_demo_startup_env_overrides_prefers_image_latent_cache_when_images_exist(self) -> None:
        args = Namespace(
            aircraft_position_env="",
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            image_dir = Path(tmpdir) / "images"
            image_dir.mkdir()
            (image_dir / "00000001.jpg").write_bytes(b"image")
            latent_dir = Path(tmpdir) / "encoder_outputs"
            latent_dir.mkdir()
            (latent_dir / "sample.pt").write_bytes(b"latent")
            image_latent_dir = Path(tmpdir) / "image_latents"
            with (
                patch.object(server, "DEFAULT_LOCAL_USRP_IMAGE_DIR_CANDIDATES", (image_dir,)),
                patch.object(server, "DEFAULT_LOCAL_USRP_LATENT_DIR_CANDIDATES", (latent_dir,)),
                patch.object(server, "DEFAULT_LOCAL_USRP_IMAGE_LATENT_DIR", image_latent_dir),
                patch.dict(
                    os.environ,
                    {
                        "MLKEM_TRANSPORT_MODE": "usrp",
                        "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                        "OPENAMP_DEMO_LOCAL_LATENT_DIR": "",
                    },
                    clear=False,
                ),
            ):
                overrides = server.demo_startup_env_overrides(args)

        self.assertEqual(overrides["OPENAMP_DEMO_LOCAL_IMAGE_DIR"], str(image_dir))
        self.assertEqual(overrides["OPENAMP_DEMO_LOCAL_LATENT_DIR"], str(image_latent_dir))
        self.assertEqual(overrides["OPENAMP_DEMO_IMAGE_TO_LATENT_OUTPUT_DIR"], str(image_latent_dir))
        self.assertEqual(overrides["OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED"], "1")

    def test_usrp_job_default_timeout_scales_with_batch_count(self) -> None:
        self.assertEqual(
            usrp_runtime._resolve_usrp_job_timeout_sec({}, expected_outputs=300),
            1500.0,
        )
        self.assertEqual(
            usrp_runtime._resolve_usrp_job_timeout_sec({"USRP_JOB_TIMEOUT_SEC": "60"}, expected_outputs=300),
            120.0,
        )
        self.assertEqual(
            usrp_runtime._resolve_usrp_job_timeout_sec({"USRP_JOB_TIMEOUT_SEC": "1800"}, expected_outputs=300),
            1800.0,
        )

    def test_usrp_wire_prepare_limits_to_requested_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_dir = temp_dir / "latents"
            output_dir = temp_dir / "prepared"
            source_dir.mkdir()
            for idx in range(5):
                (source_dir / f"{idx:03d}.pt").write_bytes(b"latent")

            def fake_build_transport_blob(path: str, *, job_id: str, payload_codec: str):
                return (
                    f"blob-{job_id}".encode("utf-8"),
                    {"job_id": job_id, "original_filename": f"{job_id}.png"},
                    {"payload_codec": payload_codec, "payload_bytes": 1, "original_filename": f"{job_id}.png"},
                )

            with patch.object(usrp_runtime, "build_transport_blob", side_effect=fake_build_transport_blob) as build_blob:
                manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=output_dir,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=2,
                    prepare_workers=1,
                )

        self.assertEqual(build_blob.call_count, 2)
        self.assertEqual(manifest["available_count"], 5)
        self.assertEqual(manifest["selected_count"], 2)
        self.assertEqual(manifest["count"], 2)
        self.assertEqual([Path(item["source"]).name for item in manifest["files"]], ["000.pt", "001.pt"])
        self.assertEqual(manifest["files"][0]["source_image"], "000.png")
        self.assertRegex(manifest["files"][0]["source_sha256"], r"^[0-9a-f]{64}$")

    def test_host_image_latent_manifest_rejects_changed_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            image_dir = temp_dir / "images"
            output_dir = temp_dir / "latents"
            image_dir.mkdir()
            output_dir.mkdir()
            image_path = image_dir / "000.png"
            image_path.write_bytes(b"image-a")
            records, available_count = usrp_runtime._host_image_records(image_dir, output_dir, 1)
            latent_path = Path(records[0]["latent"])
            latent_path.write_bytes(b"latent-a")
            manifest = usrp_runtime._write_host_image_latent_manifest(
                output_dir=output_dir,
                image_dir=image_dir,
                files=records,
                config_str="6_6_6_6_6_6_6",
                snr="10",
                device="cpu",
                elapsed_sec=0.1,
                available_image_count=available_count,
            )

            valid = usrp_runtime._host_image_latent_cache_valid(
                image_dir=image_dir,
                output_dir=output_dir,
                expected_count=1,
                config_str="6_6_6_6_6_6_6",
                snr="10",
                device="cpu",
            )
            original_stat = image_path.stat()
            image_path.write_bytes(b"image-b")
            os.utime(image_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            invalid = usrp_runtime._host_image_latent_cache_valid(
                image_dir=image_dir,
                output_dir=output_dir,
                expected_count=1,
                config_str="6_6_6_6_6_6_6",
                snr="10",
                device="cpu",
            )

        self.assertIsNotNone(valid)
        self.assertEqual(valid[1][0], latent_path)
        self.assertEqual(manifest["files"][0]["source_image_rel"], "000.png")
        self.assertRegex(manifest["files"][0]["source_image_sha256"], r"^[0-9a-f]{64}$")
        self.assertIsNone(invalid)

    def test_usrp_wire_prepare_can_use_explicit_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_dir = temp_dir / "latents"
            output_dir = temp_dir / "prepared"
            source_dir.mkdir()
            first = source_dir / "000.pt"
            second = source_dir / "001.pt"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            def fake_build_transport_blob(path: str, *, job_id: str, payload_codec: str):
                return (
                    Path(path).read_bytes(),
                    {"job_id": job_id},
                    {"payload_codec": payload_codec, "payload_bytes": 1},
                )

            with patch.object(usrp_runtime, "build_transport_blob", side_effect=fake_build_transport_blob) as build_blob:
                manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=output_dir,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=1,
                    prepare_workers=1,
                    source_files=[second],
                )
            prepared_bytes = (output_dir / "001.pt.bin").read_bytes()

        self.assertEqual(build_blob.call_count, 1)
        self.assertEqual(manifest["selected_count"], 1)
        self.assertEqual(Path(manifest["files"][0]["source"]).name, "001.pt")
        self.assertEqual(prepared_bytes, b"second")

    def test_usrp_wire_manifest_records_source_image_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            latent_path = temp_dir / "000.pt"
            manifest_path = temp_dir / "prepared" / "usrp_input_manifest.json"
            manifest_path.parent.mkdir()
            latent_path.write_bytes(b"latent")
            manifest = {
                "files": [
                    {
                        "source": str(latent_path),
                        "target": str(temp_dir / "prepared" / "000.pt.bin"),
                    }
                ]
            }
            host_manifest = {
                "files": [
                    {
                        "latent": str(latent_path),
                        "source_image": str(temp_dir / "images" / "000.png"),
                        "source_image_rel": "000.png",
                        "source_image_sha256": "a" * 64,
                        "source_image_size": 7,
                        "source_image_mtime_ns": 123,
                        "original_filename": "000",
                    }
                ]
            }

            enriched = usrp_runtime._enrich_wire_manifest_with_host_images(
                manifest,
                host_manifest,
                manifest_path,
            )
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(enriched["files"][0]["source_image"], "000")
        self.assertEqual(enriched["files"][0]["source_image_rel"], "000.png")
        self.assertEqual(enriched["files"][0]["source_image_sha256"], "a" * 64)
        self.assertEqual(saved["files"][0]["source_image_sha256"], "a" * 64)

    def test_usrp_wire_prepare_reuses_cached_wire_blobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_dir = temp_dir / "latents"
            first_output = temp_dir / "prepared1"
            second_output = temp_dir / "prepared2"
            cache_dir = temp_dir / "cache"
            source_dir.mkdir()
            (source_dir / "000.pt").write_bytes(b"latent")

            def fake_build_transport_blob(path: str, *, job_id: str, payload_codec: str):
                return (
                    f"blob-{job_id}".encode("utf-8"),
                    {"job_id": job_id, "original_filename": f"{job_id}.png"},
                    {"payload_codec": payload_codec, "payload_bytes": 1, "original_filename": f"{job_id}.png"},
                )

            with patch.object(usrp_runtime, "build_transport_blob", side_effect=fake_build_transport_blob) as build_blob:
                first_manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=first_output,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=1,
                    cache_dir=cache_dir,
                    prepare_workers=1,
                )
                second_manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=second_output,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=1,
                    cache_dir=cache_dir,
                    prepare_workers=1,
                )
            second_bytes = (second_output / "000.pt.bin").read_bytes()

        self.assertEqual(build_blob.call_count, 1)
        self.assertEqual(first_manifest["cache_hit_count"], 0)
        self.assertEqual(second_manifest["cache_hit_count"], 1)
        self.assertEqual(second_manifest["files"][0]["source_image"], "000.png")
        self.assertEqual(second_bytes, b"blob-000")

    def test_usrp_wire_prepare_rejects_cache_when_source_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_dir = temp_dir / "latents"
            first_output = temp_dir / "prepared1"
            second_output = temp_dir / "prepared2"
            cache_dir = temp_dir / "cache"
            source_dir.mkdir()
            source_path = source_dir / "000.pt"
            source_path.write_bytes(b"latent-a")

            def fake_build_transport_blob(path: str, *, job_id: str, payload_codec: str):
                payload = Path(path).read_bytes()
                return (
                    b"blob-" + payload,
                    {"job_id": job_id},
                    {"payload_codec": payload_codec, "payload_bytes": len(payload)},
                )

            with patch.object(usrp_runtime, "build_transport_blob", side_effect=fake_build_transport_blob) as build_blob:
                first_manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=first_output,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=1,
                    cache_dir=cache_dir,
                    prepare_workers=1,
                )
                original_stat = source_path.stat()
                source_path.write_bytes(b"latent-b")
                os.utime(source_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                second_manifest = usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=second_output,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=1,
                    cache_dir=cache_dir,
                    prepare_workers=1,
                )
            second_bytes = (second_output / "000.pt.bin").read_bytes()

        self.assertEqual(build_blob.call_count, 2)
        self.assertEqual(first_manifest["cache_hit_count"], 0)
        self.assertEqual(second_manifest["cache_hit_count"], 0)
        self.assertNotEqual(first_manifest["files"][0]["source_sha256"], second_manifest["files"][0]["source_sha256"])
        self.assertEqual(second_bytes, b"blob-latent-b")

    def test_usrp_wire_prepare_parallel_path_can_use_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_dir = temp_dir / "latents"
            first_output = temp_dir / "prepared1"
            second_output = temp_dir / "prepared2"
            cache_dir = temp_dir / "cache"
            source_dir.mkdir()
            for idx in range(2):
                (source_dir / f"{idx:03d}.pt").write_bytes(b"latent")

            def fake_build_transport_blob(path: str, *, job_id: str, payload_codec: str):
                return (
                    f"blob-{job_id}".encode("utf-8"),
                    {"job_id": job_id},
                    {"payload_codec": payload_codec, "payload_bytes": 1},
                )

            with patch.object(usrp_runtime, "build_transport_blob", side_effect=fake_build_transport_blob):
                usrp_runtime._prepare_wire_input_dir(
                    source_dir=source_dir,
                    output_dir=first_output,
                    payload_codec="webp-lossless",
                    pattern="*.pt",
                    max_files=2,
                    cache_dir=cache_dir,
                    prepare_workers=1,
                )
            second_manifest = usrp_runtime._prepare_wire_input_dir(
                source_dir=source_dir,
                output_dir=second_output,
                payload_codec="webp-lossless",
                pattern="*.pt",
                max_files=2,
                cache_dir=cache_dir,
                prepare_workers=2,
            )
            second_0 = (second_output / "000.pt.bin").read_bytes()
            second_1 = (second_output / "001.pt.bin").read_bytes()

        self.assertEqual(second_manifest["prepare_workers"], 2)
        self.assertEqual(second_manifest["cache_hit_count"], 2)
        self.assertEqual(second_0, b"blob-000")
        self.assertEqual(second_1, b"blob-001")

    def test_usrp_summary_recovers_progress_from_log_after_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            log_path = Path(temp_dir_name) / "cockpit_usrp.log"
            log_path.write_text(
                "\n".join(
                    [
                        "batch_progress round=0 batch=1/15 processed=20/300 pass=19 pending=281",
                        "batch_progress round=0 batch=2/15 processed=40/300 pass=39 pending=261",
                    ]
                ),
                encoding="utf-8",
            )

            summary = usrp_runtime._merge_log_progress_into_summary(
                {"target_count": 300, "completed_count": 0, "pass_count": 0, "fail_count": 0},
                log_path,
                fallback_target=300,
            )

        self.assertEqual(summary["target_count"], 300)
        self.assertEqual(summary["completed_count"], 40)
        self.assertEqual(summary["pass_count"], 39)
        self.assertEqual(summary["fail_count"], 1)
        self.assertEqual(summary["pending_count"], 260)
        self.assertFalse(summary["all_pass"])

    def test_usrp_snapshot_counts_completed_image_dirs_before_summary_exists(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )
            with patch("usrp_runtime.threading.Thread", FakeThread):
                job = usrp_runtime.UsrpBatchSpoolJob(access, variant="current", max_inputs=3)

            for index in (0, 1):
                image_dir = job._run_dir / f"image_{index:04d}"
                image_dir.mkdir(parents=True)
                (image_dir / "decode_summary.json").write_text('{"status":"ok"}', encoding="utf-8")
                (image_dir / "received_latent.npz").write_bytes(b"npz")

            with job._lock:
                job._phase = "transport"
                job._host_preprocess_completed = 3
                job._host_preprocess_state = "completed"

            snapshot = job.snapshot()

        self.assertEqual(snapshot["progress"]["count_label"], "2 / 3")
        self.assertEqual(snapshot["stage_progress"]["transport"]["completed_count"], 2)

    def test_usrp_iq_snapshot_exposes_remote_dir_decoded_manifest_before_summary_exists(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )
            with patch("usrp_runtime.threading.Thread", FakeThread):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=3,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                )

            image_0 = job._run_dir / "image_0000"
            image_0.mkdir(parents=True)
            (image_0 / "decode_summary.json").write_text(
                json.dumps({"status": "ok", "frame_complete": True, "sync_success": True}),
                encoding="utf-8",
            )
            with job._lock:
                job._phase = "transport"
                job._host_preprocess_completed = 3
                job._host_preprocess_state = "completed"

            snapshot = job.snapshot()

        manifest = snapshot["wrapper_summary"]["iq_remote_decode_manifest"]
        self.assertEqual(manifest["remote_dir"], f"/home/user/cockpit_usrp_rx/{job._run_id}_rx")
        self.assertEqual(manifest["decode_manifest"]["decoded_count"], 1)
        self.assertEqual(
            manifest["decode_manifest"]["files"],
            [f"/home/user/cockpit_usrp_rx/{job._run_id}_rx/00000000.npz"],
        )
        self.assertEqual(snapshot["stage_progress"]["transport"]["completed_count"], 1)

    def test_usrp_iq_terminal_snapshot_keeps_final_remote_decode_manifest(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )
            with patch("usrp_runtime.threading.Thread", FakeThread):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=2,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                )
            job._remote_stage_manifest = {
                "remote_dir": "/home/user/cockpit_usrp_rx/run_rx",
                "decode_manifest": {
                    "decoded_count": 2,
                    "files": [
                        "/home/user/cockpit_usrp_rx/run_rx/00000000.npy",
                        "/home/user/cockpit_usrp_rx/run_rx/00000001.npy",
                    ],
                },
            }
            job._inference_summary = {"status": "ok", "processed_count": 2}

            snapshot = job._build_terminal_snapshot(
                status="success",
                status_category="success",
                message="done",
                summary={"target_count": 2, "pass_count": 2, "all_pass": True},
            )

        manifest = snapshot["wrapper_summary"]["iq_remote_decode_manifest"]
        self.assertEqual(
            manifest["decode_manifest"]["files"],
            [
                "/home/user/cockpit_usrp_rx/run_rx/00000000.npy",
                "/home/user/cockpit_usrp_rx/run_rx/00000001.npy",
            ],
        )

    def test_usrp_local_tx_server_starts_shell_script_through_configured_bash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            fake_proc = Mock(pid=4242)
            with (
                patch("usrp_runtime.resolve_bash_executable", return_value="bash"),
                patch("usrp_runtime.subprocess.Popen", return_value=fake_proc) as popen,
            ):
                result = usrp_runtime._start_local_tx_server(
                    {"OPENAMP_USRP_TX_RUNNER": "local"},
                    log_dir=Path(temp_dir_name),
                    tx_port="29221",
                )

        self.assertEqual(result["status"], "started")
        command = popen.call_args.args[0]
        self.assertEqual(command[0], "bash")
        self.assertTrue(str(command[1]).endswith("OtaTxPersistentServer.sh"))

    def test_usrp_local_tx_server_can_start_from_docker_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            result = Mock(returncode=0, stdout="container-123\n", stderr="")
            env_values = {
                "OPENAMP_USRP_TX_RUNNER": "docker",
                "OPENAMP_USRP_TX_DOCKER_IMAGE": "iccomp-usrp-tx:latest",
            }
            with (
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=9999)),
                patch("usrp_runtime.subprocess.run", return_value=result) as run,
            ):
                payload = usrp_runtime._start_local_tx_server(env_values, log_dir=Path(temp_dir_name), tx_port="29221")

        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["runner"], "docker")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["docker", "run", "-d", "--rm"])
        self.assertIn("--mount", command)
        mount_value = command[command.index("--mount") + 1]
        self.assertIn(f"source={usrp_runtime.REPO_ROOT}", mount_value)
        self.assertIn("target=/host_workspace", mount_value)
        self.assertIn("-p", command)
        self.assertIn("127.0.0.1:29221:29221", command)
        self.assertIn("iccomp-usrp-tx:latest", command)
        self.assertEqual(command[-2:], ["bash", "/host_workspace/USRP292x/OtaTxPersistentServer.sh"])

    def test_usrp_tx_server_defaults_to_docker_on_windows_when_available(self) -> None:
        with (
            patch.object(usrp_runtime.os, "name", "nt"),
            patch("usrp_runtime.shutil.which", return_value="docker"),
        ):
            self.assertTrue(usrp_runtime._tx_server_uses_docker({}))

    def test_usrp_remote_command_timeout_returns_error_completed_process(self) -> None:
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )

        class TimeoutPopen:
            pid = 2222
            returncode = None

            def __init__(self, command, **_kwargs):  # type: ignore[no-untyped-def]
                self.args = command
                self.killed = False

            def wait(self, timeout=None):  # type: ignore[no-untyped-def]
                raise subprocess.TimeoutExpired(self.args, timeout)

            def kill(self) -> None:
                self.killed = True
                self.returncode = -9

        with (
            patch("usrp_runtime.os.name", "posix"),
            patch("usrp_runtime.resolve_bash_executable", return_value="bash"),
            patch("usrp_runtime.subprocess.Popen", side_effect=TimeoutPopen),
        ):
            result = usrp_runtime._run_remote_command(access, "echo ok", timeout=20.0)

        self.assertEqual(result.returncode, 124)
        self.assertIn(b"TimeoutExpired", result.stderr)

    def test_usrp_qpsk_runner_command_defaults_to_python_decode_backend(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            latent_dir = temp_dir / "latents"
            latent_dir.mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "OPENAMP_DEMO_LOCAL_LATENT_DIR": str(latent_dir),
                    "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED": "0",
                    "JSCC_LINK_MODE": "qpsk",
                    "OPENAMP_USRP_TX_RUNNER": "docker",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            def fake_prepare_wire_input_dir(*, output_dir: Path, **_: object) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                return {"prepared_count": 1}

            with (
                patch("usrp_runtime.threading.Thread", FakeThread),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_ensure_host_latents", return_value=latent_dir),
                patch("usrp_runtime._prepare_wire_input_dir", side_effect=fake_prepare_wire_input_dir),
                patch("usrp_runtime._enrich_wire_manifest_with_host_images", side_effect=lambda manifest, *_: manifest),
                patch("usrp_runtime._ensure_usrp_control_servers", return_value=(True, {})),
                patch("usrp_runtime._sync_iq_decode_assets_on_remote", create=True) as sync_decode_assets,
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_wait_for_completion", return_value=None),
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=1234)),
            ):
                job = usrp_runtime.UsrpBatchSpoolJob(access, variant="current", max_inputs=1)
                job._start_and_watch()
                job._log_handle.close()

        command = job._runner_command
        self.assertIn("RunQpskFileBatchSpoolArq.py", str(command[1]))
        self.assertIn("--decode-backend", command)
        self.assertEqual(command[command.index("--decode-backend") + 1], "python")
        self.assertIn("--tx-file-path-prefix-from", command)
        self.assertEqual(command[command.index("--tx-file-path-prefix-from") + 1], str(usrp_runtime.REPO_ROOT))
        self.assertIn("--tx-file-path-prefix-to", command)
        self.assertEqual(command[command.index("--tx-file-path-prefix-to") + 1], "/host_workspace")
        self.assertNotIn("--sps", command)
        self.assertNotIn("--amp", command)
        sync_decode_assets.assert_not_called()

    def test_usrp_wire_sync_uses_scp_instead_of_ssh_stdin(self) -> None:
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="demo-pass",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        with tempfile.TemporaryDirectory() as temp_dir_name:
            stage_dir = Path(temp_dir_name) / "stage"
            wire_dir = stage_dir / "_wire"
            wire_dir.mkdir(parents=True)
            (wire_dir / "00000001.bin").write_bytes(b"wire")
            calls: list[tuple[list[str], dict[str, object]]] = []

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=b'{"decoded_count": 1}\n',
                    stderr=b"",
                )

            with patch("usrp_runtime.subprocess.run", side_effect=fake_run):
                payload = usrp_runtime._sync_and_decode_wire_blobs_on_remote(
                    local_stage_dir=stage_dir,
                    remote_root="/home/user/cockpit_usrp_rx",
                    remote_subdir="run-001",
                    remote_python="python3",
                    access=access,
                )

        self.assertEqual(len(calls), 2)
        self.assertIn("scp", calls[0][0])
        self.assertNotIn("input", calls[0][1])
        self.assertNotIn("input", calls[1][1])
        self.assertEqual(calls[0][1]["env"]["SSHPASS"], "demo-pass")
        self.assertEqual(payload["decode_manifest"]["decoded_count"], 1)

    def test_usrp_iq_direct_runner_command_defaults_to_remote_decode(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            latent_dir = temp_dir / "latents"
            latent_dir.mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "OPENAMP_DEMO_LOCAL_LATENT_DIR": str(latent_dir),
                    "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED": "0",
                    "JSCC_LINK_MODE": "iq-direct",
                    "OPENAMP_DEMO_REMOTE_DECODE_PYTHON": "/home/user/venv/bin/python",
                    "OPENAMP_USRP_TX_RUNNER": "docker",
                    "ANALOG_SYNC_PROFILE": "fast-first",
                    "ANALOG_FAST_SYNC_CANDIDATES": "4",
                    "ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS": "1024",
                    "ANALOG_FALLBACK_SYNC_CANDIDATES": "12",
                    "ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS": "4096",
                    "ANALOG_RETRY_ON_BURST_MISS": "1",
                    "ANALOG_REMOTE_DECODED_FORMAT": "npy",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            def fake_prepare_wire_input_dir(*, output_dir: Path, **_: object) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                return {"prepared_count": 1}

            with (
                patch("usrp_runtime.threading.Thread", FakeThread),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_ensure_host_latents", return_value=latent_dir),
                patch("usrp_runtime._prepare_wire_input_dir", side_effect=fake_prepare_wire_input_dir),
                patch("usrp_runtime._enrich_wire_manifest_with_host_images", side_effect=lambda manifest, *_: manifest),
                patch("usrp_runtime._ensure_usrp_control_servers", return_value=(True, {})),
                patch("usrp_runtime._sync_iq_decode_assets_on_remote", create=True) as sync_decode_assets,
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_wait_for_completion", return_value=None),
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=1234)),
            ):
                job = usrp_runtime.UsrpBatchSpoolJob(access, variant="current", max_inputs=1)
                job._start_and_watch()
                job._log_handle.close()

        command = job._runner_command
        self.assertIn("RunAnalogLatentBatch.py", str(command[1]))
        self.assertIn("--tx-file-path-prefix-from", command)
        self.assertEqual(command[command.index("--tx-file-path-prefix-from") + 1], str(usrp_runtime.REPO_ROOT))
        self.assertIn("--tx-file-path-prefix-to", command)
        self.assertEqual(command[command.index("--tx-file-path-prefix-to") + 1], "/host_workspace")
        self.assertIn("--rx-capture-mode", command)
        self.assertEqual(command[command.index("--rx-capture-mode") + 1], "remote-decode")
        self.assertIn("--sps", command)
        self.assertEqual(command[command.index("--sps") + 1], "2")
        self.assertIn("--amp", command)
        self.assertEqual(command[command.index("--amp") + 1], "6000")
        self.assertIn("--max-arq-rounds", command)
        self.assertEqual(command[command.index("--max-arq-rounds") + 1], "5")
        self.assertIn("--iq-segment-size", command)
        self.assertEqual(command[command.index("--iq-segment-size") + 1], "30")
        self.assertIn("--iq-segment-repair-passes", command)
        self.assertEqual(command[command.index("--iq-segment-repair-passes") + 1], "2")
        self.assertIn("--sync-search-window-symbols", command)
        self.assertEqual(command[command.index("--sync-search-window-symbols") + 1], "4096")
        self.assertIn("--min-sync-metric", command)
        self.assertEqual(command[command.index("--min-sync-metric") + 1], "0.05")
        self.assertIn("--sync-profile", command)
        self.assertEqual(command[command.index("--sync-profile") + 1], "fast-first")
        self.assertIn("--fast-sync-candidates", command)
        self.assertEqual(command[command.index("--fast-sync-candidates") + 1], "4")
        self.assertIn("--fast-sync-search-window-symbols", command)
        self.assertEqual(command[command.index("--fast-sync-search-window-symbols") + 1], "1024")
        self.assertIn("--fallback-sync-candidates", command)
        self.assertEqual(command[command.index("--fallback-sync-candidates") + 1], "12")
        self.assertIn("--fallback-sync-search-window-symbols", command)
        self.assertEqual(command[command.index("--fallback-sync-search-window-symbols") + 1], "4096")
        self.assertIn("--retry-on-burst-miss", command)
        self.assertIn("--retry-on-low-sync", command)
        self.assertIn("--low-sync-retry-threshold", command)
        self.assertEqual(command[command.index("--low-sync-retry-threshold") + 1], "0.08")
        self.assertIn("--remote-decoded-format", command)
        self.assertEqual(command[command.index("--remote-decoded-format") + 1], "npy")
        self.assertIn("--no-robust-sync", command)
        self.assertFalse(job._shutdown_after_transport)
        self.assertEqual(job._runner_env["REMOTE_USRP_PROJECT_ROOT"], "/home/user")
        self.assertEqual(job._runner_env["REMOTE_DECODE_PYTHON"], "/home/user/venv/bin/python")
        sync_decode_assets.assert_called_once()
        _, sync_kwargs = sync_decode_assets.call_args
        self.assertEqual(sync_kwargs["remote_project_root"], "/home/user")

    def test_usrp_iq_direct_tvm_runner_defaults_to_remote_dir_decode(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            latent_dir = temp_dir / "latents"
            latent_dir.mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "OPENAMP_DEMO_LOCAL_LATENT_DIR": str(latent_dir),
                    "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED": "0",
                    "JSCC_LINK_MODE": "iq-direct",
                    "OPENAMP_USRP_TX_RUNNER": "docker",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                    "REMOTE_TVM_PYTHON": "env OMP_NUM_THREADS=3 /home/user/anaconda3/envs/tvm310_safe/bin/python",
                },
                source_summary="test",
            )

            def fake_prepare_wire_input_dir(*, output_dir: Path, **_: object) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                return {"prepared_count": 1}

            with (
                patch("usrp_runtime.threading.Thread", FakeThread),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_ensure_host_latents", return_value=latent_dir),
                patch("usrp_runtime._prepare_wire_input_dir", side_effect=fake_prepare_wire_input_dir),
                patch("usrp_runtime._enrich_wire_manifest_with_host_images", side_effect=lambda manifest, *_: manifest),
                patch("usrp_runtime._ensure_usrp_control_servers", return_value=(True, {})),
                patch("usrp_runtime._sync_iq_decode_assets_on_remote", create=True),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_wait_for_completion", return_value=None),
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=1234)),
            ):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=1,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                )
                job._start_and_watch()
                job._log_handle.close()

        command = job._runner_command
        self.assertIn("RunAnalogLatentBatch.py", str(command[1]))
        self.assertIn("--remote-decode-result-mode", command)
        self.assertEqual(command[command.index("--remote-decode-result-mode") + 1], "remote-dir")
        self.assertIn("--remote-decoded-output-dir", command)
        self.assertEqual(
            command[command.index("--remote-decoded-output-dir") + 1],
            f"/home/user/cockpit_usrp_rx/{job._run_id}_rx",
        )
        self.assertEqual(job._runner_env["REMOTE_DECODE_PYTHON"], "/home/user/venv/bin/python")

    def test_usrp_iq_direct_runner_respects_explicit_sync_overrides(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            latent_dir = temp_dir / "latents"
            latent_dir.mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "OPENAMP_DEMO_LOCAL_LATENT_DIR": str(latent_dir),
                    "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED": "0",
                    "JSCC_LINK_MODE": "iq-direct",
                    "OPENAMP_USRP_TX_RUNNER": "docker",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                    "ANALOG_MIN_SYNC_METRIC": "0.25",
                    "ANALOG_ROBUST_SYNC": "1",
                    "ANALOG_PIPELINE_DEPTH": "2",
                    "ANALOG_PIPELINE_RF_DECODE_OVERLAP": "1",
                    "ANALOG_RX_SESSION_CONTROL": "1",
                    "ANALOG_RX_BATCH_SESSION_CONTROL": "1",
                    "ANALOG_RX_BATCH_SESSION_MAX_IMAGES": "16",
                    "ANALOG_RX_HEALTH_RESET_ON_STALL": "1",
                    "ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC": "0.75",
                    "ANALOG_RX_ARM_STATUS_TIMEOUT_SEC": "0.5",
                    "ANALOG_RX_ARM_STATUS_POLL_SEC": "0.025",
                    "ANALOG_RX_WAIT_TIMEOUT_SEC": "1.0",
                    "OPENAMP_IQ_SEGMENT_SIZE": "0",
                    "OPENAMP_IQ_SEGMENT_REPAIR_PASSES": "0",
                },
                source_summary="test",
            )

            def fake_prepare_wire_input_dir(*, output_dir: Path, **_: object) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                return {"prepared_count": 1}

            with (
                patch("usrp_runtime.threading.Thread", FakeThread),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_ensure_host_latents", return_value=latent_dir),
                patch("usrp_runtime._prepare_wire_input_dir", side_effect=fake_prepare_wire_input_dir),
                patch("usrp_runtime._enrich_wire_manifest_with_host_images", side_effect=lambda manifest, *_: manifest),
                patch("usrp_runtime._ensure_usrp_control_servers", return_value=(True, {})),
                patch("usrp_runtime._sync_iq_decode_assets_on_remote", create=True),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_wait_for_completion", return_value=None),
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=1234)),
            ):
                job = usrp_runtime.UsrpBatchSpoolJob(access, variant="current", max_inputs=1)
                job._start_and_watch()
                job._log_handle.close()

        command = job._runner_command
        self.assertIn("--min-sync-metric", command)
        self.assertEqual(command[command.index("--min-sync-metric") + 1], "0.25")
        self.assertIn("--robust-sync", command)
        self.assertNotIn("--no-robust-sync", command)
        self.assertIn("--pipeline-depth", command)
        self.assertEqual(command[command.index("--pipeline-depth") + 1], "2")
        self.assertIn("--pipeline-rf-decode-overlap", command)
        self.assertIn("--rx-session-control", command)
        self.assertIn("--rx-batch-session-control", command)
        self.assertIn("--rx-batch-session-max-images", command)
        self.assertEqual(command[command.index("--rx-batch-session-max-images") + 1], "16")
        self.assertIn("--rx-health-reset-on-stall", command)
        self.assertIn("--rx-health-stall-threshold-sec", command)
        self.assertEqual(command[command.index("--rx-health-stall-threshold-sec") + 1], "0.75")
        self.assertIn("--rx-arm-status-timeout-sec", command)
        self.assertEqual(command[command.index("--rx-arm-status-timeout-sec") + 1], "0.5")
        self.assertIn("--rx-arm-status-poll-sec", command)
        self.assertEqual(command[command.index("--rx-arm-status-poll-sec") + 1], "0.025")
        self.assertIn("--rx-wait-timeout-sec", command)
        self.assertEqual(command[command.index("--rx-wait-timeout-sec") + 1], "1.0")
        self.assertIn("--iq-segment-size", command)
        self.assertEqual(command[command.index("--iq-segment-size") + 1], "0")
        self.assertIn("--iq-segment-repair-passes", command)
        self.assertEqual(command[command.index("--iq-segment-repair-passes") + 1], "0")

    def test_usrp_iq_direct_runner_can_override_rx_capture_mode_to_remote_pull(self) -> None:
        class FakeThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            latent_dir = temp_dir / "latents"
            latent_dir.mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "OPENAMP_DEMO_LOCAL_LATENT_DIR": str(latent_dir),
                    "OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED": "0",
                    "JSCC_LINK_MODE": "iq-direct",
                    "RX_CAPTURE_MODE": "remote-pull",
                    "OPENAMP_USRP_TX_RUNNER": "docker",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            def fake_prepare_wire_input_dir(*, output_dir: Path, **_: object) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                return {"prepared_count": 1}

            with (
                patch("usrp_runtime.threading.Thread", FakeThread),
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_ensure_host_latents", return_value=latent_dir),
                patch("usrp_runtime._prepare_wire_input_dir", side_effect=fake_prepare_wire_input_dir),
                patch("usrp_runtime._enrich_wire_manifest_with_host_images", side_effect=lambda manifest, *_: manifest),
                patch("usrp_runtime._ensure_usrp_control_servers", return_value=(True, {})),
                patch("usrp_runtime._sync_iq_decode_assets_on_remote", create=True) as sync_decode_assets,
                patch.object(usrp_runtime.UsrpBatchSpoolJob, "_wait_for_completion", return_value=None),
                patch("usrp_runtime.subprocess.Popen", return_value=Mock(pid=1234)),
            ):
                job = usrp_runtime.UsrpBatchSpoolJob(access, variant="current", max_inputs=1)
                job._start_and_watch()
                job._log_handle.close()

        command = job._runner_command
        self.assertIn("--rx-capture-mode", command)
        self.assertEqual(command[command.index("--rx-capture-mode") + 1], "remote-pull")
        sync_decode_assets.assert_not_called()

    def test_usrp_iq_remote_decode_reuses_board_output_dir_for_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            captured: dict[str, object] = {}
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            def fake_inference(remote_stage_manifest: dict[str, object], progress) -> dict[str, object]:
                captured["remote_stage_manifest"] = dict(remote_stage_manifest)
                progress(1, 1)
                return {
                    "status": "ok",
                    "processed_count": 1,
                    "selected_input_count": 1,
                    "run_samples_ms": [252.0],
                    "run_mean_ms": 252.0,
                    "run_median_ms": 252.0,
                }

            job = usrp_runtime.UsrpBatchSpoolJob(
                access,
                variant="current",
                max_inputs=1,
                inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                inference_callback=fake_inference,
            )
            job._run_dir.mkdir(parents=True, exist_ok=True)
            job._summary_path.write_text(
                json.dumps(
                    {
                        "target_count": 1,
                        "completed_count": 1,
                        "pass_count": 1,
                        "failed_count": 0,
                        "all_pass": True,
                        "remote_decode_result_mode": "remote-dir",
                        "remote_decoded_output_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_123_rx",
                        "images": [
                            {
                                "index": 0,
                                "passed": True,
                                "round_records": [
                                    {
                                        "remote_received_latent_npz": "/home/user/cockpit_usrp_rx/cockpit_usrp_123_rx/00000000.npz",
                                        "sync_success": True,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            job._log_path.write_text("", encoding="utf-8")
            job._process = Mock()
            job._process.wait.return_value = 0
            job._log_handle = Mock()

            with (
                patch("usrp_runtime._stage_merged_wire_blobs_for_remote_decode") as stage_wire,
                patch("usrp_runtime._sync_and_decode_wire_blobs_on_remote") as sync_wire,
            ):
                stage_wire.side_effect = AssertionError("IQ remote-dir should not restage local wire blobs")
                sync_wire.side_effect = AssertionError("IQ remote-dir should not upload decoded outputs back to board")
                job._wait_for_completion()

        manifest = captured["remote_stage_manifest"]
        self.assertEqual(manifest["remote_dir"], "/home/user/cockpit_usrp_rx/cockpit_usrp_123_rx")
        self.assertEqual(manifest["decode_location"], "board")
        self.assertEqual(manifest["decode_manifest"]["decoded_count"], 1)

    def test_usrp_iq_remote_decode_can_start_tvm_before_transport_completes(self) -> None:
        class NoStartThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        class ImmediateThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon
                self._alive = False

            def start(self) -> None:
                self.target()

            def join(self, timeout=None) -> None:
                return None

            def is_alive(self) -> bool:
                return self._alive

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            captured: dict[str, object] = {}
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "OPENAMP_IQ_STREAMING_TVM": "1",
                    "OPENAMP_IQ_STREAMING_MIN_READY": "1",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            def fake_inference(remote_stage_manifest: dict[str, object], progress) -> dict[str, object]:
                captured["remote_stage_manifest"] = dict(remote_stage_manifest)
                progress(1, 3)
                return {"status": "ok", "processed_count": 1, "selected_input_count": 3}

            with patch("usrp_runtime.threading.Thread", NoStartThread):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=3,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                    inference_callback=fake_inference,
                )
            job._iq_remote_decoded_output_dir = "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx"
            image_dir = job._run_dir / "image_0000"
            image_dir.mkdir(parents=True)
            (image_dir / "decode_summary.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "frame_complete": True,
                        "remote_received_latent_npz": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz",
                    }
                ),
                encoding="utf-8",
            )

            with patch("usrp_runtime.threading.Thread", ImmediateThread):
                started = job._maybe_start_iq_streaming_inference()

        self.assertTrue(started)
        manifest = captured["remote_stage_manifest"]
        self.assertEqual(manifest["remote_dir"], "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx")
        self.assertEqual(manifest["decode_manifest"]["decoded_count"], 1)
        self.assertEqual(job._inference_completed, 1)
        self.assertEqual(job._inference_total, 3)

    def test_usrp_iq_remote_decode_streaming_tvm_waits_for_min_ready_count(self) -> None:
        class NoStartThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "OPENAMP_IQ_STREAMING_TVM": "1",
                    "OPENAMP_IQ_STREAMING_MIN_READY": "10",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            with patch("usrp_runtime.threading.Thread", NoStartThread):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=30,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                    inference_callback=lambda *_args: {"status": "ok"},
                )
            job._iq_remote_decoded_output_dir = "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx"

            for index in range(9):
                image_dir = job._run_dir / f"image_{index:04d}"
                image_dir.mkdir(parents=True)
                (image_dir / "decode_summary.json").write_text(
                    json.dumps(
                        {
                            "status": "ok",
                            "frame_complete": True,
                            "remote_received_latent_npz": (
                                f"/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/{index:08d}.npz"
                            ),
                        }
                    ),
                    encoding="utf-8",
                )

            self.assertFalse(job._maybe_start_iq_streaming_inference())
            self.assertFalse(job._inference_started)

            image_dir = job._run_dir / "image_0009"
            image_dir.mkdir(parents=True)
            (image_dir / "decode_summary.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "frame_complete": True,
                        "remote_received_latent_npz": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000009.npz",
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(job._maybe_start_iq_streaming_inference())
            self.assertTrue(job._inference_started)
            self.assertEqual(job._remote_stage_manifest["decode_manifest"]["decoded_count"], 10)

    def test_usrp_iq_remote_decode_streaming_tvm_is_opt_in(self) -> None:
        class NoStartThread:
            def __init__(self, *, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )
            with patch("usrp_runtime.threading.Thread", NoStartThread):
                job = usrp_runtime.UsrpBatchSpoolJob(
                    access,
                    variant="current",
                    max_inputs=3,
                    inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                    inference_callback=lambda *_args: {"status": "ok"},
                )
            job._iq_remote_decoded_output_dir = "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx"
            image_dir = job._run_dir / "image_0000"
            image_dir.mkdir(parents=True)
            (image_dir / "decode_summary.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "frame_complete": True,
                        "remote_received_latent_npz": "/home/user/cockpit_usrp_rx/cockpit_usrp_stream_rx/00000000.npz",
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(job._maybe_start_iq_streaming_inference())

    def test_usrp_iq_remote_decode_refuses_control_plane_wire_restaging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            (temp_dir / "runs").mkdir()
            access = usrp_runtime.BoardAccessConfig(
                host="100.121.87.73",
                user="user",
                password="user",
                port="22",
                env_file=None,
                env_values={
                    "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                    "REMOTE_USRP_RX_DIR": "/home/user/cockpit_usrp_rx",
                    "JSCC_LINK_MODE": "iq-direct",
                    "MLKEM_USRP_RUN_ROOT": str(temp_dir / "runs"),
                },
                source_summary="test",
            )

            job = usrp_runtime.UsrpBatchSpoolJob(
                access,
                variant="current",
                max_inputs=1,
                inference_engine=usrp_runtime.INFERENCE_ENGINE_TVM,
                inference_callback=lambda *_args, **_kwargs: {"status": "ok"},
            )
            job._run_dir.mkdir(parents=True, exist_ok=True)
            job._summary_path.write_text(
                json.dumps(
                    {
                        "target_count": 1,
                        "completed_count": 1,
                        "pass_count": 1,
                        "failed_count": 0,
                        "all_pass": True,
                        "remote_decode_result_mode": "pull",
                        "images": [{"index": 0, "passed": True}],
                    }
                ),
                encoding="utf-8",
            )
            job._log_path.write_text("", encoding="utf-8")
            job._process = Mock()
            job._process.wait.return_value = 0
            job._log_handle = Mock()

            with (
                patch("usrp_runtime._stage_merged_wire_blobs_for_remote_decode") as stage_wire,
                patch("usrp_runtime._sync_and_decode_wire_blobs_on_remote") as sync_wire,
            ):
                job._wait_for_completion()

        stage_wire.assert_not_called()
        sync_wire.assert_not_called()
        snapshot = job.snapshot()
        self.assertEqual(snapshot["status"], "fallback")
        self.assertIn("IQ-direct", snapshot["message"])
        self.assertIn("remote-dir", snapshot["message"])

    def test_sync_iq_decode_assets_skips_upload_when_remote_hashes_match(self) -> None:
        import hashlib

        usrp_runtime._IQ_DECODE_ASSET_SYNC_CACHE.clear()
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        asset_pairs = (
            (usrp_runtime.REPO_ROOT / "USRP292x" / "AnalogLatentLink.py", "/home/user/USRP292x/AnalogLatentLink.py"),
            (usrp_runtime.ROOT_SCRIPTS / "latent_transport.py", "/home/user/scripts/latent_transport.py"),
            (usrp_runtime.REPO_ROOT / "USRP292x" / "OtaRxPersistentServer.cpp", "/home/user/USRP292x/OtaRxPersistentServer.cpp"),
            (usrp_runtime.REPO_ROOT / "USRP292x" / "OtaRxPersistentServer.sh", "/home/user/USRP292x/OtaRxPersistentServer.sh"),
            (usrp_runtime.REPO_ROOT / "USRP292x" / "OtaTxPersistentServer.cpp", "/home/user/USRP292x/OtaTxPersistentServer.cpp"),
            (usrp_runtime.REPO_ROOT / "USRP292x" / "OtaTxPersistentServer.sh", "/home/user/USRP292x/OtaTxPersistentServer.sh"),
            (usrp_runtime.REPO_ROOT / "USRP292x" / "BuildOtaTools.sh", "/home/user/USRP292x/BuildOtaTools.sh"),
        )
        stdout = "".join(
            f"{hashlib.sha256(local_path.read_bytes()).hexdigest()}  {remote_path}\n"
            for local_path, remote_path in asset_pairs
        ).encode("utf-8")
        calls: list[str] = []

        def fake_run_remote_command(_access, remote_command, **_kwargs):  # type: ignore[no-untyped-def]
            calls.append(str(remote_command))
            if "scp" in remote_command:
                raise AssertionError("matching remote IQ assets should not be uploaded")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=stdout, stderr=b"")

        with patch("usrp_runtime._run_remote_command", side_effect=fake_run_remote_command):
            result = usrp_runtime._sync_iq_decode_assets_on_remote(
                access,
                remote_project_root="/home/user",
            )

        self.assertEqual(result["status"], "current")
        self.assertEqual(len(calls), 1)
        self.assertIn("chmod +x", calls[0])
        self.assertIn("sha256sum", calls[0])

    def test_sync_iq_decode_assets_uploads_tar_through_ssh_helper(self) -> None:
        usrp_runtime._IQ_DECODE_ASSET_SYNC_CACHE.clear()
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        calls: list[tuple[str, dict[str, object]]] = []

        def fake_run_remote_command(_access, remote_command, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((str(remote_command), dict(kwargs)))
            self.assertNotIn("scp", remote_command)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"", stderr=b"")
            if len(calls) == 2:
                self.assertGreater(len(kwargs.get("input_data") or b""), 0)
            else:
                self.assertIsNone(kwargs.get("input_data"))
                self.assertIn("BuildOtaTools.sh", remote_command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"", stderr=b"")

        with patch("usrp_runtime._run_remote_command", side_effect=fake_run_remote_command):
            result = usrp_runtime._sync_iq_decode_assets_on_remote(
                access,
                remote_project_root="/home/user",
            )

        self.assertEqual(result["status"], "uploaded")
        self.assertEqual(len(calls), 3)
        self.assertIn("tar xzf", calls[1][0])
        self.assertIn("chmod +x", calls[1][0])
        self.assertIn("OtaRxPersistentServer.sh", calls[1][0])
        self.assertIn("OtaTxPersistentServer.sh", calls[1][0])
        self.assertGreaterEqual(float(calls[1][1]["timeout"]), 90.0)
        self.assertIn("BuildOtaTools.sh", calls[2][0])
        self.assertGreaterEqual(float(calls[2][1]["timeout"]), 120.0)

    def test_ensure_usrp_control_servers_resets_iq_streamers_before_use(self) -> None:
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        commands: list[tuple[str, str, str]] = []

        def fake_control(host, port, line, **_kwargs):  # type: ignore[no-untyped-def]
            commands.append((str(host), str(port), str(line)))
            if line == "PING":
                return "OK pong=1"
            if line == "RESET":
                return "OK reset=1 busy=0"
            raise AssertionError(f"unexpected command: {line}")

        with patch("usrp_runtime._tcp_control_command", side_effect=fake_control):
            ready, details = usrp_runtime._ensure_usrp_control_servers(
                access,
                {},
                rx_host="100.121.87.73",
                rx_port="29220",
                tx_host="127.0.0.1",
                tx_port="29221",
                remote_run_root="/tmp/usrp292x_remote_runs",
                remote_project_root="/home/user",
                auto_start=False,
                require_reset=True,
                log_dir=usrp_runtime.REPO_ROOT / "USRP292x" / "server_logs",
            )

        self.assertTrue(ready)
        self.assertEqual([line for _, _, line in commands].count("RESET"), 2)
        self.assertEqual(details["rx_control"]["reset_response"], "OK reset=1 busy=0")
        self.assertEqual(details["tx_control"]["reset_response"], "OK reset=1 busy=0")

    def test_ensure_usrp_control_servers_restarts_legacy_iq_servers(self) -> None:
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        reset_calls = 0

        def fake_control(_host, _port, line, **_kwargs):  # type: ignore[no-untyped-def]
            nonlocal reset_calls
            if line == "PING":
                return "OK pong=1"
            if line == "RESET":
                reset_calls += 1
                return "ERR error=unknown_command" if reset_calls <= 2 else "OK reset=1 busy=0"
            if line in {"STOP", "QUIT"}:
                return "OK"
            raise AssertionError(f"unexpected command: {line}")

        with (
            patch("usrp_runtime._tcp_control_command", side_effect=fake_control),
            patch("usrp_runtime._start_remote_rx_server", return_value={"status": "started"}) as start_rx,
            patch("usrp_runtime._start_local_tx_server", return_value={"status": "started"}) as start_tx,
            patch("usrp_runtime.time.sleep"),
        ):
            ready, details = usrp_runtime._ensure_usrp_control_servers(
                access,
                {},
                rx_host="100.121.87.73",
                rx_port="29220",
                tx_host="127.0.0.1",
                tx_port="29221",
                remote_run_root="/tmp/usrp292x_remote_runs",
                remote_project_root="/home/user",
                auto_start=True,
                require_reset=True,
                log_dir=usrp_runtime.REPO_ROOT / "USRP292x" / "server_logs",
            )

        self.assertTrue(ready)
        start_rx.assert_called_once()
        start_tx.assert_called_once()
        self.assertEqual(reset_calls, 4)
        self.assertEqual(details["reset_upgrade_shutdown"]["status"], "completed")

    def test_sync_iq_decode_assets_reuses_successful_sync_in_process(self) -> None:
        usrp_runtime._IQ_DECODE_ASSET_SYNC_CACHE.clear()
        access = usrp_runtime.BoardAccessConfig(
            host="100.121.87.73",
            user="user",
            password="user",
            port="22",
            env_file=None,
            env_values={},
            source_summary="test",
        )
        calls: list[tuple[str, dict[str, object]]] = []

        def fake_run_remote_command(_access, remote_command, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((str(remote_command), dict(kwargs)))
            if len(calls) == 1:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"", stderr=b"")
            if len(calls) == 2:
                self.assertGreater(len(kwargs.get("input_data") or b""), 0)
            else:
                self.assertIsNone(kwargs.get("input_data"))
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"", stderr=b"")

        with patch("usrp_runtime._run_remote_command", side_effect=fake_run_remote_command):
            first = usrp_runtime._sync_iq_decode_assets_on_remote(
                access,
                remote_project_root="/home/user",
            )
            second = usrp_runtime._sync_iq_decode_assets_on_remote(
                access,
                remote_project_root="/home/user",
            )

        self.assertEqual(first["status"], "uploaded")
        self.assertEqual(second["status"], "cached")
        self.assertEqual(second["uploaded_bytes"], 0)
        self.assertEqual(len(calls), 3)

    def test_main_builds_server_and_serves_without_startup_probe(self) -> None:
        args = Namespace(
            host="0.0.0.0",
            port=8090,
            probe_env="config/openamp.env",
            aircraft_position_env="",
            probe_timeout_sec=12.5,
            probe_startup=False,
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )
        events: list[str] = []
        fake_app_state = Mock()
        fake_server = Mock()

        def build_state(
            probe_env: str,
            probe_timeout_sec: float,
            demo_startup_env_overrides: dict[str, str] | None = None,
            event_archive_root: str | Path | None = None,
            bind_host: str = "127.0.0.1",
            bind_port: int = 8079,
        ) -> Mock:
            events.append("state_init")
            self.assertEqual(probe_env, args.probe_env)
            self.assertEqual(probe_timeout_sec, args.probe_timeout_sec)
            self.assertEqual(demo_startup_env_overrides, {})
            self.assertEqual(event_archive_root, server.default_event_archive_root())
            self.assertEqual(bind_host, args.host)
            self.assertEqual(bind_port, args.port)
            return fake_app_state

        def build_server(server_address: tuple[str, int], handler: type[DemoRequestHandler], app_state: Mock) -> Mock:
            events.append("server_init")
            self.assertEqual(server_address, (args.host, args.port))
            self.assertIs(handler, DemoRequestHandler)
            self.assertIs(app_state, fake_app_state)
            return fake_server

        fake_server.serve_forever.side_effect = lambda: events.append("serve_forever")

        with (
            patch("server.parse_args", return_value=args),
            patch("server.DashboardState", side_effect=build_state) as state_cls,
            patch("server.DemoHTTPServer", side_effect=build_server) as server_cls,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = server.main()

        state_cls.assert_called_once_with(
            args.probe_env,
            args.probe_timeout_sec,
            demo_startup_env_overrides={},
            event_archive_root=server.default_event_archive_root(),
            bind_host=args.host,
            bind_port=args.port,
        )
        server_cls.assert_called_once_with((args.host, args.port), DemoRequestHandler, fake_app_state)
        fake_app_state.refresh_live_probe.assert_not_called()
        fake_server.serve_forever.assert_called_once_with()
        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["state_init", "server_init", "serve_forever"])
        self.assertEqual(
            stdout.getvalue().splitlines(),
            [
                "Feiteng semantic visual return demo dashboard: http://0.0.0.0:8090",
                f"Project root: {server.PROJECT_ROOT}",
            ],
        )

    def test_main_runs_startup_probe_before_starting_server(self) -> None:
        args = Namespace(
            host="127.0.0.1",
            port=8079,
            probe_env="config/probe.env",
            aircraft_position_env="",
            probe_timeout_sec=5.0,
            probe_startup=True,
            demo_admission_mode="",
            signed_manifest_file="",
            signed_manifest_public_key="",
            baseline_admission_mode="",
            baseline_signed_manifest_file="",
            baseline_signed_manifest_public_key="",
        )
        events: list[str] = []
        fake_app_state = Mock()
        fake_server = Mock()

        def build_state(
            probe_env: str,
            probe_timeout_sec: float,
            demo_startup_env_overrides: dict[str, str] | None = None,
            event_archive_root: str | Path | None = None,
            bind_host: str = "127.0.0.1",
            bind_port: int = 8079,
        ) -> Mock:
            events.append("state_init")
            self.assertEqual(probe_env, args.probe_env)
            self.assertEqual(probe_timeout_sec, args.probe_timeout_sec)
            self.assertEqual(demo_startup_env_overrides, {})
            self.assertEqual(event_archive_root, server.default_event_archive_root())
            self.assertEqual(bind_host, args.host)
            self.assertEqual(bind_port, args.port)
            return fake_app_state

        def build_server(server_address: tuple[str, int], handler: type[DemoRequestHandler], app_state: Mock) -> Mock:
            events.append("server_init")
            self.assertEqual(server_address, (args.host, args.port))
            self.assertIs(handler, DemoRequestHandler)
            self.assertIs(app_state, fake_app_state)
            return fake_server

        fake_app_state.refresh_live_probe.side_effect = lambda: events.append("refresh_live_probe")
        fake_server.serve_forever.side_effect = lambda: events.append("serve_forever")

        with (
            patch("server.parse_args", return_value=args),
            patch("server.DashboardState", side_effect=build_state) as state_cls,
            patch("server.DemoHTTPServer", side_effect=build_server) as server_cls,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = server.main()

        state_cls.assert_called_once_with(
            args.probe_env,
            args.probe_timeout_sec,
            demo_startup_env_overrides={},
            event_archive_root=server.default_event_archive_root(),
            bind_host=args.host,
            bind_port=args.port,
        )
        server_cls.assert_called_once_with((args.host, args.port), DemoRequestHandler, fake_app_state)
        fake_app_state.refresh_live_probe.assert_called_once_with()
        fake_server.serve_forever.assert_called_once_with()
        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["state_init", "refresh_live_probe", "server_init", "serve_forever"])


class DemoHTTPServerTest(unittest.TestCase):
    def test_snapshot_endpoint_returns_expected_high_level_fields(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, payload = request_json(state, "GET", "/api/snapshot")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertIn("generated_at", payload)
        self.assertEqual(payload["project"]["name"], "飞腾多核弱网安全语义视觉回传系统")
        self.assertEqual(payload["mode"]["effective_label"], "仅展示证据")
        self.assertIn("current_status", payload["board"])
        self.assertIn("latest_live_status", payload)
        self.assertIn("PyTorch reference archive", payload["latest_live_status"]["headline"])
        self.assertEqual(payload["latest_live_status"]["baseline"]["completed"], "300 / 300 (archive)")
        self.assertIn("fits", payload)
        self.assertIsInstance(payload["fits"], list)

    def test_health_endpoint_returns_ok_payload(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, payload = request_json(state, "GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(payload, {"status": "ok"})

    def test_link_director_status_endpoint_returns_default_scaffold_state(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, payload = request_json(state, "GET", "/api/link-director")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(payload["selected_profile_id"], "normal")
        self.assertEqual(payload["selected_profile_label"], "正常链路")
        self.assertEqual(payload["selected_profile"]["profile_id"], "normal")
        self.assertEqual(payload["backend_binding"], "ui_scaffold_only")
        self.assertEqual(payload["backend_status"], "ui_scaffold_only")
        self.assertEqual(payload["selected_profile"]["evidence_binding"]["mode"], "live_anchor")
        self.assertIn("不执行 tc/netem", payload["summary"])
        self.assertIn("live 控制面与证据读数继续如实显示", payload["truth_note"])

    def test_link_director_profile_endpoint_switches_profile_and_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            status, headers, payload = request_json(
                state,
                "POST",
                "/api/link-director/profile",
                body=json.dumps({"profile_id": "lossy"}).encode("utf-8"),
            )
            current_status, _, current_payload = request_json(state, "GET", "/api/link-director")
            event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=10")
            archive = event_payload["aggregate"]["archive"]
            events_path = Path(archive["events_jsonl"])
            archived_events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertTrue(payload["change_applied"])
        self.assertEqual(payload["previous_profile_id"], "normal")
        self.assertEqual(payload["selected_profile_id"], "lossy")
        self.assertEqual(payload["selected_profile_label"], "高丢包")
        self.assertEqual(payload["selected_profile"]["evidence_binding"]["scenario_id"], "snr10_real_compare")
        self.assertIn("未执行 tc/netem", payload["status_message"])
        self.assertEqual(current_status, 200)
        self.assertEqual(current_payload["selected_profile_id"], "lossy")
        self.assertEqual(event_status, 200)
        self.assertEqual(event_payload["aggregate"]["link_profile"]["selected_profile_id"], "lossy")
        self.assertEqual(event_payload["aggregate"]["link_profile"]["selected_profile_label"], "高丢包")
        event_types = [item["type"] for item in event_payload["recent_events"]]
        self.assertIn("LINK_PROFILE_CHANGED", event_types)
        self.assertIn("ARCHIVE_SNAPSHOT_WRITTEN", event_types)
        link_profile_events = [event for event in archived_events if event["type"] == "LINK_PROFILE_CHANGED"]
        self.assertEqual(len(link_profile_events), 1)
        self.assertEqual(link_profile_events[0]["data"]["profile_id"], "lossy")
        self.assertEqual(link_profile_events[0]["data"]["previous_profile_id"], "normal")

    def test_link_director_profile_endpoint_is_honest_noop_when_profile_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            status, _, payload = request_json(
                state,
                "POST",
                "/api/link-director/profile",
                body=json.dumps({"profile_id": "normal"}).encode("utf-8"),
            )
            event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=10")

        self.assertEqual(status, 200)
        self.assertFalse(payload["change_applied"])
        self.assertEqual(payload["selected_profile_id"], "normal")
        self.assertIn("UI/control-plane scaffold", payload["status_message"])
        self.assertEqual(event_status, 200)
        self.assertEqual(event_payload["aggregate"]["event_count"], 0)
        self.assertEqual(event_payload["recent_events"], [])

    def test_link_director_profile_endpoint_rejects_unsupported_profiles(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, payload = request_json(
            state,
            "POST",
            "/api/link-director/profile",
            body=json.dumps({"profile_id": "not-real"}).encode("utf-8"),
        )

        self.assertEqual(status, 400)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload, {"status": "error", "message": "unsupported profile_id"})

    def test_archive_sessions_endpoint_lists_local_archive_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            write_archive_session(
                temp_dir,
                session_id="session_archive_old",
                events=[
                    archive_event(
                        session_id="session_archive_old",
                        sequence=1,
                        timestamp="2026-03-19T09:00:00+08:00",
                        event_type="JOB_SUBMITTED",
                        message="Old archive session submitted a demo job.",
                    ),
                    archive_event(
                        session_id="session_archive_old",
                        sequence=2,
                        timestamp="2026-03-19T09:00:02+08:00",
                        event_type="ARCHIVE_SNAPSHOT_WRITTEN",
                        plane="archive",
                        mode_scope="demo archive / local event evidence",
                        message="Event spine snapshot written (job_done).",
                        data={"reason": "job_done", "path": f"{temp_dir}/session_archive_old/state_snapshot.json"},
                    ),
                ],
                snapshot={
                    "generated_at": "2026-03-19T09:00:02+08:00",
                    "session_id": "session_archive_old",
                    "reason": "job_done",
                    "mode_boundary_note": server.MODE_BOUNDARY_NOTE,
                    "aggregate": {"session_id": "session_archive_old", "started_at": "2026-03-19T09:00:00+08:00"},
                    "recent_events": [],
                    "extra": {"variant": "current"},
                },
            )
            write_archive_session(
                temp_dir,
                session_id="session_archive_new",
                events=[
                    archive_event(
                        session_id="session_archive_new",
                        sequence=1,
                        timestamp="2026-03-19T11:15:00+08:00",
                        event_type="SAFE_STOP_TRIGGERED",
                        message="Heartbeat timeout triggered SAFE_STOP cleanup.",
                        data={"reason": "heartbeat_timeout_cleanup"},
                    ),
                    archive_event(
                        session_id="session_archive_new",
                        sequence=2,
                        timestamp="2026-03-19T11:15:03+08:00",
                        event_type="ARCHIVE_SNAPSHOT_WRITTEN",
                        plane="archive",
                        mode_scope="demo archive / local event evidence",
                        message="Event spine snapshot written (fault_heartbeat_timeout).",
                        data={"reason": "fault_heartbeat_timeout", "path": f"{temp_dir}/session_archive_new/state_snapshot.json"},
                    ),
                ],
                snapshot={
                    "generated_at": "2026-03-19T11:15:03+08:00",
                    "session_id": "session_archive_new",
                    "reason": "fault_heartbeat_timeout",
                    "mode_boundary_note": server.MODE_BOUNDARY_NOTE,
                    "aggregate": {"session_id": "session_archive_new", "started_at": "2026-03-19T11:15:00+08:00"},
                    "recent_events": [],
                    "extra": {"fault_type": "heartbeat_timeout"},
                },
            )
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            status, headers, payload = request_json(state, "GET", "/api/archive/sessions?limit=10")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload["session_count"], 2)
        self.assertEqual(
            [item["session_id"] for item in payload["sessions"]],
            ["session_archive_new", "session_archive_old"],
        )
        self.assertEqual(payload["sessions"][0]["last_snapshot_reason"], "fault_heartbeat_timeout")
        self.assertTrue(payload["sessions"][0]["has_events"])
        self.assertTrue(payload["sessions"][0]["has_snapshot"])
        self.assertTrue(payload["sessions"][0]["paths"]["events_jsonl"].endswith("session_archive_new/events.jsonl"))

    def test_archive_session_endpoint_replays_recent_events_and_snapshot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_id = "session_archive_job_done"
            events = [
                archive_event(
                    session_id=session_id,
                    sequence=1,
                    timestamp="2026-03-19T10:00:00+08:00",
                    event_type="JOB_SUBMITTED",
                    message="Current live launch entered the archive session.",
                    job_id="job-42",
                    data={"variant": "current"},
                ),
                archive_event(
                    session_id=session_id,
                    sequence=2,
                    timestamp="2026-03-19T10:00:01+08:00",
                    event_type="JOB_ADMITTED",
                    message="OpenAMP admitted job-42.",
                    job_id="job-42",
                    data={"variant": "current"},
                ),
                archive_event(
                    session_id=session_id,
                    sequence=3,
                    timestamp="2026-03-19T10:00:02+08:00",
                    event_type="JOB_STARTED",
                    plane="data",
                    mode_scope=server.DATA_MODE_SCOPE,
                    message="Reconstruction execution started for job-42.",
                    job_id="job-42",
                    data={"variant": "current"},
                ),
                archive_event(
                    session_id=session_id,
                    sequence=4,
                    timestamp="2026-03-19T10:00:04+08:00",
                    event_type="FRAME_RECON_READY",
                    plane="data",
                    mode_scope=server.DATA_MODE_SCOPE,
                    message="Reconstruction output is ready for job-42.",
                    job_id="job-42",
                    data={"variant": "current"},
                ),
                archive_event(
                    session_id=session_id,
                    sequence=5,
                    timestamp="2026-03-19T10:00:05+08:00",
                    event_type="JOB_DONE",
                    plane="data",
                    mode_scope=server.DATA_MODE_SCOPE,
                    message="Reconstruction job job-42 completed.",
                    job_id="job-42",
                    data={"variant": "current", "total_ms": 128.4},
                ),
                archive_event(
                    session_id=session_id,
                    sequence=6,
                    timestamp="2026-03-19T10:00:06+08:00",
                    event_type="ARCHIVE_SNAPSHOT_WRITTEN",
                    plane="archive",
                    mode_scope="demo archive / local event evidence",
                    message="Event spine snapshot written (job_done).",
                    job_id="job-42",
                    data={"reason": "job_done", "path": f"{temp_dir}/{session_id}/state_snapshot.json"},
                ),
            ]
            write_archive_session(
                temp_dir,
                session_id=session_id,
                events=events,
                snapshot={
                    "generated_at": "2026-03-19T10:00:06+08:00",
                    "session_id": session_id,
                    "reason": "job_done",
                    "mode_boundary_note": server.MODE_BOUNDARY_NOTE,
                    "aggregate": {
                        "session_id": session_id,
                        "started_at": "2026-03-19T10:00:00+08:00",
                        "event_count": 5,
                    },
                    "recent_events": events[-3:],
                    "extra": {"variant": "current", "image_index": 12},
                },
            )
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            status, headers, payload = request_json(
                state,
                "GET",
                f"/api/archive/session?session_id={session_id}&limit=3",
            )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload["summary"]["session_id"], session_id)
        self.assertEqual(payload["summary"]["event_count"], 6)
        self.assertEqual(payload["summary"]["last_snapshot_reason"], "job_done")
        self.assertEqual(payload["aggregate"]["jobs"]["done_count"], 1)
        self.assertEqual(payload["aggregate"]["frames"]["ready_count"], 1)
        self.assertEqual(payload["snapshot"]["reason"], "job_done")
        self.assertEqual(payload["snapshot"]["extra"]["image_index"], 12)
        self.assertEqual(
            [item["type"] for item in payload["recent_events"]],
            ["ARCHIVE_SNAPSHOT_WRITTEN", "JOB_DONE", "FRAME_RECON_READY"],
        )
        self.assertEqual(payload["timeline"][0]["title"], "ARCHIVE_SNAPSHOT_WRITTEN")
        self.assertEqual(payload["timeline"][1]["lane"], "data")
        self.assertEqual(payload["timeline"][1]["job_id"], "job-42")
        self.assertTrue(payload["paths"]["state_snapshot_json"].endswith(f"{session_id}/state_snapshot.json"))

    def test_archive_session_endpoint_returns_404_for_missing_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            status, headers, payload = request_json(
                state,
                "GET",
                "/api/archive/session?session_id=missing-session",
            )

        self.assertEqual(status, 404)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload, {"status": "error", "message": "archive session not found: missing-session"})

    def test_event_spine_endpoint_tracks_live_inference_completion_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)
            request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
            )
            live_job = FakeInferenceJob(
                [
                    {
                        "status": "running",
                        "request_state": "running",
                        "status_category": "running",
                        "execution_mode": "live",
                        "variant": "current",
                        "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                        "runner_summary": {},
                        "wrapper_summary": {},
                        "diagnostics": {},
                        "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                        "artifacts": {},
                    },
                    {
                        "status": "success",
                        "request_state": "completed",
                        "status_category": "success",
                        "execution_mode": "live",
                        "variant": "current",
                        "message": "OpenAMP 控制面已完成作业下发、板端执行与结果回收。",
                        "runner_summary": {
                            "load_ms": 3.2,
                            "vm_init_ms": 0.8,
                            "run_median_ms": 128.4,
                            "artifact_sha256": "abcd" * 16,
                        },
                        "wrapper_summary": {"result": "success"},
                        "diagnostics": {},
                        "progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
                        "artifacts": {},
                    },
                ],
                job_id="m0-event-job-001",
            )

            with (
                patch(
                    "server.query_live_status",
                    return_value={
                        "status": "success",
                        "guard_state": "READY",
                        "active_job_id": 0,
                        "last_fault_code": "NONE",
                        "total_fault_count": 0,
                        "heartbeat_ok": 1,
                        "logs": [],
                    },
                ),
                patch("server.launch_remote_reconstruction_job", return_value=live_job),
            ):
                start_status, start_headers, start_payload = request_json(
                    state,
                    "POST",
                    "/api/run-inference",
                    body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
                )
                progress_status, _, progress_payload = request_json(
                    state,
                    "GET",
                    f"/api/inference-progress?job_id={live_job.job_id}",
                )
                event_status, event_headers, event_payload = request_json(state, "GET", "/api/event-spine?limit=20")

                archive = event_payload["aggregate"]["archive"]
                events_path = Path(archive["events_jsonl"])
                snapshot_path = Path(archive["state_snapshot_json"])
                archived_types = [
                    json.loads(line)["type"]
                    for line in events_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]

            self.assertEqual(start_status, 200)
            self.assertEqual(start_headers["content-type"], "application/json; charset=utf-8")
            self.assertEqual(start_payload["request_state"], "running")
            self.assertEqual(progress_status, 200)
            self.assertEqual(progress_payload["request_state"], "completed")
            self.assertEqual(event_status, 200)
            self.assertEqual(event_headers["cache-control"], "no-store")
            self.assertEqual(event_payload["status"], "ok")
            self.assertEqual(event_payload["aggregate"]["jobs"]["done_count"], 1)
            self.assertEqual(event_payload["aggregate"]["frames"]["ready_count"], 1)
            self.assertEqual(event_payload["aggregate"]["heartbeat"]["status"], "ok")
            self.assertTrue(archive["enabled"])
            self.assertTrue(events_path.is_file())
            self.assertTrue(snapshot_path.is_file())
            event_types = [item["type"] for item in event_payload["recent_events"]]
            for expected_type in (
                "JOB_SUBMITTED",
                "JOB_ADMITTED",
                "HEARTBEAT_OK",
                "JOB_STARTED",
                "FRAME_RECON_READY",
                "JOB_DONE",
                "ARCHIVE_SNAPSHOT_WRITTEN",
            ):
                with self.subTest(expected_type=expected_type):
                    self.assertIn(expected_type, event_types)
                    self.assertIn(expected_type, archived_types)

    def test_event_spine_endpoint_tracks_rejected_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)

            run_status, _, run_payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )
            event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=10")

            self.assertEqual(run_status, 200)
            self.assertEqual(run_payload["status"], "fallback")
            self.assertEqual(event_status, 200)
            self.assertEqual(event_payload["aggregate"]["jobs"]["rejected_count"], 1)
            event_types = [item["type"] for item in event_payload["recent_events"]]
            self.assertIn("JOB_SUBMITTED", event_types)
            self.assertIn("JOB_REJECTED", event_types)
            self.assertIn("ARCHIVE_SNAPSHOT_WRITTEN", event_types)

    def test_event_spine_endpoint_tracks_heartbeat_timeout_fault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)
            request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
            )

            with patch(
                "server.run_fault_action",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "last_fault_code": "HEARTBEAT_TIMEOUT",
                    "board_response": {
                        "decision": "ALLOW",
                        "fault_code": "HEARTBEAT_TIMEOUT",
                        "guard_state": "READY",
                    },
                    "logs": ["[02:36:22] heartbeat timeout live success"],
                },
            ):
                fault_status, _, fault_payload = request_json(
                    state,
                    "POST",
                    "/api/inject-fault",
                    body=json.dumps({"fault_type": "heartbeat_timeout"}).encode("utf-8"),
                )
                event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=20")

            self.assertEqual(fault_status, 200)
            self.assertEqual(fault_payload["status"], "injected")
            self.assertEqual(event_status, 200)
            self.assertEqual(event_payload["aggregate"]["heartbeat"]["status"], "lost")
            self.assertFalse(event_payload["aggregate"]["safe_stop"]["active"])
            event_types = [item["type"] for item in event_payload["recent_events"]]
            for expected_type in (
                "JOB_SUBMITTED",
                "JOB_ADMITTED",
                "HEARTBEAT_OK",
                "HEARTBEAT_LOST",
                "SAFE_STOP_TRIGGERED",
                "SAFE_STOP_CLEARED",
                "ARCHIVE_SNAPSHOT_WRITTEN",
            ):
                with self.subTest(expected_type=expected_type):
                    self.assertIn(expected_type, event_types)

    def test_job_manifest_gate_preview_endpoint_tracks_preview_only_allow_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)
            request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
            )

            with (
                patch(
                    "server.describe_demo_admission",
                    return_value={
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Signed manifest v1",
                        "tone": "online",
                        "bundle_path": "/tmp/openamp_demo_signed_admission/current.bundle.json",
                        "public_key_path": "/tmp/openamp_demo_signed_admission/current.public.pem",
                        "manifest_sha256": "a" * 64,
                        "artifact_sha256": "b" * 64,
                        "key_id": "demo-live-20260316",
                        "verified_locally": True,
                        "artifact_match": True,
                        "note": "key_id=demo-live-20260316 | bundle=current.bundle.json",
                    },
                ),
                patch(
                    "server.describe_demo_variant_support",
                    return_value={
                        "variant": "current",
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Current signed live 已支持",
                        "tone": "online",
                        "note": "Current signed-admission live path is supported.",
                        "supported": True,
                        "launch_allowed": True,
                    },
                ),
                patch(
                    "server.query_live_status",
                    return_value={
                        "status": "success",
                        "guard_state": "READY",
                        "active_job_id": 0,
                        "last_fault_code": "NONE",
                        "total_fault_count": 0,
                        "logs": ["[12:00:00] STATUS_RESP: guard=READY / fault=NONE"],
                    },
                ),
            ):
                preview_status, _, preview_payload = request_json(
                    state,
                    "POST",
                    "/api/job-manifest-gate/preview",
                    body=json.dumps({"variant": "current"}).encode("utf-8"),
                )
                event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=10")

        self.assertEqual(preview_status, 200)
        self.assertEqual(preview_payload["status"], "ok")
        self.assertTrue(preview_payload["preview_only"])
        self.assertEqual(preview_payload["gate"]["verdict"], "allow")
        self.assertIn("未发送 JOB_REQ", preview_payload["message"])
        self.assertEqual(event_status, 200)
        self.assertEqual(event_payload["aggregate"]["jobs"]["submitted_count"], 0)
        self.assertEqual(event_payload["aggregate"]["jobs"]["admitted_count"], 0)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_submitted_count"], 1)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_admitted_count"], 1)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_rejected_count"], 0)
        self.assertEqual(event_payload["aggregate"]["heartbeat"]["status"], "unknown")
        event_types = [item["type"] for item in event_payload["recent_events"]]
        self.assertIn("JOB_SUBMITTED", event_types)
        self.assertIn("JOB_ADMITTED", event_types)
        self.assertIn("ARCHIVE_SNAPSHOT_WRITTEN", event_types)
        self.assertNotIn("JOB_STARTED", event_types)
        self.assertNotIn("HEARTBEAT_OK", event_types)

    def test_job_manifest_gate_preview_endpoint_tracks_preview_only_rejection_when_board_busy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)
            request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
            )

            with (
                patch(
                    "server.describe_demo_admission",
                    return_value={
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Signed manifest v1",
                        "tone": "online",
                        "bundle_path": "/tmp/openamp_demo_signed_admission/current.bundle.json",
                        "public_key_path": "/tmp/openamp_demo_signed_admission/current.public.pem",
                        "manifest_sha256": "a" * 64,
                        "artifact_sha256": "b" * 64,
                        "key_id": "demo-live-20260316",
                        "verified_locally": True,
                        "artifact_match": True,
                        "note": "key_id=demo-live-20260316 | bundle=current.bundle.json",
                    },
                ),
                patch(
                    "server.describe_demo_variant_support",
                    return_value={
                        "variant": "current",
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Current signed live 已支持",
                        "tone": "online",
                        "note": "Current signed-admission live path is supported.",
                        "supported": True,
                        "launch_allowed": True,
                    },
                ),
                patch(
                    "server.query_live_status",
                    return_value={
                        "status": "success",
                        "guard_state": "JOB_ACTIVE",
                        "active_job_id": 8093,
                        "last_fault_code": "DUPLICATE_JOB_ID",
                        "total_fault_count": 1,
                        "logs": ["[12:00:00] STATUS_RESP: guard=JOB_ACTIVE"],
                    },
                ),
            ):
                preview_status, _, preview_payload = request_json(
                    state,
                    "POST",
                    "/api/job-manifest-gate/preview",
                    body=json.dumps({"variant": "current"}).encode("utf-8"),
                )
                event_status, _, event_payload = request_json(state, "GET", "/api/event-spine?limit=10")

        self.assertEqual(preview_status, 200)
        self.assertEqual(preview_payload["status"], "ok")
        self.assertEqual(preview_payload["gate"]["verdict"], "deny")
        self.assertIn("guard_state=JOB_ACTIVE", " ".join(preview_payload["gate"]["reasons"]))
        self.assertIn("未放行", preview_payload["message"])
        self.assertEqual(event_status, 200)
        self.assertEqual(event_payload["aggregate"]["jobs"]["submitted_count"], 0)
        self.assertEqual(event_payload["aggregate"]["jobs"]["rejected_count"], 0)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_submitted_count"], 1)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_admitted_count"], 0)
        self.assertEqual(event_payload["aggregate"]["jobs"]["preview_rejected_count"], 1)
        event_types = [item["type"] for item in event_payload["recent_events"]]
        self.assertIn("JOB_SUBMITTED", event_types)
        self.assertIn("JOB_REJECTED", event_types)
        self.assertNotIn("JOB_ADMITTED", event_types)

    def test_system_status_endpoint_preloads_repo_defaults_without_password(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        expected_env_file = state._board_access.env_file.relative_to(REPO_ROOT).as_posix()

        status, headers, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload["execution_mode"]["label"], "待补全密码")
        self.assertTrue(payload["board_access"]["configured"])
        self.assertFalse(payload["board_access"]["has_password"])
        self.assertEqual(payload["board_access"]["host"], "100.121.87.73")
        self.assertEqual(payload["board_access"]["user"], "user")
        self.assertEqual(payload["board_access"]["port"], 22)
        self.assertEqual(payload["board_access"]["env_file"], expected_env_file)
        self.assertEqual(payload["board_access"]["missing_connection_fields"], ["password"])
        self.assertEqual(payload["board_access"]["missing_inference_fields_by_variant"]["current"], ["password"])
        self.assertEqual(payload["board_access"]["missing_inference_fields_by_variant"]["baseline"], ["password"])
        self.assertEqual(payload["board_access"]["field_sources"]["host"], "preloaded")
        self.assertEqual(payload["board_access"]["field_sources"]["password"], "missing")
        self.assertEqual(
            payload["board_access"]["preloaded_defaults"]["ssh_env_file"],
            "session_bootstrap/config/phytium_pi_login.example.env",
        )
        self.assertEqual(
            payload["board_access"]["preloaded_defaults"]["inference_env_file"],
            expected_env_file,
        )
        self.assertNotIn("password", payload["board_access"])
        self.assertEqual(
            payload["live"]["admission"]["artifact_sha256"],
            payload["live"]["trusted_sha"],
        )
        self.assertEqual(payload["live"]["variant_support"]["baseline"]["mode"], "legacy_sha")
        self.assertEqual(payload["live"]["variant_support"]["baseline"]["label"], "PyTorch live 已支持")
        self.assertIn(
            "expected-SHA admission (legacy_sha)",
            payload["live"]["variant_support"]["baseline"]["note"],
        )
        self.assertEqual(payload["live"]["variant_support"]["current"]["mode"], "signed_manifest_v1")
        self.assertIn("signed-admission", payload["live"]["variant_support"]["current"]["note"])
        self.assertTrue(payload["live"]["variant_support"]["baseline"]["launch_allowed"])
        self.assertFalse(payload["active_inference"]["running"])
        self.assertEqual(payload["active_inference"]["queue_depth"], 0)
        self.assertEqual(payload["active_inference"]["progress"]["count_label"], "0 active / 0 queued")
        self.assertEqual(payload["operator_cue"]["mode"], "operator_assist_only")
        self.assertEqual(payload["operator_cue"]["current_scene_id"], "scene1")
        self.assertEqual(payload["operator_cue"]["next_action"]["target_id"], "credentialPanel")
        self.assertIn("Operator-assist only", payload["operator_cue"]["manual_boundary_note"])
        self.assertEqual(payload["operator_cue"]["scenes"][0]["checks"][0]["label"], "会话已录入")
        self.assertFalse(payload["operator_cue"]["scenes"][0]["checks"][0]["ready"])

    def test_system_status_endpoint_exposes_redacted_board_access(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        save_status, _, save_payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "demo-pass",
                    "port": "2202",
                }
            ).encode("utf-8"),
        )
        status, headers, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(save_status, 200)
        self.assertEqual(save_payload["status"], "ok")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertTrue(payload["board_access"]["configured"])
        self.assertEqual(payload["board_access"]["host"], "demo-board")
        self.assertEqual(payload["board_access"]["user"], "demo-user")
        self.assertTrue(payload["board_access"]["has_password"])
        self.assertNotIn("password", payload["board_access"])

    def test_system_status_endpoint_derives_safety_panel_from_live_recover_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._last_live_probe = live_probe_payload("2026-03-19T18:42:00+0800", "board reachable")
        state._last_control_status = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "HEARTBEAT_TIMEOUT",
            "active_job_id": 0,
            "total_fault_count": 3,
        }
        state._last_fault_result = {
            "fault_type": "recover",
            "status": "recovered",
            "status_category": "success",
            "execution_mode": "live",
            "source_label": "真机 SAFE_STOP 收口",
            "message": "板端已回到 READY；last_fault_code 保留最近故障证据。",
            "guard_state": "READY",
            "last_fault_code": "HEARTBEAT_TIMEOUT",
            "status_lamp": "yellow",
            "log_entries": ["[02:36:22] ◀ STATUS_RESP: READY，last_fault=HEARTBEAT_TIMEOUT"],
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertIn("safety_panel", payload)
        self.assertEqual(payload["safety_panel"]["panel_label"], "SAFE_STOP 已执行")
        self.assertEqual(payload["safety_panel"]["safe_stop_state"], "RECOVERED")
        self.assertEqual(payload["safety_panel"]["latch_state"], "LATCHED")
        self.assertEqual(payload["safety_panel"]["guard_state"], "READY")
        self.assertEqual(payload["safety_panel"]["last_fault_code"], "HEARTBEAT_TIMEOUT")
        self.assertEqual(payload["safety_panel"]["total_fault_count"], 3)
        self.assertTrue(payload["safety_panel"]["board_online"])
        self.assertEqual(payload["safety_panel"]["status_source"], "live_control")
        self.assertEqual(payload["safety_panel"]["status_note"], "已缓存最近一次 RPMsg 控制面读数。")
        self.assertEqual(payload["safety_panel"]["last_fault_result"]["execution_mode"], "live")
        self.assertEqual(payload["safety_panel"]["last_fault_result"]["source_label"], "真机 SAFE_STOP 收口")
        self.assertEqual(
            payload["safety_panel"]["last_fault_result"]["log_tail"],
            "[02:36:22] ◀ STATUS_RESP: READY，last_fault=HEARTBEAT_TIMEOUT",
        )
        self.assertEqual(payload["safety_panel"]["recover_action"]["api_path"], "/api/recover")
        self.assertEqual(payload["safety_panel"]["recover_action"]["method"], "POST")
        self.assertIn(
            "RTOS/Bare Metal owns physical SAFE_STOP/GPIO; Linux UI is mirror/control surface only.",
            payload["safety_panel"]["ownership_note"],
        )

    def test_system_status_endpoint_derives_safety_panel_from_live_status_without_last_fault_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._last_live_probe = live_probe_payload("2026-03-19T18:45:00+0800", "board reachable")
        state._last_control_status = {
            "status": "success",
            "guard_state": "JOB_ACTIVE",
            "last_fault_code": "NONE",
            "active_job_id": 8093,
            "total_fault_count": 0,
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["safety_panel"]["panel_label"], "无告警")
        self.assertEqual(payload["safety_panel"]["safe_stop_state"], "STANDBY")
        self.assertEqual(payload["safety_panel"]["latch_state"], "CLEAR")
        self.assertEqual(payload["safety_panel"]["guard_state"], "JOB_ACTIVE")
        self.assertEqual(payload["safety_panel"]["last_fault_code"], "NONE")
        self.assertEqual(payload["safety_panel"]["total_fault_count"], 0)
        self.assertEqual(payload["safety_panel"]["last_fault_result"], {})
        self.assertEqual(payload["safety_panel"]["recover_action"]["label"], "SAFE_STOP 收口")
        self.assertIn("不会自动 SAFE_STOP", payload["safety_panel"]["status_note"])

    def test_system_status_endpoint_advances_operator_cue_to_compare_after_current_live_result(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-03-19T19:10:00+0800", "board reachable")
        state._last_control_status = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "active_job_id": 0,
            "total_fault_count": 0,
        }
        state._last_inference_result = {
            "variant": "current",
            "request_state": "completed",
            "status": "success",
            "execution_mode": "live",
            "source_label": "Current live 数据面",
            "message": "Current live 结果已经回到页面。",
            "job_id": "demo-job-compare",
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["job_manifest_gate"]["verdict"], "allow")
        self.assertEqual(payload["operator_cue"]["current_scene_id"], "scene3")
        self.assertEqual(payload["operator_cue"]["status_label"], "第三幕 / Compare 与性能口径")
        self.assertEqual(payload["operator_cue"]["next_action"]["target_id"], "compareViewerShell")
        self.assertEqual(payload["operator_cue"]["next_action"]["act_id"], "act3")
        self.assertIn("4-core", payload["operator_cue"]["boundary_note"])
        self.assertTrue(payload["operator_cue"]["scenes"][2]["checks"][0]["ready"])
        self.assertTrue(payload["operator_cue"]["scenes"][2]["checks"][1]["ready"])

    def test_system_status_endpoint_includes_backend_aircraft_position_contract(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertIn("aircraft_position", payload)
        self.assertEqual(payload["aircraft_position"]["contract_version"], "aircraft_position.v1")
        self.assertEqual(payload["aircraft_position"]["source_api_path"], "/api/aircraft-position")
        self.assertEqual(payload["aircraft_position"]["source_kind"], "backend_stub")
        self.assertEqual(payload["aircraft_position"]["source_status"], "stub")
        self.assertEqual(payload["aircraft_position"]["source_label"], "Backend stub contract")
        self.assertIn("upper-computer/backend contract", payload["aircraft_position"]["ownership_note"])
        self.assertFalse(payload["aircraft_position"]["feed_contract"]["primary_source"]["active"])
        self.assertTrue(payload["aircraft_position"]["feed_contract"]["fallback_source"]["active"])
        self.assertEqual(payload["aircraft_position"]["sample"]["sequence"], 0)
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["status"], "config_missing")
        self.assertEqual(
            payload["aircraft_position"]["bridge_runtime"]["missing_env"],
            ["AIRCRAFT_POSITION_UPSTREAM_URL", "AIRCRAFT_POSITION_BACKEND_BASE_URL"],
        )
        self.assertEqual(payload["aircraft_position"]["position_api_runtime"]["status"], "waiting_session")
        self.assertEqual(payload["live"]["aircraft_bridge"]["status"], "config_missing")
        self.assertEqual(payload["live"]["board_position_api"]["status"], "waiting_session")

    def test_query_board_position_api_health_parses_remote_health_payload(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        stdout = json.dumps(
            {
                "status": "ok",
                "url": "http://127.0.0.1:9000/health",
                "http_status": 200,
                "payload": {
                    "status": "starting",
                    "source_order": ["gpsd", "nmea"],
                    "last_error": "gpsd:[Errno 111] Connection refused",
                    "sample": None,
                },
                "body": "{}",
                "error": "",
            },
            ensure_ascii=False,
        )

        with patch(
            "server.run_ssh_command",
            return_value=server.subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
        ):
            payload = server.query_board_position_api_health(
                board_access,
                runtime_env={"BOARD_POSITION_API_BIND_HOST": "127.0.0.1", "BOARD_POSITION_API_PORT": "9000"},
                timeout_sec=3.0,
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["http_status"], 200)
        self.assertEqual(payload["payload"]["status"], "starting")

    def test_remote_http_json_probe_command_avoids_nested_single_quote_splicing(self) -> None:
        command = server._remote_http_json_probe_command("http://127.0.0.1:9000/health", timeout_sec=4.0)

        self.assertIn('base64.b64decode("', command)
        self.assertIn('.decode("utf-8")', command)
        self.assertNotIn("'\"'\"'", command)

    def test_board_position_api_status_promotes_live_sample_from_position_endpoint(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        ).with_env_overrides(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
            }
        )

        with (
            patch(
                "server.query_board_position_api_health",
                return_value={
                    "status": "ok",
                    "http_status": 200,
                    "payload": {
                        "status": "starting",
                        "source_order": ["http", "gpsd", "nmea"],
                        "last_error": "",
                        "sample": None,
                    },
                },
            ),
            patch(
                "server.query_board_position_api_sample",
                return_value={
                    "status": "ok",
                    "http_status": 200,
                    "payload": {
                        "status": "live",
                        "source": "http:https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                        "source_kind": "http",
                        "latitude": 22.943853,
                        "longitude": 113.390465,
                        "captured_at": "2026-04-11T20:24:08+0800",
                        "sequence": 1,
                    },
                },
            ),
        ):
            payload = server._board_position_api_status(board_access, timeout_sec=3.0)

        self.assertEqual(payload["status"], "live")
        self.assertTrue(payload["sample_ready"])
        self.assertEqual(payload["sample"]["source_kind"], "http")
        self.assertAlmostEqual(payload["sample"]["latitude"], 22.943853)

    def test_system_status_reports_board_position_api_source_unavailable_from_health_probe(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )

        with (
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "not_found",
                    "selected_url": "",
                    "selected_source": "",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [],
                },
            ),
            patch.object(
                state,
                "_board_position_api_snapshot",
                return_value={
                    "status": "source_unavailable",
                    "note": "板端定位 API 服务已启动，但当前没有拿到有效位置样本。",
                    "service_reachable": True,
                    "http_status": 200,
                    "health_url": "http://127.0.0.1:9000/health",
                    "remote_root": server.DEFAULT_BOARD_POSITION_API_REMOTE_ROOT,
                    "sample_ready": False,
                    "service_state": "starting",
                    "last_error": "gpsd:[Errno 111] Connection refused; nmea:/dev/ttyS1: [Errno 13] Permission denied",
                    "source_order": ["gpsd", "nmea"],
                    "sample": None,
                },
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["aircraft_position"]["position_api_runtime"]["status"], "source_unavailable")
        self.assertEqual(payload["live"]["board_position_api"]["status"], "source_unavailable")
        self.assertTrue(payload["live"]["board_position_api"]["service_reachable"])

    def test_query_board_telemetry_parses_cpu_and_memory_usage(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        board_access = server.build_board_access_config(
            {"host": "demo-board", "user": "demo-user", "password": "demo-pass", "port": "22"},
            fallback=state._board_access,
        )
        stdout = "\n".join(
            [
                "MemTotal:        2048000 kB",
                "MemFree:          128000 kB",
                "MemAvailable:     512000 kB",
                "Buffers:           64000 kB",
                "Cached:           256000 kB",
                "__BOARD_MEMINFO_END__",
                "cpu  100 0 50 850 0 0 0 0 0 0",
                "__BOARD_STAT1_END__",
                "cpu  130 0 60 870 0 0 0 0 0 0",
                "__BOARD_STAT2_END__",
                "1.25 0.50 0.25 1/100 1234",
                "__BOARD_LOADAVG_END__",
                "4",
            ]
        )

        with patch(
            "server.run_ssh_command",
            return_value=server.subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
        ):
            telemetry = server.query_board_telemetry(board_access, timeout_sec=3.0)

        self.assertEqual(telemetry["status"], "ok")
        self.assertEqual(telemetry["compute_label"], "CPU")
        self.assertAlmostEqual(telemetry["compute_pct"], 66.667, places=3)
        self.assertAlmostEqual(telemetry["memory_pct"], 75.0, places=3)
        self.assertAlmostEqual(telemetry["memory_used_mb"], 1500.0, places=1)
        self.assertAlmostEqual(telemetry["memory_total_mb"], 2000.0, places=1)
        self.assertEqual(telemetry["cpu_cores"], 4)

    def test_board_telemetry_remote_command_uses_stable_cpu_sample_window(self) -> None:
        with patch.dict(os.environ, {"BOARD_TELEMETRY_CPU_SAMPLE_SEC": ""}, clear=False):
            command = server._board_telemetry_remote_command()

        self.assertIn("sleep 1.000", command)
        self.assertNotIn("sleep 0.1", command)
        self.assertIn("echo __BOARD_MEMINFO_END__", command)
        self.assertIn("echo __BOARD_STAT1_END__", command)
        self.assertIn("echo __BOARD_STAT2_END__", command)
        self.assertIn("echo __BOARD_LOADAVG_END__", command)
        self.assertNotIn('printf "__BOARD_', command)

    def test_board_telemetry_remote_command_allows_cpu_sample_window_override(self) -> None:
        with patch.dict(os.environ, {"BOARD_TELEMETRY_CPU_SAMPLE_SEC": "0.5"}, clear=False):
            command = server._board_telemetry_remote_command()

        self.assertIn("sleep 0.500", command)

    def test_system_status_endpoint_exposes_board_telemetry(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-04-11T03:33:00+0800", "board reachable")
        state._board_telemetry_cache = {
            "status": "ok",
            "stale": False,
            "source": "ssh_procfs",
            "collected_at": "2026-04-11T03:33:05+0800",
            "compute_label": "CPU",
            "compute_pct": 48.5,
            "memory_pct": 61.2,
            "memory_used_mb": 1254.0,
            "memory_available_mb": 796.0,
            "memory_total_mb": 2050.0,
            "loadavg_1m": 1.42,
            "cpu_cores": 4,
        }
        state._board_telemetry_cache_ts = time.monotonic()

        with patch.object(
            state,
            "_aircraft_position_upstream_probe_snapshot",
            return_value={
                "status": "not_found",
                "selected_url": "",
                "selected_source": "",
                "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                "results": [],
            },
        ), patch.object(
            state,
            "_start_board_telemetry_refresh",
            side_effect=AssertionError("fresh telemetry cache should not refresh"),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["live"]["telemetry"]["status"], "ok")
        self.assertEqual(payload["live"]["telemetry"]["compute_label"], "CPU")
        self.assertAlmostEqual(payload["live"]["telemetry"]["compute_pct"], 48.5)
        self.assertAlmostEqual(payload["live"]["telemetry"]["memory_pct"], 61.2)
        self.assertAlmostEqual(payload["live"]["telemetry"]["memory_used_mb"], 1254.0)

    def test_system_status_reuses_cached_board_telemetry_while_refreshing(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-04-11T03:33:00+0800", "board reachable")
        state._board_telemetry_cache = {
            "status": "ok",
            "stale": False,
            "source": "ssh_procfs",
            "collected_at": "2026-04-11T03:33:05+0800",
            "compute_label": "CPU",
            "compute_pct": 48.5,
            "memory_pct": 61.2,
            "memory_used_mb": 1254.0,
            "memory_available_mb": 796.0,
            "memory_total_mb": 2050.0,
            "loadavg_1m": 1.42,
            "cpu_cores": 4,
        }
        state._board_telemetry_cache_ts = time.monotonic() - (server.BOARD_TELEMETRY_TTL_SEC + 1.0)

        with (
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "not_found",
                    "selected_url": "",
                    "selected_source": "",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [],
                },
            ),
            patch.object(
                state,
                "_board_position_api_snapshot",
                return_value={
                    "status": "source_unavailable",
                    "note": "板端定位 API 服务已启动，但当前没有拿到有效位置样本。",
                },
            ),
            patch.object(state, "_usrp_control_status_snapshot", return_value={"status": "waiting_session"}),
            patch.object(state, "_start_board_telemetry_refresh") as start_telemetry_refresh,
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["live"]["telemetry"]["status"], "ok")
        self.assertFalse(payload["live"]["telemetry"]["stale"])
        self.assertTrue(payload["live"]["telemetry"]["refreshing"])
        self.assertAlmostEqual(payload["live"]["telemetry"]["memory_pct"], 61.2)
        self.assertIn("后台刷新中", payload["live"]["telemetry"]["note"])
        self.assertGreater(payload["live"]["telemetry"]["age_sec"], server.BOARD_TELEMETRY_TTL_SEC)
        start_telemetry_refresh.assert_called_once()

    def test_board_telemetry_snapshot_returns_refreshing_without_sync_on_cold_online_board(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )

        with (
            patch.object(state, "_start_board_telemetry_refresh") as start_refresh,
            patch(
                "server.query_board_telemetry",
                side_effect=AssertionError("system-status must not synchronously probe board telemetry"),
            ),
        ):
            payload = state._board_telemetry_snapshot(
                board_access=state._board_access,
                board_online=True,
            )

        self.assertEqual(payload["status"], "refreshing")
        self.assertTrue(payload["stale"])
        self.assertIn("后台刷新", payload["note"])
        start_refresh.assert_called_once()
        self.assertGreaterEqual(start_refresh.call_args.kwargs["timeout_sec"], 6.0)

    def test_board_position_api_snapshot_reuses_cached_payload_while_refreshing(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )
        state._board_position_api_cache = {
            "status": "source_unavailable",
            "note": "板端定位 API 服务已启动，但当前没有拿到有效位置样本。",
            "service_reachable": True,
            "http_status": 200,
            "sample_ready": False,
        }
        state._board_position_api_cache_ts = time.monotonic() - (server.BOARD_POSITION_API_TTL_SEC + 1.0)

        fake_thread = Mock()
        fake_thread.start = Mock()

        with patch("server.threading.Thread", return_value=fake_thread) as thread_cls:
            payload = state._board_position_api_snapshot(state._board_access)

        self.assertEqual(payload["status"], "source_unavailable")
        self.assertTrue(payload["stale"])
        self.assertIn("后台刷新中", payload["note"])
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()

    def test_aircraft_position_upstream_snapshot_returns_refreshing_without_sync_on_cold_session(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )

        with (
            patch.object(state, "_start_aircraft_position_upstream_probe_refresh", create=True) as start_refresh,
            patch(
                "server.query_board_aircraft_position_upstream",
                side_effect=AssertionError("system-status must not synchronously probe aircraft upstream"),
            ),
        ):
            payload = state._aircraft_position_upstream_probe_snapshot(board_access=state._board_access)

        self.assertEqual(payload["status"], "refreshing")
        self.assertTrue(payload["stale"])
        self.assertIn("后台探测", payload["note"])
        start_refresh.assert_called_once()

    def test_system_status_refreshes_board_telemetry_for_idle_usrp_session(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "100.121.87.73",
                    "user": "demo-user",
                    "password": "demo-pass",
                    "port": "22",
                    "transport_mode": "usrp",
                }
            ).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-04-21T15:43:00+0800", "board reachable")

        with (
            patch.object(state, "_start_aircraft_position_upstream_probe_refresh") as start_upstream_refresh,
            patch.object(state, "_start_board_telemetry_refresh") as start_telemetry_refresh,
            patch.object(state, "_start_board_position_api_refresh") as start_position_refresh,
            patch.object(state, "_start_usrp_control_status_refresh", create=True) as start_usrp_refresh,
            patch(
                "server.query_board_aircraft_position_upstream",
                side_effect=AssertionError("USRP system-status must not probe aircraft upstream"),
            ),
            patch(
                "server.query_board_telemetry",
                side_effect=AssertionError("USRP system-status must not probe board telemetry"),
            ),
            patch(
                "server._board_position_api_status",
                side_effect=AssertionError("USRP system-status must not probe board position API"),
            ),
            patch(
                "server.inspect_usrp_control_servers",
                side_effect=AssertionError("USRP system-status must not probe USRP control sockets"),
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["live"]["telemetry"]["status"], "refreshing")
        self.assertIn("后台刷新", payload["live"]["telemetry"]["note"])
        self.assertEqual(payload["live"]["aircraft_bridge"]["upstream_probe"]["status"], "deferred")
        self.assertEqual(payload["live"]["board_position_api"]["status"], "deferred")
        self.assertTrue(payload["live"]["board_position_api"]["stale"])
        self.assertIn("暂缓", payload["live"]["board_position_api"]["note"])
        self.assertEqual(payload["live"]["usrp_control"]["status"], "deferred")
        self.assertTrue(payload["live"]["usrp_control"]["stale"])
        self.assertIn("暂缓", payload["live"]["usrp_control"]["message"])
        start_upstream_refresh.assert_not_called()
        start_telemetry_refresh.assert_called_once()
        start_position_refresh.assert_not_called()
        start_usrp_refresh.assert_not_called()

    def test_system_status_skips_remote_refreshes_while_tvm_batch_is_running(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-04-21T15:43:00+0800", "board reachable")
        state._batch_state = {
            "status": "running",
            "batch_job_id": "batch-123",
            "engine": "tvm",
            "total": 300,
            "completed": 128,
            "service_mode": "FULL_FRAME",
            "_samples": {},
            "benchmark": None,
        }
        state._board_telemetry_cache = {
            "status": "ok",
            "stale": False,
            "source": "ssh_procfs",
            "collected_at": "2026-04-21T15:42:55+0800",
            "compute_label": "CPU",
            "compute_pct": 43.2,
            "memory_pct": 58.1,
            "memory_used_mb": 1204.0,
            "memory_available_mb": 846.0,
            "memory_total_mb": 2050.0,
            "loadavg_1m": 1.42,
            "cpu_cores": 4,
        }
        state._board_telemetry_cache_ts = time.monotonic() - (server.BOARD_TELEMETRY_TTL_SEC + 1.0)
        state._board_position_api_cache = {
            "status": "source_unavailable",
            "note": "板端定位 API 服务已启动，但当前没有拿到有效位置样本。",
            "service_reachable": True,
            "http_status": 200,
            "sample_ready": False,
        }
        state._board_position_api_cache_ts = time.monotonic() - (server.BOARD_POSITION_API_TTL_SEC + 1.0)
        state._aircraft_position_upstream_probe_cache = {
            "status": "not_found",
            "selected_url": "",
            "selected_source": "",
            "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
            "results": [],
            "checked_at": "2026-04-21T15:42:50+0800",
        }
        state._aircraft_position_upstream_probe_cache_ts = (
            time.monotonic() - (server.AIRCRAFT_POSITION_UPSTREAM_DISCOVERY_TTL_SEC + 1.0)
        )

        with (
            patch("server.query_board_telemetry") as query_telemetry,
            patch.object(state, "_start_board_telemetry_refresh") as start_telemetry_refresh,
            patch("server._board_position_api_status") as board_position_status,
            patch.object(state, "_start_board_position_api_refresh") as start_position_refresh,
            patch.object(state, "_start_aircraft_position_upstream_probe_refresh") as start_upstream_refresh,
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["live"]["telemetry"]["status"], "stale")
        self.assertIn("常驻采样器", payload["live"]["telemetry"]["note"])
        self.assertTrue(payload["live"]["board_position_api"]["stale"])
        self.assertIn("暂缓", payload["live"]["board_position_api"]["note"])
        self.assertEqual(payload["live"]["aircraft_bridge"]["upstream_probe"]["status"], "not_found")
        self.assertIn("暂缓", payload["live"]["aircraft_bridge"]["upstream_probe"]["note"])
        query_telemetry.assert_not_called()
        start_telemetry_refresh.assert_called_once()
        board_position_status.assert_not_called()
        start_position_refresh.assert_not_called()
        start_upstream_refresh.assert_not_called()

    def test_system_status_uses_resident_board_telemetry_cache_during_running_batch(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-04-21T15:43:00+0800", "board reachable")
        state._batch_state = {
            "status": "running",
            "batch_job_id": "batch-123",
            "engine": "tvm",
            "total": 300,
            "completed": 128,
            "service_mode": "FULL_FRAME",
            "_samples": {},
            "benchmark": None,
        }
        state._board_telemetry_cache = {
            "status": "ok",
            "stale": False,
            "source": "ssh_procfs_resident",
            "collected_at": "2026-04-21T15:43:03+0800",
            "compute_label": "CPU",
            "compute_pct": 57.4,
            "memory_pct": 66.2,
            "memory_used_mb": 1357.0,
            "memory_available_mb": 693.0,
            "memory_total_mb": 2050.0,
            "loadavg_1m": 1.87,
            "cpu_cores": 4,
        }
        state._board_telemetry_cache_ts = time.monotonic()

        with (
            patch.object(state, "_start_board_telemetry_refresh") as start_telemetry_refresh,
            patch("server.query_board_telemetry") as query_telemetry,
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        telemetry = payload["live"]["telemetry"]
        self.assertEqual(telemetry["status"], "ok")
        self.assertFalse(telemetry["stale"])
        self.assertNotIn("暂缓", str(telemetry.get("note") or ""))
        self.assertAlmostEqual(telemetry["compute_pct"], 57.4)
        self.assertAlmostEqual(telemetry["memory_pct"], 66.2)
        self.assertAlmostEqual(telemetry["loadavg_1m"], 1.87)
        query_telemetry.assert_not_called()
        start_telemetry_refresh.assert_not_called()

    def test_system_status_reports_upstream_not_found_when_probe_finds_no_candidate(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )

        with (
            patch(
                "server._default_backend_base_url_for_board",
                return_value="http://100.116.93.120:8079",
            ),
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "not_found",
                    "selected_url": "",
                    "selected_source": "",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [{"url": "http://127.0.0.1:9000/gps", "error": "url_error:connection refused"}],
                },
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["status"], "upstream_not_found")
        self.assertFalse(payload["aircraft_position"]["bridge_runtime"]["configured"])
        self.assertEqual(payload["live"]["aircraft_bridge"]["status"], "upstream_not_found")

    def test_system_status_reports_autodiscovered_upstream_when_probe_finds_candidate(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None, bind_host="0.0.0.0", bind_port=8079)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {"host": "100.121.87.73", "user": "demo-user", "password": "demo-pass", "port": "22"}
            ).encode("utf-8"),
        )

        with (
            patch(
                "server._default_backend_base_url_for_board",
                return_value="http://100.116.93.120:8079",
            ),
            patch.object(
                state,
                "_aircraft_position_upstream_probe_snapshot",
                return_value={
                    "status": "detected",
                    "selected_url": "http://127.0.0.1:9527/api/v1/position",
                    "selected_source": "auto_discovered",
                    "candidate_urls": list(server.DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES),
                    "results": [{"url": "http://127.0.0.1:9527/api/v1/position", "has_coordinates": True}],
                },
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["status"], "autodiscovered")
        self.assertTrue(payload["aircraft_position"]["bridge_runtime"]["configured"])
        self.assertEqual(
            payload["aircraft_position"]["bridge_runtime"]["upstream_url"],
            "http://127.0.0.1:9527/api/v1/position",
        )
        self.assertEqual(
            payload["aircraft_position"]["bridge_runtime"]["upstream_url_source"],
            "auto_discovered",
        )
        self.assertEqual(payload["live"]["aircraft_bridge"]["status"], "autodiscovered")

    def test_aircraft_position_endpoint_updates_backend_feed(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/aircraft-position",
            body=json.dumps(
                {
                    "source_kind": "upper_computer_gps",
                    "source_status": "live",
                    "source_label": "Upper Computer GPS live feed",
                    "position": {"latitude": 31.205, "longitude": 121.551},
                    "kinematics": {"heading_deg": 145.0, "ground_speed_kph": 275.5, "altitude_m": 3201.2},
                    "fix": {"type": "RTK", "confidence_m": 2.1, "satellites": 19},
                    "sample": {
                        "captured_at": "2026-03-20T09:41:00+0800",
                        "sequence": 12,
                        "transport": "backend_http_post",
                        "producer_id": "upper-computer-gps-daemon",
                    },
                }
            ).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["source_kind"], "upper_computer_gps")
        self.assertEqual(payload["source_status"], "live")
        self.assertAlmostEqual(payload["position"]["latitude"], 31.205)
        self.assertAlmostEqual(payload["position"]["longitude"], 121.551)
        self.assertEqual(payload["fix"]["type"], "RTK")
        self.assertEqual(payload["sample"]["sequence"], 12)
        self.assertEqual(payload["sample"]["captured_at"], "2026-03-20T09:41:00+0800")
        self.assertTrue(payload["feed_contract"]["primary_source"]["active"])
        self.assertFalse(payload["feed_contract"]["fallback_source"]["active"])

        status, _, latest = request_json(state, "GET", "/api/aircraft-position")

        self.assertEqual(status, 200)
        self.assertEqual(latest["source_status"], "live")
        self.assertAlmostEqual(latest["kinematics"]["ground_speed_kph"], 275.5)
        self.assertAlmostEqual(latest["kinematics"]["altitude_m"], 3201.2)
        self.assertEqual(latest["sample"]["sequence"], 12)
        self.assertEqual(latest["feed_contract"]["active_source_label"], "Upper Computer GPS")

    def test_system_status_marks_aircraft_bridge_live_when_live_feed_is_active(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "http://127.0.0.1:9000/gps",
                "AIRCRAFT_POSITION_BACKEND_BASE_URL": "http://demo-host:8079",
            }
        )
        request_json(
            state,
            "POST",
            "/api/aircraft-position",
            body=json.dumps(
                {
                    "source_kind": "upper_computer_gps",
                    "source_status": "live",
                    "position": {"latitude": 31.205, "longitude": 121.551},
                }
            ).encode("utf-8"),
        )

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["status"], "live")
        self.assertTrue(payload["aircraft_position"]["bridge_runtime"]["configured"])
        self.assertTrue(payload["aircraft_position"]["bridge_runtime"]["live_feed_active"])
        self.assertEqual(payload["live"]["aircraft_bridge"]["status"], "live")

    def test_system_status_marks_external_aircraft_bridge_as_local(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides(
            {
                "AIRCRAFT_POSITION_EXECUTION_MODE": "local",
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
                "AIRCRAFT_POSITION_SOURCE_LABEL": "百度IP定位",
            }
        )
        with patch.object(
            state,
            "_aircraft_position_upstream_probe_snapshot",
            return_value={
                "status": "configured",
                "selected_url": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "selected_source": "env",
                "candidate_urls": [],
                "results": [],
            },
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["status"], "armed_local")
        self.assertEqual(payload["aircraft_position"]["bridge_runtime"]["execution_mode"], "local")
        self.assertEqual(payload["live"]["aircraft_bridge"]["status"], "armed_local")

    def test_run_local_aircraft_position_bridge_once_updates_backend_feed(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides(
            {
                "AIRCRAFT_POSITION_EXECUTION_MODE": "local",
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
                "AIRCRAFT_POSITION_SOURCE_LABEL": "百度IP定位",
                "AIRCRAFT_POSITION_INTERVAL_SEC": "1.0",
            }
        )

        with patch(
            "server.fetch_normalized_payload",
            return_value={
                "source_kind": "upper_computer_gps",
                "source_status": "live",
                "source_label": "百度IP定位",
                "position": {"latitude": 22.943853, "longitude": 113.390465},
                "sample": {"captured_at": "2026-04-11T12:00:00+08:00", "upstream_url": "https://api.map.baidu.com/location/ip"},
            },
        ):
            result = state._run_local_aircraft_position_bridge_once()

        self.assertTrue(result)
        latest = state.current_aircraft_position()
        self.assertEqual(latest["source_status"], "live")
        self.assertAlmostEqual(latest["position"]["latitude"], 22.943853)
        self.assertAlmostEqual(latest["position"]["longitude"], 113.390465)
        self.assertEqual(state._local_aircraft_bridge_state["status"], "running")

    def test_aircraft_position_endpoint_auto_sequences_live_samples_when_feed_metadata_is_implicit(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        first_status, _, first_payload = request_json(
            state,
            "POST",
            "/api/aircraft-position",
            body=json.dumps({"position": {"latitude": 31.2, "longitude": 121.5}}).encode("utf-8"),
        )
        second_status, _, second_payload = request_json(
            state,
            "POST",
            "/api/aircraft-position",
            body=json.dumps({"position": {"latitude": 31.21, "longitude": 121.51}}).encode("utf-8"),
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_payload["source_kind"], "upper_computer_gps")
        self.assertEqual(first_payload["source_status"], "live")
        self.assertEqual(first_payload["sample"]["sequence"], 1)
        self.assertEqual(second_payload["sample"]["sequence"], 2)
        self.assertTrue(second_payload["sample"]["captured_at"])
        self.assertIn("Upper Computer GPS", second_payload["feed_contract"]["active_source_label"])

    def test_system_status_endpoint_prioritizes_operator_cue_scene4_when_fault_is_latched(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        state._last_live_probe = live_probe_payload("2026-03-19T19:15:00+0800", "board reachable")
        state._last_control_status = {
            "status": "success",
            "guard_state": "READY",
            "last_fault_code": "HEARTBEAT_TIMEOUT",
            "active_job_id": 0,
            "total_fault_count": 1,
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["operator_cue"]["current_scene_id"], "scene4")
        self.assertEqual(payload["operator_cue"]["next_action"]["target_id"], "act4Panel")
        self.assertEqual(payload["operator_cue"]["next_action"]["act_id"], "act4")
        self.assertIn("SAFE_STOP", payload["operator_cue"]["presenter_line"])
        self.assertEqual(payload["operator_cue"]["scenes"][3]["checks"][1]["label"], "Blackbox timeline")

    def test_system_status_endpoint_exposes_recent_results_for_refresh_hydration(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        baseline_payload = server.build_prerecorded_inference_result(0, "baseline")
        baseline_payload["job_id"] = "baseline-archive-001"
        current_payload = server.build_prerecorded_inference_result(0, "current")
        current_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "status_category": "success",
                "source_label": "真实在线推进 + 归档样例图",
                "message": "Current live 结果已经回到页面。",
                "job_id": "demo-job-live-001",
                "request_state": "completed",
                "live_progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
            }
        )

        state._update_last_inference_summary(baseline_payload, "baseline")
        state._update_last_inference_summary(current_payload, "current")

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["last_inference"]["variant"], "current")
        self.assertEqual(payload["recent_results"]["current"]["job_id"], "demo-job-live-001")
        self.assertEqual(payload["recent_results"]["current"]["execution_mode"], "live")
        self.assertEqual(payload["recent_results"]["current"]["sample"]["label"], current_payload["sample"]["label"])
        self.assertTrue(payload["recent_results"]["current"]["reconstructed_image_b64"].startswith("data:image/png;base64,"))
        self.assertEqual(payload["recent_results"]["baseline"]["job_id"], "baseline-archive-001")
        self.assertEqual(payload["recent_results"]["baseline"]["execution_mode"], "reference")

    def test_system_status_endpoint_keeps_engine_specific_recent_results(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        baseline_payload = server.build_prerecorded_inference_result(0, "baseline")
        baseline_payload["job_id"] = "baseline-usrp-001"
        tvm_payload = server.build_prerecorded_inference_result(0, "current")
        tvm_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "variant": "current",
                "job_id": "usrp-tvm-001",
                "wrapper_summary": {"inference_engine": "tvm"},
            }
        )
        mnn_payload = server.build_prerecorded_inference_result(0, "current")
        mnn_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "variant": "current",
                "job_id": "usrp-mnn-001",
                "wrapper_summary": {"inference_engine": "mnn"},
            }
        )

        state._update_last_inference_summary(tvm_payload, "current")
        state._update_last_inference_summary(mnn_payload, "current")
        state._update_last_inference_summary(baseline_payload, "baseline")

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["recent_results"]["current"]["job_id"], "usrp-mnn-001")
        self.assertEqual(payload["recent_results"]["baseline"]["job_id"], "baseline-usrp-001")
        self.assertEqual(payload["recent_results"]["tvm"]["job_id"], "usrp-tvm-001")
        self.assertEqual(payload["recent_results"]["mnn"]["job_id"], "usrp-mnn-001")
        self.assertEqual(payload["recent_results"]["pytorch"]["job_id"], "baseline-usrp-001")

    def test_system_status_endpoint_harvests_completed_baseline_job_for_refresh_hydration(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        baseline_payload = server.build_prerecorded_inference_result(0, "baseline")
        baseline_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "status_category": "success",
                "variant": "baseline",
                "job_id": "baseline-live-001",
                "message": "PyTorch baseline completed.",
            }
        )
        running_job = FakeInferenceJob([baseline_payload], job_id="baseline-live-001")
        state._inference_jobs[running_job.job_id] = {
            "job": running_job,
            "job_id": running_job.job_id,
            "variant": "baseline",
            "image_index": 0,
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertFalse(payload["active_inference"]["running"])
        self.assertEqual(payload["recent_results"]["baseline"]["job_id"], "baseline-live-001")
        self.assertEqual(payload["recent_results"]["pytorch"]["job_id"], "baseline-live-001")
        self.assertEqual(payload["last_inference"]["variant"], "baseline")

    def test_completed_job_harvest_does_not_overwrite_newer_last_inference(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        baseline_payload = server.build_prerecorded_inference_result(0, "baseline")
        baseline_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "status_category": "success",
                "variant": "baseline",
                "job_id": "baseline-live-001",
            }
        )
        baseline_job = FakeInferenceJob([baseline_payload], job_id="baseline-live-001")
        state._inference_jobs[baseline_job.job_id] = {
            "job": baseline_job,
            "job_id": baseline_job.job_id,
            "variant": "baseline",
            "image_index": 0,
        }
        request_json(state, "GET", "/api/system-status")
        current_payload = server.build_prerecorded_inference_result(0, "current")
        current_payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "status_category": "success",
                "variant": "current",
                "job_id": "mnn-current-001",
                "wrapper_summary": {"inference_engine": "mnn"},
            }
        )
        state._update_last_inference_summary(current_payload, "current")

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["last_inference"]["variant"], "current")
        self.assertEqual(payload["recent_results"]["mnn"]["job_id"], "mnn-current-001")

    def test_operator_readiness_smoke_state_covers_required_page_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = DashboardState(None, 30.0, probe_cache_path=None, event_archive_root=temp_dir)
            request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
            )
            state._last_live_probe = live_probe_payload("2026-03-19T19:22:00+0800", "board reachable")
            state._last_control_status = {
                "status": "success",
                "guard_state": "READY",
                "last_fault_code": "NONE",
                "active_job_id": 0,
                "total_fault_count": 0,
                "logs": ["[19:22:00] STATUS_RESP: READY / fault=NONE"],
            }

            with (
                patch(
                    "server.describe_demo_admission",
                    return_value={
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Signed manifest v1",
                        "tone": "online",
                        "bundle_path": "/tmp/openamp_demo_signed_admission/current.bundle.json",
                        "public_key_path": "/tmp/openamp_demo_signed_admission/current.public.pem",
                        "manifest_sha256": "a" * 64,
                        "artifact_sha256": "b" * 64,
                        "key_id": "demo-live-20260316",
                        "verified_locally": True,
                        "artifact_match": True,
                        "note": "key_id=demo-live-20260316 | bundle=current.bundle.json",
                    },
                ),
                patch(
                    "server.describe_demo_variant_support",
                    side_effect=[
                        {
                            "variant": "current",
                            "status": "ready",
                            "mode": "signed_manifest_v1",
                            "label": "Current signed live 已支持",
                            "tone": "online",
                            "note": "Current signed-admission live path is supported.",
                            "supported": True,
                            "launch_allowed": True,
                        },
                        {
                            "variant": "baseline",
                            "status": "ready",
                            "mode": "legacy_sha",
                            "label": "PyTorch live 已支持",
                            "tone": "online",
                            "note": "PyTorch live path currently uses expected-SHA admission (legacy_sha).",
                            "supported": True,
                            "launch_allowed": True,
                        },
                        {
                            "variant": "current",
                            "status": "ready",
                            "mode": "signed_manifest_v1",
                            "label": "Current signed live 已支持",
                            "tone": "online",
                            "note": "Current signed-admission live path is supported.",
                            "supported": True,
                            "launch_allowed": True,
                        },
                        {
                            "variant": "baseline",
                            "status": "ready",
                            "mode": "legacy_sha",
                            "label": "PyTorch live 已支持",
                            "tone": "online",
                            "note": "PyTorch live path currently uses expected-SHA admission (legacy_sha).",
                            "supported": True,
                            "launch_allowed": True,
                        },
                    ],
                ),
                patch(
                    "server.query_live_status",
                    return_value={
                        "status": "success",
                        "guard_state": "READY",
                        "active_job_id": 0,
                        "last_fault_code": "NONE",
                        "total_fault_count": 0,
                        "logs": ["[19:22:01] STATUS_RESP: READY / fault=NONE"],
                    },
                ),
            ):
                preview_status, _, preview_payload = request_json(
                    state,
                    "POST",
                    "/api/job-manifest-gate/preview",
                    body=json.dumps({"variant": "current"}).encode("utf-8"),
                )
                link_status, _, link_payload = request_json(
                    state,
                    "POST",
                    "/api/link-director/profile",
                    body=json.dumps({"profile_id": "lossy"}).encode("utf-8"),
                )

                baseline_payload = server.build_prerecorded_inference_result(0, "baseline")
                baseline_payload["job_id"] = "baseline-archive-300"
                current_payload = server.build_prerecorded_inference_result(0, "current")
                current_payload.update(
                    {
                        "status": "success",
                        "execution_mode": "live",
                        "status_category": "success",
                        "source_label": "真实在线推进 + 归档样例图",
                        "message": "Current live 结果已经回到页面。",
                        "job_id": "demo-job-compare-300",
                        "request_state": "completed",
                        "live_progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
                    }
                )
                state._update_last_inference_summary(baseline_payload, "baseline")
                state._update_last_inference_summary(current_payload, "current")

                status, _, payload = request_json(state, "GET", "/api/system-status")
                archive_list_status, _, archive_list_payload = request_json(state, "GET", "/api/archive/sessions?limit=10")
                current_session_id = archive_list_payload["current_session_id"] or archive_list_payload["sessions"][0]["session_id"]
                archive_status, _, archive_payload = request_json(
                    state,
                    "GET",
                    f"/api/archive/session?session_id={current_session_id}&limit=10",
                )

        self.assertEqual(preview_status, 200)
        self.assertEqual(preview_payload["gate"]["verdict"], "allow")
        self.assertEqual(link_status, 200)
        self.assertEqual(link_payload["selected_profile_id"], "lossy")
        self.assertEqual(status, 200)
        self.assertEqual(payload["operator_cue"]["current_scene_id"], "scene3")
        self.assertEqual(payload["operator_cue"]["next_action"]["target_id"], "compareViewerShell")
        self.assertEqual(payload["link_director"]["selected_profile_id"], "lossy")
        self.assertEqual(payload["job_manifest_gate"]["verdict"], "allow")
        self.assertEqual(payload["recent_results"]["current"]["execution_mode"], "live")
        self.assertEqual(payload["recent_results"]["baseline"]["execution_mode"], "reference")
        self.assertEqual(payload["safety_panel"]["panel_label"], "无告警")
        self.assertEqual(payload["safety_panel"]["safe_stop_state"], "IDLE")
        self.assertGreaterEqual(payload["event_spine"]["event_count"], 4)
        self.assertEqual(archive_list_status, 200)
        self.assertGreaterEqual(archive_list_payload["session_count"], 1)
        self.assertTrue(current_session_id)
        self.assertEqual(archive_status, 200)
        self.assertEqual(archive_payload["summary"]["session_id"], current_session_id)
        self.assertGreaterEqual(archive_payload["summary"]["event_count"], 1)
        self.assertTrue(archive_payload["timeline"])
        self.assertTrue(
            {"JOB_SUBMITTED", "JOB_ADMITTED", "LINK_PROFILE_CHANGED", "ARCHIVE_SNAPSHOT_WRITTEN"}
            & {item["title"] for item in archive_payload["timeline"]}
        )

    def test_system_status_endpoint_includes_demo_admission_summary(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with (
            patch(
                "server.describe_demo_admission",
                return_value={
                    "status": "ready",
                    "mode": "signed_manifest_v1",
                    "label": "Signed manifest v1",
                    "tone": "online",
                    "bundle_path": "/tmp/openamp_demo_signed_admission/current.bundle.json",
                    "public_key_path": "/tmp/openamp_demo_signed_admission/current.public.pem",
                    "manifest_sha256": "a" * 64,
                    "artifact_sha256": "b" * 64,
                    "key_id": "demo-live-20260316",
                    "verified_locally": True,
                    "artifact_match": True,
                    "note": "key_id=demo-live-20260316 | bundle=current.bundle.json",
                },
            ),
            patch(
                "server.describe_demo_variant_support",
                side_effect=[
                    {
                        "variant": "current",
                        "status": "ready",
                        "mode": "signed_manifest_v1",
                        "label": "Current signed live 已支持",
                        "tone": "online",
                        "note": "Current signed-admission live path is supported.",
                        "supported": True,
                        "launch_allowed": True,
                    },
                    {
                        "variant": "baseline",
                        "status": "ready",
                        "mode": "legacy_sha",
                        "label": "PyTorch live 已支持",
                        "tone": "online",
                        "note": "PyTorch live path currently uses expected-SHA admission (legacy_sha).",
                        "supported": True,
                        "launch_allowed": True,
                    },
                ],
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["live"]["admission"]["mode"], "signed_manifest_v1")
        self.assertEqual(payload["live"]["admission"]["key_id"], "demo-live-20260316")
        self.assertTrue(payload["live"]["admission"]["verified_locally"])
        self.assertEqual(payload["live"]["variant_support"]["current"]["label"], "Current signed live 已支持")
        self.assertEqual(payload["live"]["variant_support"]["baseline"]["label"], "PyTorch live 已支持")
        self.assertTrue(payload["live"]["variant_support"]["baseline"]["launch_allowed"])
        self.assertEqual(payload["job_manifest_gate"]["admission_mode"], "signed_manifest_v1")
        self.assertEqual(payload["job_manifest_gate"]["variant"], "current")

    def test_job_manifest_gate_endpoint_returns_current_gate_details(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with (
            patch(
                "server.describe_demo_admission",
                return_value={
                    "status": "ready",
                    "mode": "signed_manifest_v1",
                    "label": "Signed manifest v1",
                    "tone": "online",
                    "bundle_path": "/tmp/openamp_demo_signed_admission/current.bundle.json",
                    "public_key_path": "/tmp/openamp_demo_signed_admission/current.public.pem",
                    "manifest_sha256": "a" * 64,
                    "artifact_sha256": "b" * 64,
                    "key_id": "demo-live-20260316",
                    "verified_locally": True,
                    "artifact_match": True,
                    "note": "key_id=demo-live-20260316 | bundle=current.bundle.json",
                },
            ),
            patch(
                "server.describe_demo_variant_support",
                return_value={
                    "variant": "current",
                    "status": "ready",
                    "mode": "signed_manifest_v1",
                    "label": "Current signed live 已支持",
                    "tone": "online",
                    "note": "Current signed-admission live path is supported.",
                    "supported": True,
                    "launch_allowed": True,
                },
            ),
        ):
            status, _, payload = request_json(state, "GET", "/api/job-manifest-gate")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["gate"]["variant"], "current")
        self.assertEqual(payload["gate"]["admission_mode"], "signed_manifest_v1")
        self.assertEqual(payload["gate"]["verdict"], "hold")
        self.assertTrue(any("missing password" in reason for reason in payload["gate"]["reasons"]))
        self.assertIn("wire schema", payload["gate"]["protocol_boundary_note"])

    def test_system_status_endpoint_surfaces_running_active_inference(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        running_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ],
            job_id="demo-job-active",
        )
        state._inference_jobs[running_job.job_id] = {
            "job": running_job,
            "job_id": running_job.job_id,
            "variant": "current",
            "image_index": 0,
        }

        status, _, payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertTrue(payload["active_inference"]["running"])
        self.assertEqual(payload["active_inference"]["job_id"], "demo-job-active")
        self.assertEqual(payload["active_inference"]["variant"], "current")
        self.assertEqual(payload["active_inference"]["queue_depth"], 1)
        self.assertEqual(payload["active_inference"]["progress"]["current_stage"], "板端执行中")

    def test_board_access_endpoint_accepts_password_only_and_keeps_preloaded_defaults(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        expected_env_file = state._board_access.env_file.relative_to(REPO_ROOT).as_posix()

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["host"], "100.121.87.73")
        self.assertEqual(payload["board_access"]["user"], "user")
        self.assertEqual(payload["board_access"]["port"], 22)
        self.assertEqual(payload["board_access"]["env_file"], expected_env_file)
        self.assertTrue(payload["board_access"]["has_password"])
        self.assertTrue(payload["board_access"]["connection_ready"])
        self.assertTrue(payload["board_access"]["inference_ready_variants"]["current"])
        self.assertTrue(payload["board_access"]["inference_ready_variants"]["baseline"])
        self.assertEqual(payload["board_access"]["field_sources"]["password"], "session")

    def test_board_access_endpoint_accepts_transport_mode_override(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "transport_mode": "usrp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["transport_mode"], "usrp")
        self.assertEqual(payload["board_access"]["transport_label"], "USRP 模式")
        self.assertEqual(payload["board_access"]["transport_tone"], "online")
        self.assertIn("USRP", payload["board_access"]["transport_label"])
        self.assertEqual(
            payload["board_access"]["transport_summary"],
            "USRP 模式：认证/控制面仍走 Tailscale/TCP，重建数据面走 USRP OTA。",
        )
        self.assertEqual(state._board_access.build_env()["MLKEM_TRANSPORT_MODE"], "usrp")
        self.assertEqual(state._board_access.build_env()["MLKEM_USRP_MODE"], "ota")
        self.assertEqual(state._board_access.build_env()["OPENAMP_DEMO_INPUT_SOURCE_MODE"], "usrp")

        with (
            patch.object(state, "_start_aircraft_position_upstream_probe_refresh"),
            patch.object(state, "_start_board_position_api_refresh"),
            patch.object(state, "_start_usrp_control_status_refresh"),
        ):
            system_status, _, system_payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(system_status, 200)
        self.assertEqual(system_payload["board_access"]["transport_mode"], "usrp")
        self.assertEqual(system_payload["board_access"]["transport_label"], "USRP 模式")
        self.assertEqual(system_payload["board_access"]["input_source_mode"], "usrp")

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "tcp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["transport_mode"], "tcp")
        self.assertEqual(payload["board_access"]["input_source_mode"], "prerecorded")
        self.assertEqual(state._board_access.build_env()["OPENAMP_DEMO_INPUT_SOURCE_MODE"], "prerecorded")

    def test_board_access_endpoint_accepts_remote_usrp_rx_dir_override(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "password": "demo-pass",
                    "transport_mode": "usrp",
                    "remote_usrp_rx_dir": "/home/user/cockpit_usrp_rx",
                }
            ).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["transport_mode"], "usrp")
        self.assertEqual(payload["board_access"]["remote_usrp_rx_dir"], "/home/user/cockpit_usrp_rx")
        self.assertEqual(state._board_access.build_env()["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx")

    def test_board_access_endpoint_rejects_unsupported_transport_mode(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "transport_mode": "bluetooth"}).encode("utf-8"),
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["message"], "unsupported transport_mode; expected tcp or usrp")

    def test_board_access_usrp_defaults_discover_workspace_original_images(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "usrp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        image_dir = Path(payload["board_access"]["local_usrp_image_dir"])
        self.assertEqual(image_dir.name, "原始图像")
        self.assertTrue((image_dir / "00000001.jpg").is_file())
        self.assertTrue((image_dir / "00000050.jpg").is_file())
        self.assertEqual(state._board_access.build_env()["OPENAMP_DEMO_LOCAL_IMAGE_DIR"], str(image_dir))

    def test_board_access_usrp_defaults_prepare_latents_from_original_images(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "usrp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        latent_dir = Path(payload["board_access"]["local_usrp_input_dir"])
        self.assertEqual(latent_dir.name, "encoder_outputs_airfield300")
        env = state._board_access.build_env()
        self.assertEqual(env["OPENAMP_DEMO_LOCAL_LATENT_DIR"], str(latent_dir))
        self.assertEqual(env["OPENAMP_DEMO_IMAGE_TO_LATENT_OUTPUT_DIR"], str(latent_dir))
        self.assertEqual(env["OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED"], "1")

    def test_board_access_usrp_forwards_docker_runner_environment(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.dict(
            os.environ,
            {
                "OPENAMP_SSH_RUNNER": "docker",
                "OPENAMP_SSH_DOCKER_IMAGE": "iccomp-usrp-tx:latest",
                "OPENAMP_USRP_TX_RUNNER": "docker",
                "OPENAMP_USRP_TX_DOCKER_IMAGE": "iccomp-usrp-tx:latest",
                "OPENAMP_TVM_BATCH_RUNNER": "biglittle",
                "OPENAMP_TVM_BATCH_EXIT_GRACE_SEC": "0.5",
            },
            clear=False,
        ):
            status, _, _ = request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"transport_mode": "usrp", "jscc_link_mode": "qpsk"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        env = state._board_access.build_env()
        self.assertEqual(env["OPENAMP_SSH_RUNNER"], "docker")
        self.assertEqual(env["OPENAMP_SSH_DOCKER_IMAGE"], "iccomp-usrp-tx:latest")
        self.assertEqual(env["OPENAMP_USRP_TX_RUNNER"], "docker")
        self.assertEqual(env["OPENAMP_USRP_TX_DOCKER_IMAGE"], "iccomp-usrp-tx:latest")
        self.assertEqual(env["OPENAMP_TVM_BATCH_RUNNER"], "biglittle")
        self.assertEqual(env["OPENAMP_TVM_BATCH_EXIT_GRACE_SEC"], "0.5")

    def test_board_access_usrp_iq_defaults_fast_rx_arm_status_timeout(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch.dict(
            os.environ,
            {
                "ANALOG_PRECONNECT_CONTROL": "",
                "ANALOG_REMOTE_CLEANUP_MODE": "",
                "ANALOG_REMOTE_DECODE_RESPONSE_MODE": "",
                "ANALOG_REMOTE_DECODED_FORMAT": "",
                "ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY": "",
                "ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC": "",
                "ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS": "",
                "ANALOG_RX_SC16_MMAP": "",
                "ANALOG_RX_CLIPPING_DECIMATION": "",
                "ANALOG_RX_POST_QUANTIZE": "",
                "ANALOG_RX_SESSION_CONTROL": "",
                "ANALOG_RX_BATCH_SESSION_CONTROL": "",
                "ANALOG_RX_BATCH_SESSION_MAX_IMAGES": "",
                "ANALOG_PIPELINE_DEPTH": "",
                "ANALOG_PIPELINE_RF_DECODE_OVERLAP": "",
                "ANALOG_REMOTE_DECODE_WORKER_PREFIX": "",
                "ANALOG_RETRY_ON_BURST_MISS": "",
                "ANALOG_RETRY_ON_LOW_SYNC": "",
                "ANALOG_LOW_SYNC_RETRY_THRESHOLD": "",
                "ANALOG_SYNC_PROFILE": "",
                "ANALOG_FAST_SYNC_CANDIDATES": "",
                "ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS": "",
                "ANALOG_FALLBACK_SYNC_CANDIDATES": "",
                "ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS": "",
                "ANALOG_IQ_QUALITY_GATE": "",
                "ANALOG_IQ_MIN_PILOT_GAIN_RATIO": "",
                "ANALOG_IQ_MAX_EVM_RMS": "",
                "ANALOG_IQ_MIN_SNR_DB": "",
                "OPENAMP_IQ_SEGMENT_SIZE": "",
                "OPENAMP_IQ_SEGMENT_REPAIR_PASSES": "",
                "MLKEM_USRP_MAX_ARQ_ROUNDS": "",
                "ANALOG_RX_ARM_STATUS_TIMEOUT_SEC": "",
                "ANALOG_RX_ARM_STATUS_POLL_SEC": "",
                "ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC": "",
                "ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC": "",
                "ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC": "",
                "ANALOG_RX_STOP_DRAIN_POLL_SEC": "",
                "RX_ARM_WAIT_MS": "",
                "RX_STOP_WAIT_MS": "",
                "REMOTE_USRP_RX_DIR": "",
                "REMOTE_RX_RUN_ROOT": "",
            },
            clear=False,
        ):
            status, _, _ = request_json(
                state,
                "POST",
                "/api/session/board-access",
                body=json.dumps({"transport_mode": "usrp", "jscc_link_mode": "iq-direct"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        env = state._board_access.build_env()
        self.assertEqual(env["REMOTE_USRP_RX_DIR"], "/home/user/cockpit_usrp_rx")
        self.assertEqual(env["REMOTE_RX_RUN_ROOT"], "/dev/shm/usrp292x_remote_runs")
        self.assertEqual(env["ANALOG_PRECONNECT_CONTROL"], "1")
        self.assertEqual(env["ANALOG_REMOTE_CLEANUP_MODE"], "skip")
        self.assertEqual(env["ANALOG_REMOTE_DECODE_RESPONSE_MODE"], "minimal")
        self.assertEqual(env["ANALOG_REMOTE_DECODED_FORMAT"], "npy")
        self.assertEqual(env["ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY"], "1")
        self.assertEqual(env["ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC"], "0.05")
        self.assertEqual(env["ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS"], "1")
        self.assertEqual(env["ANALOG_RX_SC16_MMAP"], "1")
        self.assertEqual(env["ANALOG_RX_CLIPPING_DECIMATION"], "8")
        self.assertEqual(env["ANALOG_RX_POST_QUANTIZE"], "0")
        self.assertEqual(env["ANALOG_RX_SESSION_CONTROL"], "1")
        self.assertEqual(env["ANALOG_RX_BATCH_SESSION_CONTROL"], "1")
        self.assertEqual(env["ANALOG_RX_BATCH_SESSION_MAX_IMAGES"], "16")
        self.assertEqual(env["ANALOG_PIPELINE_DEPTH"], "1")
        self.assertEqual(env["ANALOG_PIPELINE_RF_DECODE_OVERLAP"], "0")
        self.assertNotIn("ANALOG_REMOTE_DECODE_WORKER_PREFIX", env)
        self.assertEqual(env["ANALOG_RETRY_ON_BURST_MISS"], "1")
        self.assertEqual(env["ANALOG_RETRY_ON_LOW_SYNC"], "1")
        self.assertEqual(env["ANALOG_LOW_SYNC_RETRY_THRESHOLD"], "0.08")
        self.assertEqual(env["ANALOG_SYNC_PROFILE"], "fast-first")
        self.assertEqual(env["ANALOG_FAST_SYNC_CANDIDATES"], "4")
        self.assertEqual(env["ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS"], "1024")
        self.assertEqual(env["ANALOG_FALLBACK_SYNC_CANDIDATES"], "4")
        self.assertEqual(env["ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS"], "1024")
        self.assertEqual(env["ANALOG_IQ_QUALITY_GATE"], "1")
        self.assertEqual(env["ANALOG_IQ_QUALITY_MIN_SYNC_METRIC"], "0.75")
        self.assertEqual(env["ANALOG_IQ_MIN_PILOT_GAIN_RATIO"], "0.85")
        self.assertEqual(env["ANALOG_IQ_MAX_EVM_RMS"], "0.75")
        self.assertEqual(env["ANALOG_IQ_MIN_SNR_DB"], "3.0")
        self.assertEqual(env["OPENAMP_IQ_SEGMENT_SIZE"], "30")
        self.assertEqual(env["OPENAMP_IQ_SEGMENT_REPAIR_PASSES"], "2")
        self.assertEqual(env["MLKEM_USRP_MAX_ARQ_ROUNDS"], "12")
        self.assertEqual(env["ANALOG_RX_ARM_STATUS_TIMEOUT_SEC"], "0.5")
        self.assertEqual(env["ANALOG_RX_ARM_STATUS_POLL_SEC"], "0.025")
        self.assertNotIn("ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC", env)
        self.assertEqual(env["ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC"], "1.5")
        self.assertEqual(env["ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC"], "8.0")
        self.assertEqual(env["ANALOG_RX_STOP_DRAIN_POLL_SEC"], "0.05")
        self.assertEqual(env["RX_ARM_WAIT_MS"], "500")
        self.assertEqual(env["RX_STOP_WAIT_MS"], "8000")

    def test_board_access_endpoint_accepts_jscc_link_mode_override(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "usrp", "jscc_link_mode": "iq-direct"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["jscc_link_mode"], "iq-direct")
        self.assertEqual(state._board_access.build_env()["JSCC_LINK_MODE"], "iq-direct")

    def test_board_access_usrp_defaults_to_iq_direct_link_mode(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "usrp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["transport_mode"], "usrp")
        self.assertEqual(payload["board_access"]["jscc_link_mode"], "iq-direct")
        self.assertEqual(state._board_access.build_env()["JSCC_LINK_MODE"], "iq-direct")

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"transport_mode": "tcp"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["transport_mode"], "tcp")
        self.assertEqual(payload["board_access"]["input_source_mode"], "prerecorded")

    def test_usrp_live_payload_uses_original_gallery_range(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})

        payload = state._build_live_payload_from_batch_summary(
            engine="tvm",
            job_id="usrp-gallery-50",
            count=50,
            summary={
                "processed_count": 50,
                "selected_input_count": 50,
                "run_samples_ms": [250.0],
                "run_median_ms": 250.0,
                "run_mean_ms": 250.0,
            },
        )

        self.assertEqual(payload["original_gallery"]["mode"], "usrp")
        self.assertEqual(payload["original_gallery"]["range"]["start"], 1)
        self.assertEqual(payload["original_gallery"]["range"]["end"], 50)
        self.assertEqual(payload["original_gallery"]["images"][0]["filename"], "00000001.jpg")
        self.assertEqual(payload["original_gallery"]["images"][-1]["filename"], "00000050.jpg")
        self.assertTrue(payload["image_sources"]["original_path"].endswith("00000001.jpg"))
        self.assertTrue(payload["original_image_b64"].startswith("data:image/jpeg;base64,"))

    def test_usrp_live_payload_exposes_debug_quality_pairs_without_archived_quality(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._board_access = state._board_access.with_env_overrides({"MLKEM_TRANSPORT_MODE": "usrp"})

        payload = state._build_live_payload_from_batch_summary(
            engine="tvm",
            job_id="usrp-quality-pairs",
            count=30,
            summary={
                "processed_count": 30,
                "selected_input_count": 30,
                "run_samples_ms": [250.0],
                "run_median_ms": 250.0,
                "run_mean_ms": 250.0,
            },
        )

        self.assertNotIn("quality", payload)
        pairs = payload["quality_pairs"]
        self.assertEqual(pairs["pytorch_tvm"]["label"], "PyTorch-TVM")
        self.assertGreater(pairs["pytorch_tvm"]["psnr_db"], 30.0)
        self.assertGreater(pairs["pytorch_tvm"]["ssim"], 0.9)
        self.assertEqual(pairs["original_tvm"]["label"], "原图-TVM")
        self.assertGreater(pairs["original_tvm"]["psnr_db"], 20.0)
        self.assertGreater(pairs["original_tvm"]["ssim"], 0.8)
        self.assertIn("reconstruction_error_audit_usrp", pairs["original_tvm"]["report_path"])

    def test_board_access_env_switch_refreshes_current_trusted_sha_runtime(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        legacy_env = "session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env"

        status, _, payload = request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass", "env_file": legacy_env}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["board_access"]["env_file"], legacy_env)
        self.assertEqual(state._trusted_current_sha, "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1")

        status, _, system_payload = request_json(state, "GET", "/api/system-status")

        self.assertEqual(status, 200)
        self.assertEqual(
            system_payload["live"]["trusted_sha"],
            "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
        )
        self.assertEqual(
            system_payload["live"]["admission"]["artifact_sha256"],
            "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
        )

    def test_probe_board_endpoint_updates_snapshot_after_success(self) -> None:
        success = live_probe_payload("2026-03-15T12:00:00+0800", "board reachable")
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch("server.run_live_probe", return_value=success):
            probe_status, _, probe_payload = request_json(state, "POST", "/api/probe-board", body=b"{}")
            snapshot_status, _, snapshot_payload = request_json(state, "GET", "/api/snapshot")

        self.assertEqual(probe_status, 200)
        self.assertEqual(probe_payload, success)
        self.assertEqual(snapshot_status, 200)
        self.assertEqual(snapshot_payload["mode"]["effective_label"], "在线读数可用")
        self.assertEqual(snapshot_payload["board"]["current_status"]["label"], "最新只读 SSH 探板")
        self.assertEqual(snapshot_payload["board"]["current_status"]["requested_at"], success["requested_at"])
        self.assertTrue(snapshot_payload["board"]["current_status"]["reachable"])

    def test_probe_board_endpoint_uses_saved_session_access_when_present(self) -> None:
        success = live_probe_payload("2026-03-15T12:00:00+0800", "board reachable")
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "demo-pass",
                    "port": "2202",
                }
            ).encode("utf-8"),
        )

        with (
            patch("server.run_live_probe", return_value=success) as run_probe,
            patch("server.query_live_status", return_value={"status": "error", "message": "skip"}) as query_status,
        ):
            probe_status, _, probe_payload = request_json(state, "POST", "/api/probe-board", body=b"{}")

        self.assertEqual(probe_status, 200)
        self.assertEqual(probe_payload["requested_at"], success["requested_at"])
        run_probe.assert_called_once()
        self.assertEqual(run_probe.call_args.kwargs["env_values"]["REMOTE_HOST"], "demo-board")
        self.assertEqual(run_probe.call_args.kwargs["env_values"]["REMOTE_USER"], "demo-user")
        self.assertEqual(run_probe.call_args.kwargs["env_values"]["REMOTE_PASS"], "demo-pass")
        self.assertEqual(run_probe.call_args.kwargs["env_values"]["REMOTE_SSH_PORT"], "2202")
        query_status.assert_called_once()

    def test_probe_board_endpoint_returns_failure_without_mutating_snapshot(self) -> None:
        failure = failed_probe_payload(
            "2026-03-15T12:05:00+0800",
            "probe failed",
            "ssh timeout",
        )
        state = DashboardState(None, 30.0, probe_cache_path=None)

        with patch("server.run_live_probe", return_value=failure):
            probe_status, _, probe_payload = request_json(state, "POST", "/api/probe-board", body=b"{}")
            snapshot_status, _, snapshot_payload = request_json(state, "GET", "/api/snapshot")

        self.assertEqual(probe_status, 200)
        self.assertEqual(probe_payload, failure)
        self.assertEqual(snapshot_status, 200)
        self.assertEqual(snapshot_payload["mode"]["effective_label"], "仅展示证据")
        self.assertEqual(snapshot_payload["board"]["current_status"]["label"], "暂无在线探板")
        self.assertFalse(snapshot_payload["board"]["current_status"]["reachable"])
        self.assertEqual(snapshot_payload["board"]["current_status"]["requested_at"], "")

    def test_run_inference_endpoint_falls_back_until_password_is_provided(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, payload = request_json(
            state,
            "POST",
            "/api/run-inference",
            body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload["execution_mode"], "prerecorded")
        self.assertEqual(payload["variant"], "current")
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["request_state"], "completed")
        self.assertEqual(payload["status_category"], "config_error")
        self.assertIn("配置不完整或不可用", payload["message"])
        self.assertEqual(payload["live_attempt"]["status"], "config_error")
        self.assertEqual(payload["live_attempt"]["diagnostics"]["missing_fields"], ["password"])
        self.assertEqual(payload["live_progress"]["completed_count"], 0)
        self.assertEqual(payload["live_progress"]["expected_count"], server.DEFAULT_MAX_INPUTS)
        self.assertEqual(payload["live_progress"]["count_label"], f"0 / {server.DEFAULT_MAX_INPUTS}")
        self.assertIsNone(payload["timings"]["payload_ms"])
        self.assertIsNone(payload["timings"]["total_ms"])
        self.assertEqual(payload["timings"]["stages"], [])
        self.assertIn("guided_demo", state.current_snapshot())

    def test_run_inference_endpoint_starts_live_job_with_preloaded_env_after_password_only_save(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        saved_access = state._board_access
        live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ]
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch(
                "server.launch_remote_reconstruction_job",
                return_value=live_job,
            ) as launch_job,
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["request_state"], "running")
        self.assertEqual(payload["job_id"], live_job.job_id)
        access = launch_job.call_args.args[0]
        self.assertIs(access, saved_access)
        self.assertEqual(access.host, "100.121.87.73")
        self.assertEqual(access.user, "user")
        self.assertEqual(access.password, "demo-pass")
        self.assertEqual(access.env_file, saved_access.env_file)
        self.assertEqual(
            access.build_env()["INFERENCE_CURRENT_EXPECTED_SHA256"],
            "bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb",
        )

    def test_run_inference_endpoint_blocks_when_demo_already_has_running_live_job(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        running_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ],
            job_id="demo-job-001",
        )
        state._inference_jobs[running_job.job_id] = {
            "job": running_job,
            "job_id": running_job.job_id,
            "variant": "current",
            "image_index": 0,
        }

        with patch("server.launch_remote_reconstruction_job") as launch_job:
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["status_category"], "board_busy")
        self.assertIn("demo-job-001", payload["message"])
        self.assertEqual(payload["live_attempt"]["status"], "blocked")
        launch_job.assert_not_called()

    def test_run_inference_endpoint_blocks_when_live_status_reports_job_active(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )

        with (
            patch(
                "server.describe_demo_variant_support",
                return_value={
                    "variant": "current",
                    "status": "ready",
                    "mode": "signed_manifest_v1",
                    "label": "Current signed live 已支持",
                    "tone": "online",
                    "note": "Current signed-admission live path is supported.",
                    "supported": True,
                    "launch_allowed": True,
                },
            ),
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "JOB_ACTIVE",
                    "active_job_id": 8093,
                    "last_fault_code": "DUPLICATE_JOB_ID",
                    "logs": ["[02:27:52] STATUS_RESP: guard=JOB_ACTIVE"],
                },
            ),
            patch("server.launch_remote_reconstruction_job") as launch_job,
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["status_category"], "board_busy")
        self.assertIn("Current signed-admission live path 已支持", payload["message"])
        self.assertIn("guard_state=JOB_ACTIVE", payload["message"])
        self.assertEqual(payload["live_attempt"]["diagnostics"]["board_status"]["active_job_id"], 8093)
        launch_job.assert_not_called()

    def test_run_inference_endpoint_falls_back_to_runner_only_live_when_status_preflight_fails(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "Current live 已切到 SSH 兼容模式，界面正在同步板端执行进度。",
                    "control_transport": "none",
                    "control_handshake_complete": False,
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {
                        "control_preflight": {
                            "status": "timeout",
                            "status_category": "timeout",
                        }
                    },
                    "progress": live_progress_payload("真实在线执行（控制面降级）", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ],
            job_id="compat-live-001",
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "timeout",
                    "status_category": "timeout",
                    "message": "远端状态查询超时，请确认板卡在线后重试。",
                    "diagnostics": {"error": "STATUS_REQ tx_ok_rx_timeout"},
                    "logs": [],
                },
            ),
            patch("server.launch_remote_reconstruction_job", return_value=live_job) as launch_job,
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["source_label"], "真实在线执行（控制面降级）")
        self.assertIn("SSH 兼容模式", payload["message"])
        self.assertEqual(payload["live_attempt"]["control_transport"], "none")
        self.assertFalse(payload["live_attempt"]["control_handshake_complete"])
        launch_job.assert_called_once()
        _, kwargs = launch_job.call_args
        self.assertEqual(kwargs["control_transport"], "none")
        self.assertEqual(
            kwargs["control_preflight"]["status"],
            "timeout",
        )

    def test_run_baseline_endpoint_starts_pytorch_live_job(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "baseline",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                }
            ],
            job_id="demo-pytorch-001",
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch("server.launch_remote_reconstruction_job", return_value=live_job) as launch_job,
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-baseline",
                body=json.dumps({"image_index": 0}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["request_state"], "running")
        self.assertEqual(payload["variant"], "baseline")
        self.assertEqual(payload["job_id"], "demo-pytorch-001")
        self.assertEqual(payload["source_label"], "真实在线推进")
        self.assertIn("OpenAMP 控制面已接管", payload["message"])
        launch_job.assert_called_once()
        self.assertEqual(launch_job.call_args.kwargs["max_inputs"], server.DEFAULT_MAX_INPUTS)

    def test_inference_progress_endpoint_returns_completed_live_payload(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                },
                {
                    "status": "success",
                    "request_state": "completed",
                    "status_category": "success",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已完成作业下发、板端执行与结果回收。",
                    "runner_summary": {
                        "load_ms": 3.2,
                        "vm_init_ms": 0.8,
                        "run_median_ms": 128.4,
                        "artifact_sha256": "abcd" * 16,
                    },
                    "wrapper_summary": {"result": "success"},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
                    "artifacts": {},
                },
            ]
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch(
                "server.launch_remote_reconstruction_job",
                return_value=live_job,
            ) as launch_job,
        ):
            start_status, _, start_payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )
            status, _, payload = request_json(
                state,
                "GET",
                f"/api/inference-progress?job_id={live_job.job_id}",
            )

        self.assertEqual(start_status, 200)
        self.assertEqual(start_payload["request_state"], "running")
        self.assertEqual(status, 200)
        self.assertEqual(payload["request_state"], "completed")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["source_label"], "真实在线推进 + 归档样例图")
        self.assertAlmostEqual(payload["timings"]["total_ms"], 132.4)
        self.assertEqual(payload["artifact_sha"], "abcd" * 16)
        self.assertEqual(payload["live_progress"]["completed_count"], server.DEFAULT_MAX_INPUTS)
        self.assertEqual(payload["live_progress"]["expected_count"], server.DEFAULT_MAX_INPUTS)
        self.assertEqual(payload["live_progress"]["count_source"], "runner_summary.processed_count")
        launch_job.assert_called_once()
        access = launch_job.call_args.args[0]
        self.assertEqual(
            access.build_env()["INFERENCE_CURRENT_EXPECTED_SHA256"],
            "bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb",
        )

    def test_inference_progress_endpoint_uses_nested_pipeline_summary_for_live_payload(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps({"password": "demo-pass"}).encode("utf-8"),
        )
        nested_pipeline_sha = "beef" * 16
        live_job = FakeInferenceJob(
            [
                {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已接管本次演示，界面正在同步板端阶段。",
                    "runner_summary": {},
                    "wrapper_summary": {},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "running", 76, "板端执行中"),
                    "artifacts": {},
                },
                {
                    "status": "success",
                    "request_state": "completed",
                    "status_category": "success",
                    "execution_mode": "live",
                    "variant": "current",
                    "message": "OpenAMP 控制面已完成作业下发、板端执行与结果回收。",
                    "runner_summary": {
                        "pipeline": {
                            "load_ms": 3.2,
                            "vm_init_ms": 0.8,
                            "ms_per_image": 239.4,
                            "run_median_ms": 168.1,
                            "artifact_sha256": nested_pipeline_sha,
                        }
                    },
                    "wrapper_summary": {"result": "success"},
                    "diagnostics": {},
                    "progress": live_progress_payload("真实在线推进", "completed", 100, "已返回结果"),
                    "artifacts": {},
                },
            ],
            job_id="demo-pipeline-001",
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch("server.launch_remote_reconstruction_job", return_value=live_job),
        ):
            start_status, _, start_payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )
            status, _, payload = request_json(
                state,
                "GET",
                f"/api/inference-progress?job_id={live_job.job_id}",
            )

        self.assertEqual(start_status, 200)
        self.assertEqual(start_payload["request_state"], "running")
        self.assertEqual(status, 200)
        self.assertEqual(payload["request_state"], "completed")
        self.assertEqual(payload["execution_mode"], "live")
        self.assertAlmostEqual(payload["timings"]["payload_ms"], 239.4)
        self.assertAlmostEqual(payload["timings"]["prepare_ms"], 4.0)
        self.assertAlmostEqual(payload["timings"]["total_ms"], 239.4)
        self.assertEqual(payload["timings"]["stages"][0]["label"], "板端重建（流水线）")
        self.assertEqual(payload["artifact_sha"], nested_pipeline_sha)

    def test_inference_progress_endpoint_returns_not_found_for_unknown_job(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "GET",
            "/api/inference-progress?job_id=missing-job",
        )

        self.assertEqual(status, 404)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["message"], "job not found")

    def test_inference_progress_endpoint_preserves_live_failure_diagnostics_on_fallback(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "placeholder-pass",
                    "port": "22",
                    "env_file": "session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env",
                }
            ).encode("utf-8"),
        )
        live_job = FakeInferenceJob(
            [
                {
                    "status": "error",
                    "request_state": "completed",
                    "status_category": "auth_error",
                    "execution_mode": "fallback",
                    "variant": "current",
                    "message": "远端推理认证失败，请检查板卡用户名、密码或 SSH 端口设置。 当前已回退到预录结果。",
                    "runner_summary": {},
                    "wrapper_summary": {"result": "runner_failed"},
                    "diagnostics": {"stderr": "Permission denied (publickey,password).", "returncode": 255},
                    "progress": live_progress_payload("在线失败已回退", "completed", 100, "已返回结果"),
                    "artifacts": {},
                }
            ]
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch(
                "server.launch_remote_reconstruction_job",
                return_value=live_job,
            ),
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "prerecorded")
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["status_category"], "auth_error")
        self.assertIn("认证失败", payload["message"])
        self.assertNotIn("Permission denied", payload["message"])
        self.assertEqual(payload["live_attempt"]["diagnostics"]["stderr"], "Permission denied (publickey,password).")
        self.assertEqual(payload["live_progress"]["label"], "在线失败已回退")
        self.assertIsNone(payload["timings"]["payload_ms"])
        self.assertIsNone(payload["timings"]["total_ms"])
        self.assertEqual(payload["timings"]["stages"], [])

    def test_inference_timeout_fallback_marks_handshake_incomplete_and_archive_only(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "placeholder-pass",
                    "port": "22",
                    "env_file": "session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env",
                }
            ).encode("utf-8"),
        )
        live_job = FakeInferenceJob(
            [
                {
                    "status": "error",
                    "request_state": "completed",
                    "status_category": "timeout",
                    "execution_mode": "fallback",
                    "variant": "current",
                    "message": (
                        "STATUS_REQ 已写入 RPMsg，但超时前未收到 STATUS_RESP；"
                        "JOB_REQ 已写入 RPMsg，但超时前未收到 JOB_ACK。"
                        "本次板端握手未完成，界面已回退到预录结果。"
                    ),
                    "control_handshake_complete": False,
                    "runner_summary": {},
                    "wrapper_summary": {"result": "denied_by_control_hook"},
                    "diagnostics": {
                        "control_handshake": {
                            "complete": False,
                            "status_req_transport": "tx_ok_rx_timeout",
                            "job_req_transport": "tx_ok_rx_timeout",
                        }
                    },
                    "progress": live_progress_payload("握手未完成，已回退", "completed", 0, "连接失败"),
                    "artifacts": {},
                }
            ]
        )

        with (
            patch(
                "server.query_live_status",
                return_value={
                    "status": "success",
                    "guard_state": "READY",
                    "active_job_id": 0,
                    "last_fault_code": "NONE",
                    "total_fault_count": 0,
                    "logs": [],
                },
            ),
            patch(
                "server.launch_remote_reconstruction_job",
                return_value=live_job,
            ),
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/run-inference",
                body=json.dumps({"image_index": 0, "mode": "current"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "prerecorded")
        self.assertEqual(payload["status"], "fallback")
        self.assertEqual(payload["status_category"], "timeout")
        self.assertEqual(payload["source_label"], "握手未完成，回退展示（归档样例）")
        self.assertIn("不宣称本次 live 已完成", payload["message"])
        self.assertFalse(payload["live_attempt"]["control_handshake_complete"])
        self.assertEqual(payload["live_progress"]["label"], "握手未完成，已回退")
        self.assertIsNone(payload["timings"]["payload_ms"])
        self.assertIsNone(payload["timings"]["total_ms"])
        self.assertEqual(payload["timings"]["stages"], [])

    def test_inject_fault_endpoint_keeps_live_attempt_diagnostics_on_replay_fallback(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "placeholder-pass",
                    "port": "22",
                }
            ).encode("utf-8"),
        )

        with patch(
            "server.run_fault_action",
            return_value={
                "status": "parse_error",
                "status_category": "auth_error",
                "message": "远端故障注入认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
                "diagnostics": {"stderr": "Permission denied (publickey,password).", "returncode": 255},
                "logs": [],
            },
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/inject-fault",
                body=json.dumps({"fault_type": "wrong_sha"}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "replay")
        self.assertEqual(payload["status_category"], "auth_error")
        self.assertIn("认证失败", payload["message"])
        self.assertNotIn("Permission denied", payload["message"])
        self.assertEqual(payload["live_attempt"]["diagnostics"]["stderr"], "Permission denied (publickey,password).")

    def test_inject_fault_endpoint_returns_replay_when_not_configured(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, payload = request_json(
            state,
            "POST",
            "/api/inject-fault",
            body=json.dumps({"fault_type": "wrong_sha"}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "replay")
        self.assertEqual(payload["fit_id"], "FIT-01")
        self.assertIn("回放", payload["source_label"])

    def test_inject_fault_endpoint_uses_updated_current_sha_after_env_switch(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "password": "placeholder-pass",
                    "env_file": "session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env",
                }
            ).encode("utf-8"),
        )

        with patch(
            "server.run_fault_action",
            return_value={
                "status": "parse_error",
                "status_category": "auth_error",
                "message": "远端故障注入认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
                "diagnostics": {"stderr": "Permission denied (publickey,password).", "returncode": 255},
                "logs": [],
            },
        ) as run_fault_action:
            request_json(
                state,
                "POST",
                "/api/inject-fault",
                body=json.dumps({"fault_type": "wrong_sha"}).encode("utf-8"),
            )

        self.assertEqual(
            run_fault_action.call_args.kwargs["trusted_sha"],
            "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
        )

    def test_recover_endpoint_keeps_retained_fault_visible_on_live_safe_stop(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "placeholder-pass",
                    "port": "22",
                }
            ).encode("utf-8"),
        )

        with patch(
            "server.run_recover_action",
            return_value={
                "status": "success",
                "guard_state": "READY",
                "last_fault_code": "HEARTBEAT_TIMEOUT",
                "board_response": {
                    "decision": "ACK",
                    "fault_code": "HEARTBEAT_TIMEOUT",
                    "guard_state": "READY",
                },
                "logs": ["[02:36:22] ◀ STATUS_RESP: READY，last_fault=HEARTBEAT_TIMEOUT"],
            },
        ):
            status, _, payload = request_json(
                state,
                "POST",
                "/api/recover",
                body=json.dumps({}).encode("utf-8"),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "live")
        self.assertEqual(payload["source_label"], "真机 SAFE_STOP 收口")
        self.assertEqual(payload["guard_state"], "READY")
        self.assertEqual(payload["last_fault_code"], "HEARTBEAT_TIMEOUT")
        self.assertEqual(payload["status_lamp"], "yellow")
        self.assertIn("不宣称已清零", payload["message"])

    def test_recover_endpoint_uses_updated_current_sha_after_env_switch(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        request_json(
            state,
            "POST",
            "/api/session/board-access",
            body=json.dumps(
                {
                    "password": "placeholder-pass",
                    "env_file": "session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env",
                }
            ).encode("utf-8"),
        )

        with patch(
            "server.run_recover_action",
            return_value={
                "status": "parse_error",
                "status_category": "auth_error",
                "message": "远端恢复认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
                "diagnostics": {"stderr": "Permission denied (publickey,password).", "returncode": 255},
                "logs": [],
            },
        ) as run_recover_action:
            request_json(
                state,
                "POST",
                "/api/recover",
                body=json.dumps({}).encode("utf-8"),
            )

        self.assertEqual(
            run_recover_action.call_args.kwargs["trusted_sha"],
            "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
        )

    def test_recover_endpoint_replay_preserves_latest_fault_code(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        state._last_fault_result = {
            "fault_type": "wrong_sha",
            "status": "injected",
            "status_category": "success",
            "execution_mode": "replay",
            "message": "cached replay",
            "guard_state": "READY",
            "last_fault_code": "ARTIFACT_SHA_MISMATCH",
        }

        status, _, payload = request_json(
            state,
            "POST",
            "/api/recover",
            body=json.dumps({}).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "replay")
        self.assertEqual(payload["source_label"], "SAFE_STOP 收口回放")
        self.assertEqual(payload["guard_state"], "READY")
        self.assertEqual(payload["last_fault_code"], "ARTIFACT_SHA_MISMATCH")
        self.assertEqual(payload["status_lamp"], "yellow")
        self.assertIn("保留最近 fault code", payload["message"])

    def test_root_serves_dashboard_entry_page(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, body = request_text(state, "GET", "/")

        self.assertEqual(status, 200)
        self.assertTrue(headers["content-type"].startswith("text/html"))
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIn("<title>飞腾多核弱网安全语义视觉回传演示系统</title>", body)
        self.assertIn("飞腾多核弱网安全语义视觉回传系统", body)
        self.assertIn('id="cockpitShell"', body)
        self.assertIn('id="flightStage"', body)
        self.assertIn('id="aircraftVector"', body)
        self.assertIn('id="aircraftContractStrip"', body)
        self.assertIn('<div class="mission-stage-main">', body)
        self.assertIn('id="missionCoreCard"', body)
        self.assertIn('id="comparePeekCard"', body)
        self.assertIn('id="missionCurrentLaunch"', body)
        self.assertIn('id="missionRunCurrentButton"', body)
        self.assertIn("启动远端 Current 重建", body)
        self.assertIn("展开 Current 重建详情", body)
        self.assertIn('id="missionCurrentProgressBadge"', body)
        self.assertIn('id="missionCurrentProgressCount"', body)
        self.assertIn('id="missionCurrentProgressBar"', body)
        self.assertIn('id="missionCurrentProgressStage"', body)
        self.assertIn('id="missionCurrentProgressMeta"', body)
        self.assertIn('id="missionPasswordInline"', body)
        self.assertIn('id="missionPasswordStatus"', body)
        self.assertIn('id="missionPasswordInput"', body)
        self.assertIn('id="missionPasswordSaveButton"', body)
        self.assertIn('id="weakNetworkConsole"', body)
        self.assertIn('id="operatorCueShell"', body)
        self.assertIn('id="mainSafetyMirror"', body)
        self.assertIn('id="sessionDrawer"', body)
        self.assertIn('id="compareDrawer"', body)
        self.assertIn('id="safetyDrawer"', body)
        self.assertIn('id="compareViewerBoard"', body)
        self.assertIn('id="compareViewerSampleLabel"', body)
        self.assertIn('id="baselineProgressTitle"', body)
        self.assertIn("PyTorch reference 300 张图", body)
        self.assertIn("运行 PyTorch live 数据面 300 张图", body)
        self.assertIn('<script src="/app.js"></script>', body)

    def test_app_js_serves_dashboard_javascript(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, body = request_text(state, "GET", "/app.js")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/javascript; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIn("const state = {", body)
        self.assertIn('fetchJSON("/api/snapshot")', body)
        self.assertIn('fetchJSON("/api/system-status")', body)
        self.assertIn('fetchJSON("/api/link-director")', body)
        self.assertIn('fetchJSON("/api/archive/sessions?limit=25")', body)
        self.assertIn('fetchJSON(`/api/archive/session?session_id=${encodeURIComponent(nextArchiveSessionId)}&limit=25`)', body)
        self.assertIn('fetchJSON("/api/link-director/profile"', body)
        self.assertIn("systemStatus?.aircraft_position", body)
        self.assertIn('document.getElementById("aircraftContractStrip")', body)
        self.assertIn("aircraft.feed_contract?.summary", body)
        self.assertIn("renderCockpitShell", body)
        self.assertIn("openDrawer", body)
        self.assertIn("closeDrawer", body)
        self.assertIn("normalizeOperatorCue", body)
        self.assertIn("renderOperatorCue", body)
        self.assertIn("renderWeakNetworkConsole", body)
        self.assertNotIn("navigator.geolocation", body)
        self.assertIn("hydrateRecentResultsFromSystemStatus", body)
        self.assertIn("systemStatus?.recent_results", body)
        self.assertIn("state.currentResult = recentResults.current;", body)
        self.assertIn("state.baselineResult = recentResults.baseline;", body)
        self.assertIn('document.getElementById("operatorCueShell")', body)
        self.assertIn("systemStatus.operator_cue", body)
        self.assertIn("buildCommandCenterModel", body)
        self.assertIn("resolveWeakNetworkSelection", body)
        self.assertIn("jumpToTarget", body)
        self.assertIn("focusMissionPasswordInput", body)
        self.assertIn("renderMissionPasswordInline", body)
        self.assertIn('document.getElementById("missionPasswordInput")', body)
        self.assertIn("renderMissionCurrentLaunch", body)
        self.assertIn("currentMissionProgressState", body)
        self.assertIn('document.getElementById("missionRunCurrentButton")', body)
        self.assertIn('badgeId: "missionCurrentProgressBadge"', body)
        self.assertIn('stageId: "missionCurrentProgressStage"', body)
        self.assertIn("submitBoardAccess", body)
        self.assertIn("saveMissionPassword", body)
        self.assertIn('document.getElementById("missionCoreCard")', body)
        self.assertIn('document.getElementById("weakNetworkConsole")', body)
        self.assertIn('document.getElementById("comparePeekCard")', body)
        self.assertIn("data-jump-target", body)
        self.assertIn("data-open-drawer", body)
        self.assertIn("data-weak-scenario-id", body)
        self.assertIn("effectiveSafetyPanel", body)
        self.assertIn("renderSafetyFrontPanel", body)
        self.assertIn("systemStatus.safety_panel", body)
        self.assertIn('"/api/recover"', body)
        self.assertIn("selectedCompareViewerSample", body)
        self.assertIn("originalGallerySummary", body)
        self.assertIn("original_gallery", body)
        self.assertIn('document.getElementById("compareViewerBoard")', body)
        self.assertIn("baselineLiveDisplayLabel", body)
        self.assertIn("PyTorch reference archive", body)
        self.assertIn("PyTorch signed live", body)
        self.assertNotIn("去 Session / Gate 填密码", body)

    def test_app_js_keeps_homepage_current_launch_on_home_surface(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, _, body = request_text(state, "GET", "/app.js")

        self.assertEqual(status, 200)
        self.assertIn("async function runCurrentInferenceFromHomepage()", body)
        self.assertIn("runCurrentInference({ switchActOptions: { openDrawer: false, user: false } });", body)
        self.assertIn("if (options.openDrawer === false) {", body)
        self.assertIn("switchAct(actId, switchActOptions);", body)
        self.assertIn("runCurrentInferenceFromHomepage();", body)

    def test_app_css_serves_dashboard_stylesheet(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)

        status, headers, body = request_text(state, "GET", "/app.css")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/css; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIn(":root {", body)
        self.assertIn("--accent: #59d8ff;", body)
        self.assertIn(".cockpit-shell", body)
        self.assertIn(".flight-stage", body)
        self.assertIn(".details-drawer", body)
        self.assertIn(".aircraft-vector", body)
        self.assertIn(".cockpit-signal-strip", body)
        self.assertIn(".flight-stage-sweep", body)
        self.assertIn(".operator-cue-shell", body)
        self.assertIn(".weak-console-metrics", body)
        self.assertIn(
            ".mission-stage-panel {\n"
            "  grid-template-rows: auto minmax(0, 1fr) auto auto;\n"
            "  overflow-y: auto;\n"
            "  overflow-x: hidden;\n"
            "}",
            body,
        )

    def test_docs_endpoint_renders_repo_relative_markdown_document(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        doc_path = "session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md"
        expected_line = (REPO_ROOT / doc_path).read_text(encoding="utf-8").splitlines()[0]

        status, headers, body = request_text(state, "GET", f"/docs?path={quote(doc_path, safe='')}")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/html; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIn(f"<title>{doc_path}</title>", body)
        self.assertIn(f'<div class="path">{doc_path}</div>', body)
        self.assertIn(html.escape(expected_line), body)

    def test_docs_endpoint_rejects_missing_invalid_and_missing_file_paths(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        cases = (
            ("/docs", 400, "missing path"),
            (f"/docs?path={quote('/etc/passwd', safe='')}", 400, "invalid path"),
            ("/docs?path=session_bootstrap/demo/openamp_control_plane_demo/not-real.md", 404, "file not found"),
        )

        for request_path, expected_status, expected_message in cases:
            with self.subTest(request_path=request_path):
                status, headers, body = request_text(state, "GET", request_path)
                self.assertEqual(status, expected_status)
                self.assertTrue(headers["content-type"].startswith("text/html"))
                self.assertEqual(headers["cache-control"], "no-store")
                self.assertIn(expected_message, body)

    def test_docs_endpoint_pretty_prints_json_documents(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        doc_path = "session_bootstrap/reports/openamp_input_contract_fit_20260315_014542/fit_summary.json"
        raw_json = (REPO_ROOT / doc_path).read_text(encoding="utf-8")
        expected_json = html.escape(json.dumps(json.loads(raw_json), ensure_ascii=False, indent=2))

        status, headers, body = request_text(state, "GET", f"/docs?path={quote(doc_path, safe='')}")

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/html; charset=utf-8")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIn(f'<div class="path">{doc_path}</div>', body)
        self.assertIn(expected_json, body)


class DemoHTTPServerSocketSmokeTest(unittest.TestCase):
    def test_health_endpoint_smoke_via_real_localhost_socket(self) -> None:
        state = DashboardState(None, 30.0, probe_cache_path=None)
        try:
            http_server = server.DemoHTTPServer(("127.0.0.1", 0), DemoRequestHandler, state)
        except PermissionError as exc:
            self.skipTest(f"Local socket binding is not permitted in this runtime: {exc}")

        server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        server_thread.start()

        try:
            host, port = http_server.server_address
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f"http://{host}:{port}/api/health", timeout=2) as response:
                status = response.status
                headers = dict(response.headers.items())
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            http_server.shutdown()
            http_server.server_close()
            server_thread.join(timeout=2)

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(payload, {"status": "ok"})
        self.assertFalse(server_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
