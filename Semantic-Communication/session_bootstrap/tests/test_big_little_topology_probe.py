from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "big_little_topology_probe.py"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import big_little_topology_probe as topology_probe  # noqa: E402


LSCPU_TEXT = """Architecture:                         aarch64
CPU(s):                               4
On-line CPU(s) list:                  0-3
Model name:                           Demo SoC
"""

LSCPU_E_TEXT = """CPU CORE SOCKET NODE ONLINE MAXMHZ MINMHZ MHZ
0 0 0 0 yes 2200.0000 900.0000 2101.0000
1 1 0 0 yes 2200.0000 900.0000 2088.0000
2 2 0 0 yes 1600.0000 600.0000 1511.0000
3 3 0 0 yes 1600.0000 600.0000 1498.0000
"""

HOMOGENEOUS_LSCPU_E_TEXT = """CPU CORE SOCKET NODE ONLINE MAXMHZ MINMHZ MHZ
0 0 0 0 yes 2000.0000 800.0000 1980.0000
1 1 0 0 yes 2000.0000 800.0000 1975.0000
2 2 0 0 yes 2000.0000 800.0000 1969.0000
3 3 0 0 yes 2000.0000 800.0000 1960.0000
"""


def parse_last_json(stdout: str) -> dict[str, object]:
    for raw in reversed(stdout.splitlines()):
        line = raw.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"no JSON payload found in output:\n{stdout}")


class BigLittleTopologyProbeTest(unittest.TestCase):
    def test_cli_parse_pair_of_files_recommends_big_and_little_cores(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            lscpu_path = temp_dir / "lscpu.txt"
            lscpu_e_path = temp_dir / "lscpu_e.txt"
            lscpu_path.write_text(LSCPU_TEXT, encoding="utf-8")
            lscpu_e_path.write_text(LSCPU_E_TEXT, encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "parse",
                    "--lscpu",
                    str(lscpu_path),
                    "--lscpu-e",
                    str(lscpu_e_path),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["suggestion"]["basis"], "maxmhz")
            self.assertEqual(payload["suggestion"]["big_cores"], [0, 1])
            self.assertEqual(payload["suggestion"]["little_cores"], [2, 3])
            self.assertEqual(payload["suggestion"]["big_cores_env"], "0,1")
            self.assertEqual(payload["suggestion"]["little_cores_env"], "2,3")

    def test_cli_parse_capture_from_stdin_works(self) -> None:
        capture = topology_probe.build_raw_capture(LSCPU_TEXT, LSCPU_E_TEXT)

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "parse",
                "--stdin-kind",
                "capture",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            input=capture,
        )

        payload = parse_last_json(completed.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["input"]["stdin_used"])
        self.assertEqual(payload["suggestion"]["big_cores_env"], "0,1")
        self.assertEqual(payload["suggestion"]["little_cores_env"], "2,3")

    def test_analyze_topology_requires_manual_confirmation_without_frequency_split(self) -> None:
        payload = topology_probe.analyze_topology(
            lscpu_text=LSCPU_TEXT,
            lscpu_e_text=HOMOGENEOUS_LSCPU_E_TEXT,
            source="unit_test",
        )

        self.assertEqual(payload["status"], "needs_manual_confirmation")
        self.assertEqual(payload["suggestion"]["basis"], "none")
        self.assertEqual(payload["suggestion"]["big_cores"], [])
        self.assertEqual(payload["suggestion"]["little_cores"], [])

    def test_build_remote_probe_command_uses_password_helper(self) -> None:
        command, connection = topology_probe.build_remote_probe_command(
            host="demo-board",
            user="demo-user",
            password="demo-pass",
            port="2202",
        )

        self.assertEqual(connection["auth_mode"], "ssh_with_password")
        self.assertEqual(
            command[:10],
            [
                "bash",
                str(topology_probe.SSH_WITH_PASSWORD_SCRIPT),
                "--host",
                "demo-board",
                "--user",
                "demo-user",
                "--pass",
                "demo-pass",
                "--port",
                "2202",
            ],
        )
        self.assertIn(topology_probe.RAW_LSCPU_BEGIN, command[-1])
        self.assertIn("lscpu -e", command[-1])

    def test_run_remote_probe_parses_mocked_stdout_and_writes_raw_capture(self) -> None:
        capture = topology_probe.build_raw_capture(LSCPU_TEXT, LSCPU_E_TEXT)
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            raw_path = Path(temp_dir_raw) / "topology_capture.txt"
            args = argparse.Namespace(
                env="",
                host="demo-board",
                user="demo-user",
                password="demo-pass",
                port="22",
                write_raw=str(raw_path),
                timeout_sec=5.0,
            )
            completed = subprocess.CompletedProcess(
                args=["ssh"],
                returncode=0,
                stdout=capture,
                stderr="",
            )

            with patch.object(topology_probe.subprocess, "run", return_value=completed) as run_mock:
                payload = topology_probe.run_remote_probe(args)

            run_mock.assert_called_once()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["source"], "ssh")
            self.assertEqual(payload["suggestion"]["big_cores_env"], "0,1")
            self.assertTrue(raw_path.is_file())
            self.assertEqual(raw_path.read_text(encoding="utf-8"), capture)

    def test_build_remote_probe_command_without_password_uses_plain_ssh(self) -> None:
        command, connection = topology_probe.build_remote_probe_command(
            host="demo-board",
            user="demo-user",
            password="",
            port="22",
        )

        self.assertEqual(connection["auth_mode"], "ssh")
        self.assertEqual(
            command[:8],
            [
                "ssh",
                "-p",
                "22",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
            ],
        )
        self.assertIn("BatchMode=yes", command)


if __name__ == "__main__":
    unittest.main()
