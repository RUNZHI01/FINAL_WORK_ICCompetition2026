from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEMO_ROOT.parents[2]
LAUNCHER = REPO_ROOT / "session_bootstrap" / "scripts" / "run_openamp_demo.sh"
SERVER = REPO_ROOT / "session_bootstrap" / "demo" / "openamp_control_plane_demo" / "server.py"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


class OpenAMPDemoLauncherTest(unittest.TestCase):
    def build_mock_env(
        self,
        temp_dir: Path,
        ss_outputs: list[str],
        ps_outputs: list[str],
        lsof_outputs: list[str],
    ) -> tuple[dict[str, str], Path, Path]:
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()

        ss_call_count_path = temp_dir / "ss.calls"
        ps_call_count_path = temp_dir / "ps.calls"
        lsof_call_count_path = temp_dir / "lsof.calls"
        python_log_path = temp_dir / "python.log"
        python_password_env_log_path = temp_dir / "python.password.log"
        kill_log_path = temp_dir / "kill.log"
        bash_env_path = temp_dir / "bash_env.sh"
        ss_output_dir = temp_dir / "ss"
        ps_output_dir = temp_dir / "ps"
        lsof_output_dir = temp_dir / "lsof"
        ss_output_dir.mkdir()
        ps_output_dir.mkdir()
        lsof_output_dir.mkdir()

        for index, output in enumerate(ss_outputs):
            (ss_output_dir / f"{index}.txt").write_text(output, encoding="utf-8")
        for index, output in enumerate(ps_outputs):
            (ps_output_dir / f"{index}.txt").write_text(output, encoding="utf-8")
        for index, output in enumerate(lsof_outputs):
            (lsof_output_dir / f"{index}.txt").write_text(output, encoding="utf-8")

        write_executable(
            bin_dir / "ss",
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                call_count=0
                if [[ -f "${MOCK_SS_CALL_COUNT_FILE}" ]]; then
                    call_count="$(cat "${MOCK_SS_CALL_COUNT_FILE}")"
                fi
                output_index="${call_count}"
                if (( output_index >= MOCK_SS_OUTPUT_COUNT )); then
                    output_index=$((MOCK_SS_OUTPUT_COUNT - 1))
                fi
                printf '%s' "$((call_count + 1))" > "${MOCK_SS_CALL_COUNT_FILE}"
                cat "${MOCK_SS_OUTPUT_DIR}/${output_index}.txt"
                """
            ),
        )
        write_executable(
            bin_dir / "ps",
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                if [[ "${1:-}" == "-eo" && "${2:-}" == "pid=,args=" ]]; then
                    call_count=0
                    if [[ -f "${MOCK_PS_CALL_COUNT_FILE}" ]]; then
                        call_count="$(cat "${MOCK_PS_CALL_COUNT_FILE}")"
                    fi
                    output_index="${call_count}"
                    if (( output_index >= MOCK_PS_OUTPUT_COUNT )); then
                        output_index=$((MOCK_PS_OUTPUT_COUNT - 1))
                    fi
                    printf '%s' "$((call_count + 1))" > "${MOCK_PS_CALL_COUNT_FILE}"
                    cat "${MOCK_PS_OUTPUT_DIR}/${output_index}.txt"
                    exit 0
                fi
                printf 'unexpected ps invocation: %s\n' "$*" >&2
                exit 1
                """
            ),
        )
        write_executable(
            bin_dir / "lsof",
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                call_count=0
                if [[ -f "${MOCK_LSOF_CALL_COUNT_FILE}" ]]; then
                    call_count="$(cat "${MOCK_LSOF_CALL_COUNT_FILE}")"
                fi
                output_index="${call_count}"
                if (( output_index >= MOCK_LSOF_OUTPUT_COUNT )); then
                    output_index=$((MOCK_LSOF_OUTPUT_COUNT - 1))
                fi
                printf '%s' "$((call_count + 1))" > "${MOCK_LSOF_CALL_COUNT_FILE}"
                cat "${MOCK_LSOF_OUTPUT_DIR}/${output_index}.txt"
                """
            ),
        )
        bash_env_path.write_text(
            textwrap.dedent(
                """\
                kill() {
                    printf '%s\n' "$*" >> "${MOCK_KILL_LOG_FILE}"
                    return 0
                }

                sleep() {
                    return 0
                }
                """
            ),
            encoding="utf-8",
        )
        write_executable(
            bin_dir / "python3",
            textwrap.dedent(
                """\
                #!/bin/sh
                set -eu
                printf '%s\n' "$*" > "${MOCK_PYTHON_LOG_FILE}"
                if [ -n "${OPENAMP_DEMO_READINESS_PASSWORD:-}" ]; then
                    printf '%s\n' "${OPENAMP_DEMO_READINESS_PASSWORD}" > "${MOCK_PYTHON_PASSWORD_ENV_LOG_FILE}"
                elif [ -n "${REMOTE_PASS:-}" ]; then
                    printf '%s\n' "${REMOTE_PASS}" > "${MOCK_PYTHON_PASSWORD_ENV_LOG_FILE}"
                fi
                exit 0
                """
            ),
        )

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                "BASH_ENV": str(bash_env_path),
                "MOCK_SS_OUTPUT_COUNT": str(len(ss_outputs)),
                "MOCK_SS_OUTPUT_DIR": str(ss_output_dir),
                "MOCK_SS_CALL_COUNT_FILE": str(ss_call_count_path),
                "MOCK_PS_OUTPUT_COUNT": str(len(ps_outputs)),
                "MOCK_PS_OUTPUT_DIR": str(ps_output_dir),
                "MOCK_PS_CALL_COUNT_FILE": str(ps_call_count_path),
                "MOCK_LSOF_OUTPUT_COUNT": str(len(lsof_outputs)),
                "MOCK_LSOF_OUTPUT_DIR": str(lsof_output_dir),
                "MOCK_LSOF_CALL_COUNT_FILE": str(lsof_call_count_path),
                "MOCK_KILL_LOG_FILE": str(kill_log_path),
                "MOCK_PYTHON_LOG_FILE": str(python_log_path),
                "MOCK_PYTHON_PASSWORD_ENV_LOG_FILE": str(python_password_env_log_path),
            }
        )
        return env, python_log_path, python_password_env_log_path, kill_log_path

    def test_reclaims_existing_demo_server_listener_before_restart(self) -> None:
        port = "8090"
        fake_pid = "999999"
        ss_outputs = [f"LISTEN 0 5 127.0.0.1:{port} 0.0.0.0:*\n", ""]
        ps_outputs = [f"{fake_pid} python3 {SERVER} --port {port}\n"]
        lsof_outputs = [f"p{fake_pid}\nn127.0.0.1:{port}\n", ""]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, _, kill_log_path = self.build_mock_env(temp_dir, ss_outputs, ps_outputs, lsof_outputs)

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--port", port],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Reclaiming port {port} from existing OpenAMP demo server PID {fake_pid} with TERM.", result.stderr)
            self.assertEqual(kill_log_path.read_text(encoding="utf-8").strip(), f"-TERM {fake_pid}")
            self.assertEqual(python_log_path.read_text(encoding="utf-8").strip(), f"{SERVER} --port {port}")

    def test_refuses_to_kill_non_demo_listener_on_requested_port(self) -> None:
        port = "8091"
        ss_outputs = [f"LISTEN 0 5 127.0.0.1:{port} 0.0.0.0:*\n"]
        lsof_outputs = [f"p555555\nn127.0.0.1:{port}\n"]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, _, kill_log_path = self.build_mock_env(temp_dir, ss_outputs, [""], lsof_outputs)

            result = subprocess.run(
                ["bash", str(LAUNCHER), f"--port={port}"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"Requested OpenAMP demo port {port} is already in use", result.stderr)
            self.assertIn("Refusing to stop a non-OpenAMP listener.", result.stderr)
            self.assertFalse(python_log_path.exists())
            self.assertFalse(kill_log_path.exists())

    def test_escalates_to_kill_when_demo_listener_survives_term_grace(self) -> None:
        port = "8092"
        fake_pid = "777777"
        ss_outputs = [f"LISTEN 0 5 127.0.0.1:{port} 0.0.0.0:*\n"] * 12 + [""]
        ps_outputs = [f"{fake_pid} python3 {SERVER} --port {port}\n"]
        lsof_outputs = [f"p{fake_pid}\nn127.0.0.1:{port}\n"] * 12 + [""]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, _, kill_log_path = self.build_mock_env(temp_dir, ss_outputs, ps_outputs, lsof_outputs)

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--port", port],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Reclaiming port {port} from existing OpenAMP demo server PID {fake_pid} with TERM.", result.stderr)
            self.assertIn(
                f"Existing OpenAMP demo server PID(s) {fake_pid} still hold port {port} after TERM grace period",
                result.stderr,
            )
            self.assertIn(
                f"Escalating reclaim of port {port} to KILL for existing OpenAMP demo server PID {fake_pid}.",
                result.stderr,
            )
            self.assertEqual(kill_log_path.read_text(encoding="utf-8").splitlines(), [f"-TERM {fake_pid}", f"-KILL {fake_pid}"])
            self.assertEqual(python_log_path.read_text(encoding="utf-8").strip(), f"{SERVER} --port {port}")

    def test_check_readiness_still_execs_checker_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, python_password_env_log_path, kill_log_path = self.build_mock_env(temp_dir, [""], [""], [""])

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--check-readiness", "--readiness-format", "json", "--host", "10.0.0.8"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                python_log_path.read_text(encoding="utf-8").strip(),
                f"{REPO_ROOT / 'session_bootstrap' / 'scripts' / 'check_openamp_demo_session_readiness.py'} --format json --host 10.0.0.8",
            )
            self.assertFalse(python_password_env_log_path.exists())
            self.assertFalse(kill_log_path.exists())

    def test_check_readiness_prompt_password_reads_from_stdin_without_exposing_password(self) -> None:
        password = "demo-pass"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, python_password_env_log_path, kill_log_path = self.build_mock_env(temp_dir, [""], [""], [""])

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--check-readiness-prompt-password", "--readiness-format", "text"],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                python_log_path.read_text(encoding="utf-8").strip(),
                f"{REPO_ROOT / 'session_bootstrap' / 'scripts' / 'check_openamp_demo_session_readiness.py'} --format text",
            )
            self.assertEqual(python_password_env_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertNotIn(password, python_log_path.read_text(encoding="utf-8"))
            self.assertFalse(kill_log_path.exists())

    def test_prompt_password_launches_server_with_runtime_password_env_without_echo(self) -> None:
        password = "demo-pass"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, python_password_env_log_path, kill_log_path = self.build_mock_env(temp_dir, [""], [""], [""])

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--prompt-password", "--port", "8093"],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                python_log_path.read_text(encoding="utf-8").strip(),
                f"{SERVER} --port 8093",
            )
            self.assertEqual(python_password_env_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertFalse(kill_log_path.exists())

    def test_prompt_password_keeps_probe_startup_arg_when_launching_server(self) -> None:
        password = "demo-pass"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, python_password_env_log_path, kill_log_path = self.build_mock_env(temp_dir, [""], [""], [""])

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--prompt-password", "--probe-startup", "--port", "8094"],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                python_log_path.read_text(encoding="utf-8").strip(),
                f"{SERVER} --probe-startup --port 8094",
            )
            self.assertEqual(python_password_env_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertFalse(kill_log_path.exists())

    def test_prompt_password_probe_startup_alias_launches_server(self) -> None:
        password = "demo-pass"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env, python_log_path, python_password_env_log_path, kill_log_path = self.build_mock_env(temp_dir, [""], [""], [""])

            result = subprocess.run(
                ["bash", str(LAUNCHER), "--prompt-password-probe-startup", "--port", "8095"],
                cwd=REPO_ROOT,
                env=env,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                python_log_path.read_text(encoding="utf-8").strip(),
                f"{SERVER} --probe-startup --port 8095",
            )
            self.assertEqual(python_password_env_log_path.read_text(encoding="utf-8").strip(), password)
            self.assertNotIn(password, result.stdout)
            self.assertNotIn(password, result.stderr)
            self.assertFalse(kill_log_path.exists())


if __name__ == "__main__":
    unittest.main()
