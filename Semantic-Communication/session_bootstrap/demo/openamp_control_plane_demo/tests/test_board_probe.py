from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from board_probe import (  # noqa: E402
    CONNECT_SCRIPT,
    PROJECT_ROOT,
    REMOTE_PROBE_CODE,
    SSH_WITH_PASSWORD_SCRIPT,
    build_probe_command,
    load_probe_output,
    run_live_probe,
    write_probe_output,
)


EXPECTED_REMOTE_COMMAND = f"python3 -c {shlex.quote(REMOTE_PROBE_CODE)}"


class BuildProbeCommandTest(unittest.TestCase):
    def write_env(self, content: str, *, relative: bool = False) -> str:
        temp_dir = tempfile.TemporaryDirectory(dir=PROJECT_ROOT)
        self.addCleanup(temp_dir.cleanup)
        env_path = Path(temp_dir.name) / "probe.env"
        env_path.write_text(content, encoding="utf-8")
        if relative:
            return str(env_path.relative_to(PROJECT_ROOT))
        return str(env_path)

    def test_password_env_uses_ssh_with_password_script_with_default_port(self) -> None:
        env_file = self.write_env(
            "\n".join(
                [
                    "REMOTE_HOST=demo-board",
                    "REMOTE_USER=demo-user",
                    "REMOTE_PASS=demo-pass",
                ]
            ),
            relative=True,
        )

        command = build_probe_command(env_file)

        self.assertEqual(
            command,
            [
                "bash",
                str(SSH_WITH_PASSWORD_SCRIPT),
                "--host",
                "demo-board",
                "--user",
                "demo-user",
                "--pass",
                "demo-pass",
                "--port",
                "22",
                "--",
                EXPECTED_REMOTE_COMMAND,
            ],
        )

    def test_password_env_honors_remote_ssh_port_override(self) -> None:
        env_file = self.write_env(
            "\n".join(
                [
                    "REMOTE_HOST=demo-board",
                    "REMOTE_USER=demo-user",
                    "REMOTE_PASS=demo-pass",
                    "REMOTE_SSH_PORT=2202",
                ]
            )
        )

        command = build_probe_command(env_file)

        self.assertEqual(
            command,
            [
                "bash",
                str(SSH_WITH_PASSWORD_SCRIPT),
                "--host",
                "demo-board",
                "--user",
                "demo-user",
                "--pass",
                "demo-pass",
                "--port",
                "2202",
                "--",
                EXPECTED_REMOTE_COMMAND,
            ],
        )

    def test_missing_password_auth_vars_falls_back_to_connect_script_with_env(self) -> None:
        env_file = self.write_env(
            "\n".join(
                [
                    "REMOTE_HOST=demo-board",
                    "REMOTE_USER=demo-user",
                ]
            ),
            relative=True,
        )

        command = build_probe_command(env_file)

        self.assertEqual(
            command,
            [
                "bash",
                str(CONNECT_SCRIPT),
                "--env",
                env_file,
                "--",
                EXPECTED_REMOTE_COMMAND,
            ],
        )


class LoadWriteProbeOutputTest(unittest.TestCase):
    def make_probe_path(self, *, relative: bool = False) -> str:
        temp_dir = tempfile.TemporaryDirectory(dir=PROJECT_ROOT)
        self.addCleanup(temp_dir.cleanup)
        probe_path = Path(temp_dir.name) / "cache" / "probe.json"
        if relative:
            return str(probe_path.relative_to(PROJECT_ROOT))
        return str(probe_path)

    def test_write_probe_output_writes_json_to_target_path(self) -> None:
        payload = {
            "requested_at": "2026-03-15T13:00:00+0800",
            "reachable": True,
            "status": "success",
            "details": {"hostname": "demo-board"},
        }
        output_path = Path(self.make_probe_path())

        write_probe_output(payload, output_path)

        self.assertTrue(output_path.exists())
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), payload)
        self.assertTrue(output_path.read_text(encoding="utf-8").endswith("\n"))

    def test_load_probe_output_reads_valid_json_from_relative_path(self) -> None:
        payload = {
            "requested_at": "2026-03-15T13:05:00+0800",
            "reachable": True,
            "status": "success",
        }
        output_path = self.make_probe_path(relative=True)

        write_probe_output(payload, output_path)

        self.assertEqual(load_probe_output(output_path), payload)

    def test_load_probe_output_returns_none_for_missing_file(self) -> None:
        output_path = self.make_probe_path(relative=True)

        self.assertIsNone(load_probe_output(output_path))

    def test_load_probe_output_returns_none_for_malformed_json(self) -> None:
        output_path = Path(self.make_probe_path())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{not-json\n", encoding="utf-8")

        self.assertIsNone(load_probe_output(output_path))

    def test_load_probe_output_returns_none_for_valid_non_dict_json(self) -> None:
        output_path = Path(self.make_probe_path())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(["reachable", True]), encoding="utf-8")

        self.assertIsNone(load_probe_output(output_path))

    def test_write_probe_output_propagates_write_failures(self) -> None:
        payload = {
            "requested_at": "2026-03-15T13:10:00+0800",
            "reachable": True,
            "status": "success",
        }
        expected_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        resolved_path = Mock()
        resolved_path.parent = Mock()
        resolved_path.write_text.side_effect = OSError("disk full")

        with (
            patch("board_probe.resolve_project_path", return_value=resolved_path) as resolve_path,
            self.assertRaisesRegex(OSError, "disk full"),
        ):
            write_probe_output(payload, "session_bootstrap/reports/openamp_demo_live_probe_latest.json")

        resolve_path.assert_called_once_with(
            "session_bootstrap/reports/openamp_demo_live_probe_latest.json"
        )
        resolved_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        resolved_path.write_text.assert_called_once_with(expected_text, encoding="utf-8")


class RunLiveProbeTest(unittest.TestCase):
    def test_success_payload_shaping_from_valid_json_stdout(self) -> None:
        command = ["bash", "fake-connect"]
        details = {
            "hostname": "phytium-demo",
            "remoteproc": [
                {"name": "remoteproc0", "state": "running"},
                {"name": "remoteproc1", "state": "offline"},
            ],
            "rpmsg_devices": ["/dev/rpmsg0", "/dev/rpmsg1"],
            "firmware": {"sha256": "abcdef1234567890fedcba"},
        }
        completed = subprocess.CompletedProcess(
            command,
            0,
            stdout="ssh banner\n" + json.dumps(details) + "\n",
            stderr="",
        )

        with (
            patch("board_probe.now_iso", return_value="2026-03-15T12:00:00+0800"),
            patch("board_probe.build_probe_command", return_value=command) as build_command,
            patch("board_probe.subprocess.run", return_value=completed) as run_mock,
        ):
            payload = run_live_probe(env_file="demo.env", timeout_sec=12.5)

        build_command.assert_called_once_with("demo.env")
        run_mock.assert_called_once_with(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=12.5,
        )
        self.assertEqual(
            payload,
            {
                "requested_at": "2026-03-15T12:00:00+0800",
                "reachable": True,
                "status": "success",
                "status_category": "success",
                "summary": "phytium-demo reachable; remoteproc0=running, remoteproc1=offline; 2 rpmsg device(s); firmware abcdef123456.",
                "error": "",
                "details": details,
                "diagnostics": {},
            },
        )

    def test_timeout_returns_timeout_payload(self) -> None:
        command = ["bash", "fake-connect"]

        with (
            patch("board_probe.now_iso", return_value="2026-03-15T12:05:00+0800"),
            patch("board_probe.build_probe_command", return_value=command) as build_command,
            patch(
                "board_probe.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=command, timeout=3.0),
            ) as run_mock,
        ):
            payload = run_live_probe(timeout_sec=3.0)

        build_command.assert_called_once_with(None)
        run_mock.assert_called_once_with(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=3.0,
        )
        self.assertEqual(
            payload,
            {
                "requested_at": "2026-03-15T12:05:00+0800",
                "reachable": False,
                "status": "timeout",
                "status_category": "timeout",
                "summary": "板卡探测超时，请确认板卡在线后重试。",
                "error": "板卡探测超时，请确认板卡在线后重试。",
                "details": {},
                "diagnostics": {},
            },
        )

    def test_command_launch_failure_returns_error_payload(self) -> None:
        env_file = "session_bootstrap/demo/openamp_control_plane_demo/tests/missing-probe.env"

        with patch("board_probe.now_iso", return_value="2026-03-15T12:07:00+0800"):
            payload = run_live_probe(env_file=env_file, timeout_sec=4.0)

        self.assertEqual(
            payload,
            {
                "requested_at": "2026-03-15T12:07:00+0800",
                "reachable": False,
                "status": "launch_error",
                "status_category": "config_error",
                "summary": "板卡探测配置不可用，请检查环境文件、主机和端口设置。",
                "error": "板卡探测配置不可用，请检查环境文件、主机和端口设置。",
                "details": {},
                "diagnostics": {"error": f"[Errno 2] No such file or directory: '{PROJECT_ROOT / env_file}'"},
            },
        )

    def test_non_zero_exit_returns_error_payload(self) -> None:
        command = ["bash", "fake-connect"]
        completed = subprocess.CompletedProcess(
            command,
            7,
            stdout="transient stdout\n",
            stderr="permission denied\n",
        )

        with (
            patch("board_probe.now_iso", return_value="2026-03-15T12:10:00+0800"),
            patch("board_probe.build_probe_command", return_value=command) as build_command,
            patch("board_probe.subprocess.run", return_value=completed) as run_mock,
        ):
            payload = run_live_probe(timeout_sec=9.0)

        build_command.assert_called_once_with(None)
        run_mock.assert_called_once_with(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=9.0,
        )
        self.assertEqual(
            payload,
            {
                "requested_at": "2026-03-15T12:10:00+0800",
                "reachable": False,
                "status": "error",
                "status_category": "auth_error",
                "summary": "板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。",
                "error": "板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。",
                "details": {},
                "diagnostics": {"stdout": "transient stdout", "stderr": "permission denied", "returncode": 7},
            },
        )

    def test_socket_block_returns_host_env_error_payload(self) -> None:
        command = ["bash", "fake-connect"]
        completed = subprocess.CompletedProcess(
            command,
            255,
            stdout="",
            stderr="socket: Operation not permitted\nssh: connect to host demo-board port 22: failure\n",
        )

        with (
            patch("board_probe.now_iso", return_value="2026-03-15T12:11:00+0800"),
            patch("board_probe.build_probe_command", return_value=command),
            patch("board_probe.subprocess.run", return_value=completed),
        ):
            payload = run_live_probe(timeout_sec=9.0)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["status_category"], "host_env_error")
        self.assertIn("当前主机环境禁止建立 SSH socket", payload["summary"])
        self.assertNotIn("权限不足", payload["summary"])
        self.assertEqual(
            payload["diagnostics"],
            {
                "stderr": "socket: Operation not permitted\nssh: connect to host demo-board port 22: failure",
                "returncode": 255,
            },
        )

    def test_invalid_json_stdout_returns_parse_error_payload(self) -> None:
        command = ["bash", "fake-connect"]
        completed = subprocess.CompletedProcess(
            command,
            0,
            stdout="ssh banner\nnot-json\n",
            stderr="stderr line\n",
        )

        with (
            patch("board_probe.now_iso", return_value="2026-03-15T12:15:00+0800"),
            patch("board_probe.build_probe_command", return_value=command) as build_command,
            patch("board_probe.subprocess.run", return_value=completed) as run_mock,
        ):
            payload = run_live_probe(timeout_sec=6.0)

        build_command.assert_called_once_with(None)
        run_mock.assert_called_once_with(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=6.0,
        )
        self.assertEqual(payload["requested_at"], "2026-03-15T12:15:00+0800")
        self.assertFalse(payload["reachable"])
        self.assertEqual(payload["status"], "parse_error")
        self.assertEqual(payload["status_category"], "error")
        self.assertEqual(
            payload["summary"],
            "板卡探测失败，请查看诊断信息。",
        )
        self.assertEqual(payload["error"], "板卡探测失败，请查看诊断信息。")
        self.assertEqual(
            payload["details"],
            {"stdout": "ssh banner\nnot-json", "stderr": "stderr line"},
        )
        self.assertEqual(
            payload["diagnostics"],
            {
                "stdout": "ssh banner\nnot-json",
                "stderr": "stderr line",
                "error": "Expecting value: line 1 column 1 (char 0)",
            },
        )


if __name__ == "__main__":
    unittest.main()
