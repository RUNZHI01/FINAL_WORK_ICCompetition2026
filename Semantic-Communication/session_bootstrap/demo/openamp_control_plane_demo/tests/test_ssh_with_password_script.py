from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SESSION_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = SESSION_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from openamp_control_wrapper import resolve_bash_executable  # noqa: E402


SSH_HELPER = SCRIPTS_ROOT / "ssh_with_password.sh"


def bash_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        drive = resolved.drive.rstrip(":").lower()
        return f"/{drive}{resolved.as_posix()[2:]}"
    return str(resolved)


class SshWithPasswordScriptTest(unittest.TestCase):
    def test_paramiko_runner_uses_python_helper_and_preserves_stdin(self) -> None:
        bash = resolve_bash_executable()
        version = subprocess.run(
            [bash, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "microsoft" in (version.stdout + version.stderr).lower():
            self.skipTest("WSL bash is intentionally not used for this project")

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            paramiko_log = temp_dir / "paramiko.args"
            paramiko_stdin = temp_dir / "paramiko.stdin"
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "printf 'PASS_ENV=%s\\n' \"${SSH_WITH_PASSWORD_PARAMIKO_PASS:-}\" >\"$FAKE_PARAMIKO_LOG\"",
                        "printf '%s\\n' \"$@\" >>\"$FAKE_PARAMIKO_LOG\"",
                        "cat >\"$FAKE_PARAMIKO_STDIN\"",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text("#!/usr/bin/env bash\nexit 44\n", encoding="utf-8")
            fake_sshpass = fake_bin / "sshpass"
            fake_sshpass.write_text("#!/usr/bin/env bash\nexit 45\n", encoding="utf-8")
            os.chmod(fake_python, 0o755)
            os.chmod(fake_ssh, 0o755)
            os.chmod(fake_sshpass, 0o755)

            env = os.environ.copy()
            env.update(
                {
                    "OPENAMP_SSH_RUNNER": "paramiko",
                    "FAKE_PARAMIKO_LOG": bash_path(paramiko_log),
                    "FAKE_PARAMIKO_STDIN": bash_path(paramiko_stdin),
                }
            )
            command = (
                f"export PATH={shlex.quote(bash_path(fake_bin))}:$PATH; "
                f"bash {shlex.quote(bash_path(SSH_HELPER))} "
                "--host demo-board --user demo-user --pass demo-secret --port 2202 -- bash -s"
            )

            result = subprocess.run(
                [bash, "-lc", command],
                input="echo remote\n",
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = paramiko_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "PASS_ENV=demo-secret")
            self.assertIn("ssh_with_password_paramiko.py", lines[1])
            self.assertIn("--host", lines)
            self.assertIn("demo-board", lines)
            self.assertIn("--user", lines)
            self.assertIn("demo-user", lines)
            self.assertIn("--pass-env", lines)
            self.assertIn("SSH_WITH_PASSWORD_PARAMIKO_PASS", lines)
            self.assertIn("--port", lines)
            self.assertIn("2202", lines)
            self.assertIn("--timeout-sec", lines)
            self.assertIn("900", lines)
            self.assertIn("'bash' '-s'", lines)
            self.assertNotIn("demo-secret", "\n".join(lines[1:]))
            self.assertEqual(paramiko_stdin.read_text(encoding="utf-8"), "echo remote\n")

    def test_docker_runner_uses_sshpass_container_and_preserves_stdin(self) -> None:
        bash = resolve_bash_executable()
        version = subprocess.run(
            [bash, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "microsoft" in (version.stdout + version.stderr).lower():
            self.skipTest("WSL bash is intentionally not used for this project")

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            docker_log = temp_dir / "docker.args"
            docker_stdin = temp_dir / "docker.stdin"
            fake_docker = fake_bin / "docker"
            fake_docker.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "printf 'SSHPASS=%s\\n' \"${SSHPASS:-}\" >\"$FAKE_DOCKER_LOG\"",
                        "printf '%s\\n' \"$@\" >>\"$FAKE_DOCKER_LOG\"",
                        "cat >\"$FAKE_DOCKER_STDIN\"",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            os.chmod(fake_docker, 0o755)

            env = os.environ.copy()
            env.update(
                {
                    "OPENAMP_SSH_RUNNER": "docker",
                    "OPENAMP_SSH_DOCKER_IMAGE": "demo-ssh-image:latest",
                    "FAKE_DOCKER_LOG": bash_path(docker_log),
                    "FAKE_DOCKER_STDIN": bash_path(docker_stdin),
                }
            )
            command = (
                f"export PATH={shlex.quote(bash_path(fake_bin))}:$PATH; "
                f"bash {shlex.quote(bash_path(SSH_HELPER))} "
                "--host demo-board --user demo-user --pass demo-secret --port 2202 -- bash -s"
            )

            result = subprocess.run(
                [bash, "-lc", command],
                input="echo remote\n",
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = docker_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "SSHPASS=demo-secret")
            self.assertEqual(lines[1:4], ["run", "--rm", "-i"])
            self.assertIn("demo-ssh-image:latest", lines)
            self.assertIn("sshpass", lines)
            self.assertIn("ssh", lines)
            self.assertIn("LogLevel=ERROR", lines)
            self.assertIn("-p", lines)
            self.assertIn("2202", lines)
            self.assertIn("demo-user@demo-board", lines)
            self.assertIn("'bash' '-s'", lines)
            self.assertNotIn("demo-secret", "\n".join(lines[1:]))
            self.assertEqual(docker_stdin.read_text(encoding="utf-8"), "echo remote\n")


if __name__ == "__main__":
    unittest.main()
