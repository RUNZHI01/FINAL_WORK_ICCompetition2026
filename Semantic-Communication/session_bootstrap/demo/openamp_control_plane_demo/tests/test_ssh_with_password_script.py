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
            self.assertIn("-p", lines)
            self.assertIn("2202", lines)
            self.assertIn("demo-user@demo-board", lines)
            self.assertIn("'bash' '-s'", lines)
            self.assertNotIn("demo-secret", "\n".join(lines[1:]))
            self.assertEqual(docker_stdin.read_text(encoding="utf-8"), "echo remote\n")


if __name__ == "__main__":
    unittest.main()
