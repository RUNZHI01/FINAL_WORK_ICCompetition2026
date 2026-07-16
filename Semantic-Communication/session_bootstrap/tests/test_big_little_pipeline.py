from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from openamp_control_wrapper import resolve_bash_executable  # noqa: E402
import big_little_pipeline as pipeline  # noqa: E402

PYTHON_RUNNER = SCRIPTS_DIR / "big_little_pipeline.py"
WRAPPER_RUNNER = SCRIPTS_DIR / "run_big_little_pipeline.sh"
COMPARE_RUNNER = SCRIPTS_DIR / "run_big_little_compare.sh"
BASH = resolve_bash_executable()
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def bash_path(path: str | Path) -> str:
    if os.name != "nt":
        return str(path)
    completed = subprocess.run(
        [BASH, "-lc", 'cygpath -u "$1"', "cygpath", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


FAKE_REMOTE_CAPTURE = """=== BIG_LITTLE_LSCPU BEGIN ===
Architecture:                         aarch64
CPU(s):                               4
On-line CPU(s) list:                  0-3
Model name:                           Fake Demo SoC
=== BIG_LITTLE_LSCPU END ===
=== BIG_LITTLE_LSCPU_E BEGIN ===
CPU CORE SOCKET NODE ONLINE MAXMHZ MINMHZ MHZ
0 0 0 0 yes 2200.0000 900.0000 2101.0000
1 1 0 0 yes 2200.0000 900.0000 2088.0000
2 2 0 0 yes 1600.0000 600.0000 1511.0000
3 3 0 0 yes 1600.0000 600.0000 1498.0000
=== BIG_LITTLE_LSCPU_E END ===
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


def write_mock_inputs(input_dir: Path, count: int) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        array = np.full((1, 32, 32, 32), fill_value=index + 1, dtype=np.float32)
        np.save(input_dir / f"sample_{index:03d}.npy", array)


def write_mock_artifact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mock-big-little-artifact")


class BigLittlePipelineTest(unittest.TestCase):
    def test_wrapper_remote_execute_closes_stdin_for_password_helper(self) -> None:
        script = WRAPPER_RUNNER.read_text(encoding="utf-8")

        self.assertIn('"umask 077; cat > \'$REMOTE_RUNNER_SCRIPT\'" <"$runner_script"', script)
        self.assertIn(
            '"set -e; chmod 700 \'$REMOTE_RUNNER_SCRIPT\'; set +e; bash \'$REMOTE_RUNNER_SCRIPT\'; '
            'rc=\\$?; rm -f \'$REMOTE_RUNNER_SCRIPT\'; exit \\$rc" < /dev/null',
            script,
        )

    def test_wrapper_converts_msys_paths_before_windows_python_reads_them(self) -> None:
        script = WRAPPER_RUNNER.read_text(encoding="utf-8")

        self.assertIn("local_python_path()", script)
        self.assertIn('input_path="$(local_python_path "$1")"', script)
        self.assertIn('pipeline_json_file_py="$(local_python_path "$pipeline_json_file")"', script)
        self.assertIn('pipeline_json_file_py="$(local_python_path "$PIPELINE_JSON_FILE")"', script)

    def test_python_runner_dry_run_writes_summary_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            input_dir = temp_dir / "inputs"
            output_dir = temp_dir / "outputs"
            summary_json = temp_dir / "summary.json"
            summary_md = temp_dir / "summary.md"
            write_mock_artifact(artifact_path)
            write_mock_inputs(input_dir, count=3)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PYTHON_RUNNER),
                    "--artifact-path",
                    str(artifact_path),
                    "--input-dir",
                    str(input_dir),
                    "--output-dir",
                    str(output_dir),
                    "--snr",
                    "12",
                    "--batch-size",
                    "1",
                    "--variant",
                    "current",
                    "--dry-run",
                    "--allow-missing-affinity",
                    "--big-cores",
                    "0",
                    "--little-cores",
                    "1",
                    "--backend",
                    "threads",
                    "--max-inputs",
                    "3",
                    "--summary-json",
                    str(summary_json),
                    "--summary-md",
                    str(summary_md),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["processed_count"], 3)
            self.assertEqual(payload["output_count"], 3)
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue((output_dir / "reconstructions").is_dir())

    def test_dynamic_input_iterator_waits_for_late_npz(self) -> None:
        import threading
        import time

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            input_dir = Path(temp_dir_raw) / "inputs"
            input_dir.mkdir()

            def publish_late_input() -> None:
                time.sleep(0.1)
                np.savez(input_dir / "00000000.npz", latent=np.zeros((1, 4, 4, 4), dtype=np.float32))

            producer = threading.Thread(target=publish_late_input)
            producer.start()
            try:
                files = list(
                    pipeline.iter_input_files_dynamic(
                        input_dir=input_dir,
                        max_inputs=1,
                        wait_timeout_sec=2.0,
                        poll_sec=0.02,
                    )
                )
            finally:
                producer.join(timeout=2.0)

            self.assertEqual([path.name for path in files], ["00000000.npz"])

    def test_dynamic_input_iterator_releases_inputs_in_chunks(self) -> None:
        import threading
        import time

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            input_dir = Path(temp_dir_raw) / "inputs"
            input_dir.mkdir()
            yielded: list[str] = []
            errors: list[Exception] = []

            def publish(index: int) -> None:
                np.savez(input_dir / f"{index:08d}.npz", latent=np.zeros((1, 4, 4, 4), dtype=np.float32))

            def consume_inputs() -> None:
                try:
                    for path in pipeline.iter_input_files_dynamic(
                        input_dir=input_dir,
                        max_inputs=5,
                        wait_timeout_sec=3.0,
                        poll_sec=0.02,
                        chunk_size=3,
                    ):
                        yielded.append(path.name)
                except Exception as exc:  # pragma: no cover - assertion reports unexpected worker errors.
                    errors.append(exc)

            consumer = threading.Thread(target=consume_inputs)
            consumer.start()
            try:
                publish(0)
                publish(1)
                time.sleep(0.15)
                self.assertEqual(errors, [])
                self.assertEqual(yielded, [])

                publish(2)
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline and len(yielded) < 3:
                    time.sleep(0.02)
                self.assertEqual(yielded[:3], ["00000000.npz", "00000001.npz", "00000002.npz"])

                publish(3)
                publish(4)
            finally:
                consumer.join(timeout=4.0)

            self.assertFalse(consumer.is_alive(), "dynamic iterator did not flush final partial chunk")
            self.assertEqual(errors, [])
            self.assertEqual(
                yielded,
                ["00000000.npz", "00000001.npz", "00000002.npz", "00000003.npz", "00000004.npz"],
            )

    def test_wrapper_local_env_dry_run_emits_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "artifact" / "optimized_model.so"
            input_dir = temp_dir / "inputs"
            output_base = temp_dir / "remote_outputs"
            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            env_file = temp_dir / "local.env"
            write_mock_artifact(artifact_path)
            write_mock_inputs(input_dir, count=4)
            env_file.write_text(
                "\n".join(
                    [
                        f"LOG_DIR={shlex.quote(bash_path(log_dir))}",
                        f"REPORT_DIR={shlex.quote(bash_path(report_dir))}",
                        "REMOTE_MODE=local",
                        "REMOTE_TVM_PYTHON=/usr/bin/python3",
                        f"REMOTE_LOCAL_PYTHON_CANDIDATES={shlex.quote(bash_path(sys.executable))}",
                        f"REMOTE_INPUT_DIR={shlex.quote(bash_path(input_dir))}",
                        f"REMOTE_OUTPUT_BASE={shlex.quote(bash_path(output_base))}",
                        f"REMOTE_CURRENT_ARTIFACT={shlex.quote(bash_path(artifact_path))}",
                        "REMOTE_SNR_CURRENT=12",
                        "REMOTE_BATCH_CURRENT=1",
                        "BIG_LITTLE_BIG_CORES=0",
                        "BIG_LITTLE_LITTLE_CORES=1",
                        "BIG_LITTLE_BACKEND=threads",
                        "BIG_LITTLE_ALLOW_MISSING_AFFINITY=1",
                        "BIG_LITTLE_INPUT_QUEUE_SIZE=2",
                        "BIG_LITTLE_OUTPUT_QUEUE_SIZE=2",
                        "BIG_LITTLE_DRY_RUN=1",
                        "BIG_LITTLE_MOCK_INFER_MS=5",
                        "BIG_LITTLE_MAX_INPUTS=4",
                        "BIG_LITTLE_OUTPUT_PREFIX=unit_big_little_outputs",
                        "BIG_LITTLE_REPORT_PREFIX=unit_big_little_report",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    BASH,
                    bash_path(WRAPPER_RUNNER),
                    "--env",
                    bash_path(env_file),
                    "--variant",
                    "current",
                    "--run-id",
                    "unit_big_little_wrapper",
                    "--allow-overwrite",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=UTF8_ENV,
            )

            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["pipeline"]["status"], "ok")
            self.assertEqual(payload["pipeline"]["processed_count"], 4)
            self.assertEqual(payload["pipeline"]["execution_mode"], "pipeline")
            report_json = report_dir / "unit_big_little_wrapper.json"
            report_md = report_dir / "unit_big_little_wrapper.md"
            log_file = log_dir / "unit_big_little_wrapper.log"
            self.assertTrue(report_json.is_file())
            self.assertTrue(report_md.is_file())
            self.assertIn(
                f"resolved_remote_tvm_python={bash_path(sys.executable)}",
                log_file.read_text(encoding="utf-8"),
            )

    @unittest.skipUnless(COMPARE_RUNNER.is_file(), "run_big_little_compare.sh is not present")
    def test_compare_wrapper_local_mock_uses_serial_dry_run_fallback(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "artifact" / "optimized_model.so"
            input_dir = temp_dir / "inputs"
            output_base = temp_dir / "remote_outputs"
            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            env_file = temp_dir / "local.env"
            write_mock_artifact(artifact_path)
            write_mock_inputs(input_dir, count=4)
            env_file.write_text(
                "\n".join(
                    [
                        f"LOG_DIR={shlex.quote(bash_path(log_dir))}",
                        f"REPORT_DIR={shlex.quote(bash_path(report_dir))}",
                        "REMOTE_MODE=local",
                        "REMOTE_TVM_PYTHON=/usr/bin/python3",
                        f"REMOTE_LOCAL_PYTHON_CANDIDATES={shlex.quote(bash_path(sys.executable))}",
                        f"REMOTE_INPUT_DIR={shlex.quote(bash_path(input_dir))}",
                        f"REMOTE_OUTPUT_BASE={shlex.quote(bash_path(output_base))}",
                        f"REMOTE_CURRENT_ARTIFACT={shlex.quote(bash_path(artifact_path))}",
                        "REMOTE_SNR_CURRENT=12",
                        "REMOTE_BATCH_CURRENT=1",
                        "BIG_LITTLE_BIG_CORES=0",
                        "BIG_LITTLE_LITTLE_CORES=1",
                        "BIG_LITTLE_BACKEND=threads",
                        "BIG_LITTLE_ALLOW_MISSING_AFFINITY=1",
                        "BIG_LITTLE_INPUT_QUEUE_SIZE=2",
                        "BIG_LITTLE_OUTPUT_QUEUE_SIZE=2",
                        "BIG_LITTLE_DRY_RUN=1",
                        "BIG_LITTLE_MOCK_INFER_MS=5",
                        "BIG_LITTLE_MAX_INPUTS=4",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    BASH,
                    bash_path(COMPARE_RUNNER),
                    "--env",
                    bash_path(env_file),
                    "--run-id",
                    "unit_big_little_compare",
                    "--allow-overwrite",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=UTF8_ENV,
            )

            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertIn("comparison", payload)
            self.assertIsNotNone(payload["comparison"]["throughput_uplift_pct"])
            self.assertIn("--execution-mode serial", payload["serial_command"])
            self.assertEqual(payload["serial"]["pipeline"]["execution_mode"], "serial")
            self.assertEqual(payload["pipeline"]["pipeline"]["execution_mode"], "pipeline")
            self.assertEqual(payload["board_state"]["capture_status"], "skipped")
            self.assertEqual(payload["board_state"]["capture_reason"], "REMOTE_MODE is not ssh")

    @unittest.skipUnless(COMPARE_RUNNER.is_file(), "run_big_little_compare.sh is not present")
    def test_compare_wrapper_ssh_capture_records_board_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                f"{FAKE_REMOTE_CAPTURE}"
                "EOF\n",
                encoding="utf-8",
            )
            fake_ssh.chmod(0o755)

            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            env_file = temp_dir / "ssh.env"
            env_file.write_text(
                "\n".join(
                    [
                        f"LOG_DIR={shlex.quote(bash_path(log_dir))}",
                        f"REPORT_DIR={shlex.quote(bash_path(report_dir))}",
                        "REMOTE_MODE=ssh",
                        "REMOTE_HOST=fake-board",
                        "REMOTE_USER=fake-user",
                        "REMOTE_PASS=",
                        "REMOTE_SSH_PORT=22",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            serial_payload = {"status": "ok", "processed_count": 4, "total_wall_ms": 40.0}
            pipeline_payload = {"status": "ok", "processed_count": 4, "total_wall_ms": 30.0}
            serial_cmd = f"printf '%s\\n' {shlex.quote(json.dumps(serial_payload))}"
            pipeline_cmd = f"printf '%s\\n' {shlex.quote(json.dumps(pipeline_payload))}"
            completed = subprocess.run(
                [
                    BASH,
                    bash_path(COMPARE_RUNNER),
                    "--env",
                    bash_path(env_file),
                    "--run-id",
                    "unit_big_little_compare_remote_capture",
                    "--allow-overwrite",
                    "--serial-cmd",
                    serial_cmd,
                    "--pipeline-cmd",
                    pipeline_cmd,
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **UTF8_ENV,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                },
            )

            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["board_state"]["capture_status"], "ok")
            self.assertEqual(payload["board_state"]["capture_reason"], "automatic ssh topology snapshots enabled")
            summary = payload["board_state"]["summary"]
            self.assertEqual(summary["pre_serial_status"], "ok")
            self.assertEqual(summary["pre_pipeline_status"], "ok")
            self.assertEqual(summary["post_pipeline_status"], "ok")
            self.assertEqual(summary["pre_serial_online_cpus"], [0, 1, 2, 3])
            self.assertEqual(summary["pre_pipeline_online_cpus"], [0, 1, 2, 3])
            self.assertEqual(summary["post_pipeline_online_cpus"], [0, 1, 2, 3])
            self.assertFalse(summary["online_cpu_changed_across_compare"])

            snapshots = payload["board_state"]["snapshots"]
            self.assertTrue(Path(snapshots["pre_serial"]["json_path"]).is_file())
            self.assertTrue(Path(snapshots["pre_serial"]["raw_path"]).is_file())
            self.assertEqual(snapshots["pre_serial"]["payload"]["suggestion"]["big_cores_env"], "0,1")
            self.assertEqual(snapshots["pre_serial"]["payload"]["suggestion"]["little_cores_env"], "2,3")


if __name__ == "__main__":
    unittest.main()
