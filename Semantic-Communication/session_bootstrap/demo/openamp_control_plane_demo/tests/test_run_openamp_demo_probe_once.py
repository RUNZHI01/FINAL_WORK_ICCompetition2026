from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEMO_ROOT.parents[2]
HELPER = REPO_ROOT / "session_bootstrap" / "scripts" / "run_openamp_demo_probe_once.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


class OpenAMPDemoProbeOnceTest(unittest.TestCase):
    def build_mock_runtime(self, temp_dir: Path) -> tuple[dict[str, str], Path, Path, Path]:
        launcher_path = temp_dir / "mock_launcher.sh"
        python_path = temp_dir / "mock_python.py"
        args_log_path = temp_dir / "launcher.args.log"
        password_log_path = temp_dir / "launcher.password.log"
        term_log_path = temp_dir / "launcher.term.log"

        write_executable(
            python_path,
            """\
            #!/usr/bin/env python3
            from __future__ import annotations

            import json
            from pathlib import Path
            import subprocess
            import sys
            import tempfile
            import os

            if len(sys.argv) >= 2 and sys.argv[1] == "-":
                script = sys.stdin.read()
                args = sys.argv[2:]
            else:
                script = ""
                args = sys.argv[1:]

            SYSTEM_STATUS = {
                "execution_mode": {"label": "在线模式"},
                "board_access": {
                    "connection_ready": True,
                    "missing_connection_fields": [],
                },
            }
            SNAPSHOT = {
                "mode": {"effective_label": "在线读数可用"},
                "board": {
                    "current_status": {
                        "label": "保存的只读 SSH 探板",
                        "summary": "该结果来自上一次成功探板的保存记录。",
                    },
                },
                "latest_live_status": {"valid_instance": "8115"},
            }
            PROBE_BOARD = {
                "status": "error",
                "reachable": False,
                "summary": "板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。",
                "error": "板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。",
            }

            if 'base + "/api/health"' in script and len(args) == 1:
                raise SystemExit(0)

            if 'base.rstrip("/") + path' in script and len(args) == 6:
                _, path, output_path, method, timeout_sec, allow_error_payload = args
                if path == "/api/health":
                    payload = {"status": "ok"}
                elif path == "/api/system-status":
                    payload = SYSTEM_STATUS
                elif path == "/api/snapshot":
                    payload = SNAPSHOT
                elif path == "/api/probe-board":
                    payload = PROBE_BOARD
                else:
                    raise SystemExit(f"unsupported path: {path}")
                Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
                raise SystemExit(0)

            real_python = os.environ["REAL_PYTHON_BIN"]
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                handle.write(script)
                script_path = handle.name
            try:
                completed = subprocess.run([real_python, script_path, *args], check=False)
            finally:
                Path(script_path).unlink(missing_ok=True)
            raise SystemExit(completed.returncode)
            """,
        )

        write_executable(
            launcher_path,
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            host="127.0.0.1"
            port="8079"
            printf '%s\\n' "$*" > "${MOCK_LAUNCHER_ARGS_LOG:?}"
            printf '%s\\n' "${REMOTE_PASS:-}" > "${MOCK_LAUNCHER_PASSWORD_LOG:?}"
            trap 'printf "terminated\\n" > "${MOCK_LAUNCHER_TERM_LOG:?}"; exit 0' TERM INT

            while (($#)); do
                case "$1" in
                    --host)
                        host="${2:?missing value for --host}"
                        shift 2
                        ;;
                    --host=*)
                        host="${1#*=}"
                        shift
                        ;;
                    --port)
                        port="${2:?missing value for --port}"
                        shift 2
                        ;;
                    --port=*)
                        port="${1#*=}"
                        shift
                        ;;
                    *)
                        shift
                        ;;
                esac
            done

            while true; do
                sleep 1
            done
            """,
        )

        env = os.environ.copy()
        env.update(
            {
                "OPENAMP_DEMO_PROBE_ONCE_LAUNCHER": str(launcher_path),
                "OPENAMP_DEMO_PROBE_ONCE_PYTHON": str(python_path),
                "OPENAMP_DEMO_PROBE_ONCE_WAIT_STEPS": "20",
                "OPENAMP_DEMO_PROBE_ONCE_WAIT_SEC": "0.1",
                "MOCK_LAUNCHER_ARGS_LOG": str(args_log_path),
                "MOCK_LAUNCHER_PASSWORD_LOG": str(password_log_path),
                "MOCK_LAUNCHER_TERM_LOG": str(term_log_path),
                "REAL_PYTHON_BIN": os.environ.get("PYTHON", "python3"),
            }
        )
        return env, args_log_path, password_log_path, term_log_path

    def test_probe_once_captures_summary_and_stops_demo(self) -> None:
        password = "demo-pass"
        port = 18090

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            output_dir = temp_dir / "capture"
            env, args_log_path, password_log_path, term_log_path = self.build_mock_runtime(temp_dir)

            result = subprocess.run(
                [
                    "bash",
                    str(HELPER),
                    "--password",
                    password,
                    "--output-dir",
                    str(output_dir),
                    "--port",
                    str(port),
                    "--probe-env",
                    "./session_bootstrap/config/phytium_pi_login.example.env",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output_dir / "api_health.json").is_file())
            self.assertTrue((output_dir / "api_system_status.json").is_file())
            self.assertTrue((output_dir / "api_snapshot.json").is_file())
            self.assertFalse((output_dir / "api_probe_board.json").exists())
            self.assertTrue((output_dir / "summary.json").is_file())

            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["execution_mode"], "在线模式")
            self.assertTrue(summary["connection_ready"])
            self.assertEqual(summary["missing_connection_fields"], [])
            self.assertEqual(summary["mode_effective_label"], "在线读数可用")
            self.assertEqual(summary["board_current_status_label"], "保存的只读 SSH 探板")
            self.assertEqual(summary["valid_instance"], "8115")
            self.assertFalse(summary["fresh_probe_visible"])
            self.assertIn("saved probe record", summary["startup_probe_note"])

            launcher_args = args_log_path.read_text(encoding="utf-8").strip()
            self.assertIn("--probe-startup", launcher_args)
            self.assertIn(f"--port {port}", launcher_args)
            self.assertIn("--probe-env ./session_bootstrap/config/phytium_pi_login.example.env", launcher_args)
            self.assertEqual(password_log_path.read_text(encoding="utf-8").strip(), password)

            self.assertIn("execution_mode: 在线模式", result.stdout)
            self.assertIn("mode.effective_label: 在线读数可用", result.stdout)
            self.assertIn("board.current_status.label: 保存的只读 SSH 探板", result.stdout)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertEqual(term_log_path.read_text(encoding="utf-8").strip(), "terminated")

    def test_probe_once_prompt_password_reads_stdin_without_echo(self) -> None:
        password = "prompt-pass"
        port = 18091

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            output_dir = temp_dir / "capture"
            env, _, password_log_path, term_log_path = self.build_mock_runtime(temp_dir)

            result = subprocess.run(
                [
                    "bash",
                    str(HELPER),
                    "--prompt-password",
                    "--output-dir",
                    str(output_dir),
                    "--port",
                    str(port),
                ],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(password_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertEqual(term_log_path.read_text(encoding="utf-8").strip(), "terminated")

    def test_probe_once_post_probe_board_captures_probe_result(self) -> None:
        password = "prompt-pass"
        port = 18092

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            output_dir = temp_dir / "capture"
            env, _, password_log_path, term_log_path = self.build_mock_runtime(temp_dir)

            result = subprocess.run(
                [
                    "bash",
                    str(HELPER),
                    "--prompt-password",
                    "--post-probe-board",
                    "--output-dir",
                    str(output_dir),
                    "--port",
                    str(port),
                ],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output_dir / "api_probe_board.json").is_file())
            probe_board = json.loads((output_dir / "api_probe_board.json").read_text(encoding="utf-8"))
            self.assertEqual(probe_board["status"], "error")
            self.assertFalse(probe_board["reachable"])
            self.assertIn("SSH 认证失败", probe_board["summary"])
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["probe_board_requested"])
            self.assertEqual(summary["probe_board_status"], "error")
            self.assertFalse(summary["probe_board_reachable"])
            self.assertIn("SSH 认证失败", summary["probe_board_summary"])
            self.assertEqual(password_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertEqual(term_log_path.read_text(encoding="utf-8").strip(), "terminated")

    def test_probe_once_strict_probe_board_exits_nonzero_on_probe_failure(self) -> None:
        password = "prompt-pass"
        port = 18093

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            output_dir = temp_dir / "capture"
            env, _, password_log_path, term_log_path = self.build_mock_runtime(temp_dir)

            result = subprocess.run(
                [
                    "bash",
                    str(HELPER),
                    "--prompt-password",
                    "--strict-probe-board",
                    "--output-dir",
                    str(output_dir),
                    "--port",
                    str(port),
                ],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue((output_dir / "api_probe_board.json").is_file())
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["probe_board_requested"])
            self.assertEqual(summary["probe_board_status"], "error")
            self.assertIn("SSH 认证失败", summary["probe_board_summary"])
            self.assertIn("strict probe-board mode", result.stderr)
            self.assertEqual(password_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertEqual(term_log_path.read_text(encoding="utf-8").strip(), "terminated")


if __name__ == "__main__":
    unittest.main()
