from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from threading import Lock
import unittest
from unittest.mock import Mock, patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))
SCRIPTS_ROOT = DEMO_ROOT.parents[1] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import inference_runner  # noqa: E402
import openamp_signed_manifest  # noqa: E402
from board_access import BoardAccessConfig  # noqa: E402
from inference_runner import (  # noqa: E402
    PROJECT_ROOT,
    LiveRemoteReconstructionJob,
    REMOTE_PYTORCH_REFERENCE_SCRIPT,
    REMOTE_RECONSTRUCTION_SCRIPT,
    live_control_hook_timeout_sec,
    run_remote_reconstruction,
)


def make_access(env_values: dict[str, str] | None = None) -> BoardAccessConfig:
    values = {
        "REMOTE_TVM_PYTHON": "/usr/bin/python3",
        "REMOTE_INPUT_DIR": "/tmp/input",
        "REMOTE_OUTPUT_BASE": "/tmp/output",
        "REMOTE_JSCC_DIR": "/tmp/jscc",
        "REMOTE_SNR_CURRENT": "12",
        "REMOTE_BATCH_CURRENT": "1",
        "INFERENCE_CURRENT_EXPECTED_SHA256": "a" * 64,
    }
    values.update(env_values or {})
    return BoardAccessConfig(
        host="demo-board",
        user="demo-user",
        password="demo-pass",
        port="22",
        env_file=None,
        env_values=values,
        source_summary="unit test",
    )


def generate_keypair(temp_dir: Path) -> tuple[Path, Path]:
    private_key = temp_dir / "demo-signing.pem"
    public_key = temp_dir / "demo-signing.pub.pem"
    subprocess.run(
        [
            "openssl",
            "genpkey",
            "-algorithm",
            "EC",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-out",
            str(private_key),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "openssl",
            "pkey",
            "-in",
            str(private_key),
            "-pubout",
            "-out",
            str(public_key),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return private_key, public_key


def build_signed_bundle(temp_dir: Path, *, variant: str = "current") -> tuple[Path, Path, Path, str]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = temp_dir / f"{variant}_optimized_model.so"
    artifact_path.write_bytes(f"demo-signed-{variant}-artifact".encode("utf-8"))
    private_key, public_key = generate_keypair(temp_dir)
    bundle = openamp_signed_manifest.build_signed_manifest_bundle(
        artifact_path=artifact_path,
        variant=variant,
        key_id=f"demo-live-{variant}-20260316",
        publisher_channel="openamp-demo",
        deadline_ms=300000,
        expected_outputs=inference_runner.DEFAULT_MAX_INPUTS,
        job_flags="reconstruction",
        private_key=private_key,
    )
    bundle_path = temp_dir / f"{variant}.bundle.json"
    openamp_signed_manifest.write_json(bundle_path, bundle)
    return artifact_path, bundle_path, public_key, str(bundle["manifest"]["artifact"]["sha256"])


class RunRemoteReconstructionTest(unittest.TestCase):
    def test_parse_runner_summary_tolerates_local_path_encoding_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            runner_log_path = Path(temp_dir) / "runner.log"
            payload_prefix = (
                b'{"status":"ok","runner":"run_big_little_pipeline.sh",'
                b'"log_file":"E:/Main/Career/'
            )
            payload_suffix = (
                b'/openamp.log","pipeline":{"status":"ok","processed_count":3,'
                b'"input_count":3,"run_median_ms":253.271,"run_mean_ms":262.139}}\n'
            )
            runner_log_path.write_bytes(payload_prefix + b"\xbc\xaf\xb4\xb4\xc8\xfc" + payload_suffix)

            summary = inference_runner.parse_runner_summary_from_log(runner_log_path)

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["pipeline"]["processed_count"], 3)
        self.assertAlmostEqual(summary["pipeline"]["run_median_ms"], 253.271)

    def test_runner_only_live_job_accepts_big_little_wrapper_log_with_local_encoding_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            runner_log_path = output_dir / "runner.log"
            trace_path = output_dir / "control_trace.jsonl"
            trace_path.write_text("", encoding="utf-8")
            (output_dir / "wrapper_summary.json").write_text(
                json.dumps({"result": "success", "runner_exit_code": 0}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            payload_prefix = (
                b'{"status":"ok","runner":"run_big_little_pipeline.sh",'
                b'"run_id":"biglittle-encoding-demo","log_file":"E:/Main/Career/'
            )
            payload_suffix = (
                b'/openamp.log","pipeline":{"status":"ok","processed_count":3,'
                b'"input_count":3,"run_samples_ms":[284.035,249.11,253.271],'
                b'"run_median_ms":253.271,"run_mean_ms":262.139,'
                b'"big_cores":[2],"little_cores":[0,1]}}\n'
            )
            runner_log_path.write_bytes(payload_prefix + b"\xbc\xaf\xb4\xb4\xc8\xfc" + payload_suffix)

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "3838347825"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = 3
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = output_dir / "wrapper_summary.json"
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None
            job._control_transport = inference_runner.CONTROL_TRANSPORT_NONE
            job._control_preflight = None
            job._admission = {"mode": "legacy_sha"}
            job._input_source_mode = "prerecorded"
            job._input_source_label = "预录模式"

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["execution_mode"], "live")
            self.assertEqual(snapshot["runner_summary"]["pipeline"]["processed_count"], 3)
            self.assertEqual(snapshot["progress"]["completed_count"], 3)
            self.assertEqual(snapshot["progress"]["expected_count"], 3)
            self.assertEqual(snapshot["progress"]["count_source"], "runner_summary.processed_count")

    def assert_live_signed_demo_trace(self, *, variant: str) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "live"
            output_dir.mkdir(parents=True, exist_ok=True)
            _, bundle_path, public_key, _ = build_signed_bundle(temp_dir / "bundle", variant=variant)
            hook_script = temp_dir / "fake_hook.py"
            hook_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "import sys",
                        "",
                        "event = json.loads(sys.stdin.read() or '{}')",
                        "phase = str(event.get('phase') or '')",
                        "if phase == 'STATUS_REQ':",
                        "    response = {",
                        "        'phase': phase,",
                        "        'transport_status': 'status_resp_received',",
                        "        'protocol_semantics': 'implemented',",
                        "    }",
                        "elif phase.startswith('SIGNED_ADMISSION_'):",
                        "    response = {",
                        "        'phase': phase,",
                        "        'acknowledged': True,",
                        "        'transport_status': 'signed_admission_ack_received',",
                        "        'protocol_semantics': 'implemented',",
                        "    }",
                        "elif phase == 'JOB_REQ':",
                        "    response = {",
                        "        'phase': phase,",
                        "        'decision': 'ALLOW',",
                        "        'fault_code': 0,",
                        "        'fault_name': 'NONE',",
                        "        'guard_state': 2,",
                        "        'guard_state_name': 'JOB_ACTIVE',",
                        "        'transport_status': 'job_ack_received',",
                        "        'protocol_semantics': 'implemented',",
                        "    }",
                        "else:",
                        "    response = {",
                        "        'phase': phase,",
                        "        'acknowledged': True,",
                        "        'transport_status': 'ack_received',",
                        "        'protocol_semantics': 'implemented',",
                        "    }",
                        "print(json.dumps(response, ensure_ascii=False))",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            bundle = openamp_signed_manifest.load_signed_manifest_bundle(bundle_path)
            transport_plan = openamp_signed_manifest.build_signed_admission_transport_plan(
                bundle,
                job_id=4242,
                key_slot=1,
                seq_start=1,
            )

            class ImmediateThread:
                def __init__(self, target=None, daemon=None, **_kwargs):
                    self._target = target

                def start(self) -> None:
                    if self._target is not None:
                        self._target()

            access_values = {
                "INFERENCE_CURRENT_EXPECTED_SHA256": "",
                "INFERENCE_BASELINE_EXPECTED_SHA256": "",
                "REMOTE_SNR_BASELINE": "12",
                "REMOTE_BATCH_BASELINE": "1",
            }
            if variant == "baseline":
                access_values.update(
                    {
                        inference_runner.DEMO_BASELINE_ADMISSION_MODE_ENV: "signed_manifest_v1",
                        inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                        inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                    }
                )
            else:
                access_values.update(
                    {
                        inference_runner.DEMO_ADMISSION_MODE_ENV: "signed_manifest_v1",
                        inference_runner.DEMO_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                        inference_runner.DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                    }
                )
            access = make_access(access_values)
            runner_cmd = (
                "python3 -c "
                "\"import json; print(json.dumps({'result': 'ok', 'samples': []}, ensure_ascii=False))\""
            )

            with (
                patch("inference_runner.generate_live_job_id", return_value="4242"),
                patch("inference_runner.tempfile.mkdtemp", return_value=str(output_dir)),
                patch("inference_runner.build_runner_command", return_value=runner_cmd),
                patch.object(
                    LiveRemoteReconstructionJob,
                    "_build_hook_command",
                    return_value=shlex.join(["python3", str(hook_script)]),
                ),
                patch("inference_runner.Thread", ImmediateThread),
            ):
                job = LiveRemoteReconstructionJob(access, variant=variant)

            trace_events = [
                json.loads(line)
                for line in (output_dir / "control_trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            manifest = json.loads((output_dir / "job_manifest.json").read_text(encoding="utf-8"))

        self.assertIsNotNone(job._final_snapshot)
        self.assertEqual(job._final_snapshot["status"], "success")
        self.assertEqual(job._final_snapshot["execution_mode"], "live")
        self.assertEqual(job._final_snapshot["variant"], variant)
        self.assertEqual(
            [event["phase"] for event in trace_events],
            ["STATUS_REQ", *[frame["phase"] for frame in transport_plan["frames"]], "JOB_ACK", "JOB_DONE"],
        )
        self.assertEqual(manifest["admission_mode"], "signed_manifest_v1")
        self.assertEqual(manifest["variant"], variant)

    def test_generate_live_job_id_uses_non_zero_uint32_nonce_and_stays_unique(self) -> None:
        original_last_job_id = inference_runner._LAST_LIVE_JOB_ID
        try:
            inference_runner._LAST_LIVE_JOB_ID = 0
            with patch("inference_runner.secrets.randbelow", side_effect=[0, 0, inference_runner.UINT32_MAX - 1]):
                first = inference_runner.generate_live_job_id()
                second = inference_runner.generate_live_job_id()
        finally:
            inference_runner._LAST_LIVE_JOB_ID = original_last_job_id

        self.assertEqual(first, "1")
        self.assertEqual(second, str(inference_runner.UINT32_MAX))
        self.assertLessEqual(int(second), inference_runner.UINT32_MAX)

    def test_count_completed_images_from_runner_log_uses_real_latency_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner_log = Path(temp_dir) / "runner.log"
            runner_log.write_text(
                "\n".join(
                    [
                        "[current-real] variant=current",
                        "2026-03-16 10:00:01 - INFO - 批量推理时间（1 个样本）: 0.011000 秒",
                        "重构图像保存至: /tmp/run/sample_001.png",
                        "2026-03-16 10:00:02 - INFO - 批量推理时间（1 个样本）: 0.012000 秒",
                        "batch inference time: 0.013 sec",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = inference_runner.count_completed_images_from_runner_log(runner_log)

        self.assertEqual(completed, 3)

    def test_parse_json_stdout_skips_trailing_non_json_lines(self) -> None:
        raw = "\n".join(
            [
                "[pytorch-ref] running",
                json.dumps({"openamp_demo_progress": {"completed_count": 1}}),
                json.dumps({"variant": "baseline", "processed_count": 1, "status": "success"}),
                "2026-05-05 INFO Manifest written",
                "2026-05-05 INFO Completed 1/1 reference reconstructions",
            ]
        )

        payload = inference_runner.parse_json_stdout(raw)

        self.assertEqual(payload["variant"], "baseline")
        self.assertEqual(payload["processed_count"], 1)

    def test_count_completed_images_from_runner_log_uses_openamp_demo_progress_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner_log = Path(temp_dir) / "runner.log"
            runner_log.write_text(
                "\n".join(
                    [
                        '{"openamp_demo_progress":{"completed_count":1,"expected_count":300}}',
                        '{"openamp_demo_progress":{"completed_count":4,"expected_count":300}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = inference_runner.count_completed_images_from_runner_log(runner_log)

        self.assertEqual(completed, 4)

    def test_build_completion_counts_marks_missing_runner_log_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner_log = Path(temp_dir) / "runner.log"

            counts = inference_runner.build_completion_counts(
                runner_log_path=runner_log,
                expected_outputs=inference_runner.DEFAULT_MAX_INPUTS,
            )

        self.assertEqual(counts["completed_count"], 0)
        self.assertEqual(counts["expected_count"], inference_runner.DEFAULT_MAX_INPUTS)
        self.assertEqual(counts["count_label"], f"0 / {inference_runner.DEFAULT_MAX_INPUTS}")
        self.assertEqual(counts["count_source"], "runner_log.missing")

    def test_build_completion_counts_uses_reconstruction_outputs_when_runner_log_has_no_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            runner_log = output_dir / "runner.log"
            runner_log.write_text(
                "\n".join(
                    [
                        "[2026-04-20T10:00:00+0800] openamp wrapper start",
                        "{\"phase\": \"HEARTBEAT\", \"note\": \"still running\"}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            reconstructions_dir = output_dir / "reconstructions"
            reconstructions_dir.mkdir(parents=True, exist_ok=True)
            for index in range(3):
                (reconstructions_dir / f"sample_{index:03d}_recon.png").write_bytes(b"demo")

            counts = inference_runner.build_completion_counts(
                runner_log_path=runner_log,
                expected_outputs=inference_runner.DEFAULT_MAX_INPUTS,
            )

        self.assertEqual(counts["completed_count"], 3)
        self.assertEqual(counts["count_source"], "output_dir.reconstruction_files")
        self.assertEqual(counts["count_label"], f"3 / {inference_runner.DEFAULT_MAX_INPUTS}")

    def test_running_snapshot_reports_real_completed_count_from_runner_log(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            runner_log_path = output_dir / "runner.log"
            runner_log_path.write_text(
                "\n".join(
                    [
                        "[2026-03-16T11:00:00+0800] openamp wrapper start",
                        "批量推理时间（1 个样本）: 0.012 秒",
                        "批量推理时间（1 个样本）: 0.014 秒",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            trace_path = output_dir / "control_trace.jsonl"
            trace_path.write_text(
                json.dumps(
                    {
                        "at": "2026-03-16T11:00:01+0800",
                        "phase": "JOB_ACK",
                        "payload": {"job_id": 4242, "decision": "ALLOW", "guard_state_name": "JOB_ACTIVE"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = output_dir / "wrapper_summary.json"
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None
            job._process = None

            snapshot = job.snapshot()

        self.assertEqual(snapshot["request_state"], "running")
        self.assertEqual(snapshot["progress"]["completed_count"], 2)
        self.assertEqual(snapshot["progress"]["expected_count"], inference_runner.DEFAULT_MAX_INPUTS)
        self.assertEqual(snapshot["progress"]["remaining_count"], inference_runner.DEFAULT_MAX_INPUTS - 2)
        self.assertEqual(snapshot["progress"]["count_label"], f"2 / {inference_runner.DEFAULT_MAX_INPUTS}")
        self.assertEqual(snapshot["progress"]["count_source"], "runner_log.sample_latency_lines")
        self.assertEqual(snapshot["progress"]["percent"], 1)

    def test_running_snapshot_reports_completed_count_from_reconstruction_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            runner_log_path = output_dir / "runner.log"
            runner_log_path.write_text(
                "\n".join(
                    [
                        "[2026-04-20T11:00:00+0800] openamp wrapper start",
                        '{"phase":"HEARTBEAT","payload":{"elapsed_ms":1200}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            reconstructions_dir = output_dir / "reconstructions"
            reconstructions_dir.mkdir(parents=True, exist_ok=True)
            for index in range(4):
                (reconstructions_dir / f"sample_{index:03d}_recon.png").write_bytes(b"demo")
            trace_path = output_dir / "control_trace.jsonl"
            trace_path.write_text(
                json.dumps(
                    {
                        "at": "2026-04-20T11:00:01+0800",
                        "phase": "JOB_ACK",
                        "payload": {"job_id": 4242, "decision": "ALLOW", "guard_state_name": "JOB_ACTIVE"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = output_dir / "wrapper_summary.json"
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None
            job._process = None

            snapshot = job.snapshot()

        self.assertEqual(snapshot["request_state"], "running")
        self.assertEqual(snapshot["progress"]["completed_count"], 4)
        self.assertEqual(snapshot["progress"]["count_source"], "output_dir.reconstruction_files")
        self.assertEqual(snapshot["progress"]["count_label"], f"4 / {inference_runner.DEFAULT_MAX_INPUTS}")

    def test_missing_required_config_returns_operator_friendly_config_error(self) -> None:
        access = make_access(
            {
                "REMOTE_TVM_PYTHON": "",
                "REMOTE_INPUT_DIR": "",
            }
        )

        payload = run_remote_reconstruction(access, variant="current")

        self.assertEqual(payload["status"], "config_error")
        self.assertEqual(payload["status_category"], "config_error")
        self.assertIn("远端推理配置不完整或不可用", payload["message"])
        self.assertNotIn("REMOTE_TVM_PYTHON", payload["message"])
        self.assertIn("REMOTE_TVM_PYTHON", payload["diagnostics"]["missing_fields"])
        self.assertIn("REMOTE_INPUT_DIR", payload["diagnostics"]["missing_fields"])

    def test_auth_failure_keeps_raw_stderr_in_diagnostics_only(self) -> None:
        access = make_access()
        runner_cmd = inference_runner.build_runner_command(
            access,
            variant="current",
            max_inputs=inference_runner.DEFAULT_MAX_INPUTS,
            seed=0,
        )
        command = ["bash", "-lc", runner_cmd]
        completed = subprocess.CompletedProcess(
            command,
            255,
            stdout="",
            stderr="Permission denied (publickey,password).\n",
        )

        with patch("inference_runner.subprocess.run", return_value=completed) as run_mock:
            payload = run_remote_reconstruction(access, variant="current", timeout_sec=12.0)

        run_mock.assert_called_once_with(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=12.0,
            env={
                **access.build_subprocess_env(),
                "REMOTE_MODE": "ssh",
                "OPENAMP_DEMO_MODE": "1",
                "OPENAMP_DEMO_MAX_INPUTS": str(inference_runner.DEFAULT_MAX_INPUTS),
            },
        )
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["status_category"], "auth_error")
        self.assertIn("认证失败", payload["message"])
        self.assertNotIn("Permission denied", payload["message"])
        self.assertEqual(
            payload["diagnostics"],
            {
                "stderr": "Permission denied (publickey,password).",
                "returncode": 255,
            },
        )

    def test_artifact_sha_mismatch_surfaces_actionable_category_and_structured_diagnostics(self) -> None:
        access = make_access()
        expected_sha = "1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644"
        actual_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
        artifact_path = "/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so"
        command = ["bash", "-lc", inference_runner.build_runner_command(access, variant="current", max_inputs=1, seed=0)]
        completed = subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=(
                "ERROR: artifact sha256 mismatch "
                f"path={artifact_path} expected={expected_sha} actual={actual_sha}\n"
            ),
        )

        with patch("inference_runner.subprocess.run", return_value=completed):
            payload = run_remote_reconstruction(access, variant="current")

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["status_category"], "artifact_mismatch")
        self.assertIn("trusted current SHA 不一致", payload["message"])
        self.assertNotIn(expected_sha, payload["message"])
        self.assertEqual(
            payload["diagnostics"],
            {
                "stderr": (
                    "ERROR: artifact sha256 mismatch "
                    f"path={artifact_path} expected={expected_sha} actual={actual_sha}"
                ),
                "returncode": 1,
                "artifact_path": artifact_path,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
            },
        )

    def test_build_hook_command_keeps_live_demo_on_bundled_bridge_runtime(self) -> None:
        access = make_access({"REMOTE_PROJECT_ROOT": "/tmp/openamp_wrong_sha_fit/project"})
        job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
        job.job_id = "job-123"

        command = shlex.split(job._build_hook_command(access))

        self.assertNotIn("--remote-project-root", command)

    def test_build_runner_command_pins_baseline_to_pytorch_live_runner(self) -> None:
        access = make_access(
            {
                "REMOTE_JSCC_DIR": "/tmp/jscc",
                "REMOTE_SNR_BASELINE": "10",
                "REMOTE_BATCH_BASELINE": "1",
                "INFERENCE_BASELINE_EXPECTED_SHA256": "b" * 64,
                "INFERENCE_BASELINE_CMD": "bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline",
            }
        )

        command = inference_runner.build_runner_command(access, variant="baseline", max_inputs=1, seed=0)

        self.assertEqual(
            command,
            (
                f"bash {inference_runner.bash_path(REMOTE_PYTORCH_REFERENCE_SCRIPT)} --max-images 1 --seed 0 "
                f"--expected-sha256 {'b' * 64}"
            ),
        )
        self.assertNotIn("run_remote_legacy_tvm_compat.sh", command)
        self.assertNotIn(REMOTE_RECONSTRUCTION_SCRIPT.name, command)

    def test_build_runner_command_keeps_sampling_args_for_current_reconstruction_cmd(self) -> None:
        access = make_access(
            {
                "INFERENCE_CURRENT_CMD": (
                    "bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh "
                    "--variant current --max-inputs 1 --seed 99 --profile-ops"
                ),
            }
        )

        command = inference_runner.build_runner_command(access, variant="current", max_inputs=3, seed=7)

        self.assertEqual(
            command,
            (
                f"bash {inference_runner.bash_path(REMOTE_RECONSTRUCTION_SCRIPT)} "
                "--variant current --profile-ops --max-inputs 3 --seed 7"
            ),
        )
        self.assertNotIn("--max-inputs 1", command)
        self.assertNotIn("--seed 99", command)

    def test_build_runner_command_for_current_uses_configured_big_little_pipeline_cmd(self) -> None:
        access = make_access(
            {
                "INFERENCE_CURRENT_CMD": (
                    "bash ./session_bootstrap/scripts/run_big_little_pipeline.sh "
                    "--variant current --max-inputs 300 --execution-mode pipeline"
                ),
            }
        )

        command = inference_runner.build_runner_command(access, variant="current", max_inputs=120, seed=7)

        self.assertEqual(
            command,
            shlex.join(
                [
                    "bash",
                    inference_runner.bash_path(
                        PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_big_little_pipeline.sh"
                    ),
                    "--variant",
                    "current",
                    "--execution-mode",
                    "pipeline",
                    "--max-inputs",
                    "120",
                    "--seed",
                    "7",
                ]
            ),
        )
        self.assertNotIn("--max-inputs 300", command)

    def test_build_runner_command_for_current_ignores_legacy_current_cmd_residue(self) -> None:
        access = make_access(
            {
                "INFERENCE_CURRENT_CMD": "bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant current --max-inputs 1",
            }
        )

        command = inference_runner.build_runner_command(access, variant="current", max_inputs=300, seed=0)

        self.assertEqual(
            command,
            shlex.join(
                [
                    "bash",
                    inference_runner.bash_path(REMOTE_RECONSTRUCTION_SCRIPT),
                    "--variant",
                    "current",
                    "--max-inputs",
                    "300",
                    "--seed",
                    "0",
                ]
            ),
        )
        self.assertNotIn("run_remote_legacy_tvm_compat.sh", command)

    def test_baseline_live_job_requires_formal_baseline_expected_sha_before_launch(self) -> None:
        access = make_access(
            {
                "REMOTE_SNR_BASELINE": "12",
                "REMOTE_BATCH_BASELINE": "1",
            }
        )

        with patch("inference_runner.subprocess.Popen") as popen_mock:
            live_job = LiveRemoteReconstructionJob(access, variant="baseline")

        snapshot = live_job.snapshot()
        self.assertEqual(snapshot["status"], "config_error")
        self.assertEqual(snapshot["status_category"], "config_error")
        self.assertIn("PyTorch generator expected SHA", snapshot["message"])
        self.assertEqual(snapshot["diagnostics"]["missing_fields"], ["INFERENCE_BASELINE_EXPECTED_SHA256"])
        popen_mock.assert_not_called()

    def test_signed_manifest_current_live_job_requires_bundle_and_public_key(self) -> None:
        access = make_access(
            {
                "INFERENCE_CURRENT_EXPECTED_SHA256": "",
                inference_runner.DEMO_ADMISSION_MODE_ENV: "signed_manifest_v1",
            }
        )

        with patch("inference_runner.subprocess.Popen") as popen_mock:
            live_job = LiveRemoteReconstructionJob(access, variant="current")

        snapshot = live_job.snapshot()
        self.assertEqual(snapshot["status"], "config_error")
        self.assertEqual(snapshot["status_category"], "config_error")
        self.assertIn("signed-manifest admission", snapshot["message"])
        self.assertEqual(
            snapshot["diagnostics"]["missing_fields"],
            [
                inference_runner.DEMO_SIGNED_MANIFEST_FILE_ENV,
                inference_runner.DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV,
            ],
        )
        popen_mock.assert_not_called()

    def test_signed_manifest_baseline_live_job_requires_bundle_and_public_key(self) -> None:
        access = make_access(
            {
                "REMOTE_SNR_BASELINE": "12",
                "REMOTE_BATCH_BASELINE": "1",
                "INFERENCE_BASELINE_EXPECTED_SHA256": "",
                inference_runner.DEMO_BASELINE_ADMISSION_MODE_ENV: "signed_manifest_v1",
            }
        )

        with patch("inference_runner.subprocess.Popen") as popen_mock:
            live_job = LiveRemoteReconstructionJob(access, variant="baseline")

        snapshot = live_job.snapshot()
        self.assertEqual(snapshot["status"], "config_error")
        self.assertEqual(snapshot["status_category"], "config_error")
        self.assertIn("PyTorch live 已切到 signed-manifest admission", snapshot["message"])
        self.assertEqual(
            snapshot["diagnostics"]["missing_fields"],
            [
                inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV,
                inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV,
            ],
        )
        popen_mock.assert_not_called()

    def test_describe_demo_admission_verifies_signed_manifest_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            _, bundle_path, public_key, expected_sha256 = build_signed_bundle(temp_dir)
            access = make_access(
                {
                    "INFERENCE_CURRENT_EXPECTED_SHA256": "",
                    inference_runner.DEMO_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                    inference_runner.DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                }
            )

            summary = inference_runner.describe_demo_admission(access, variant="current")

        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["mode"], "signed_manifest_v1")
        self.assertTrue(summary["verified_locally"])
        self.assertTrue(summary["artifact_match"])
        self.assertEqual(summary["artifact_sha256"], expected_sha256)
        self.assertEqual(summary["bundle_path"], str(bundle_path))
        self.assertEqual(summary["public_key_path"], str(public_key))

    def test_describe_demo_admission_reports_baseline_signed_manifest_variant_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            _, bundle_path, public_key, _ = build_signed_bundle(temp_dir, variant="current")
            access = make_access(
                {
                    "REMOTE_SNR_BASELINE": "12",
                    "REMOTE_BATCH_BASELINE": "1",
                    "INFERENCE_BASELINE_EXPECTED_SHA256": "",
                    inference_runner.DEMO_BASELINE_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                }
            )

            summary = inference_runner.describe_demo_admission(access, variant="baseline")

        self.assertEqual(summary["status"], "config_error")
        self.assertEqual(summary["mode"], "signed_manifest_v1")
        self.assertIn("does not match demo variant 'baseline'", summary["note"])

    def test_describe_demo_variant_support_marks_baseline_signed_live_as_ready_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            _, current_bundle_path, current_public_key, _ = build_signed_bundle(temp_dir / "current", variant="current")
            _, baseline_bundle_path, baseline_public_key, _ = build_signed_bundle(
                temp_dir / "baseline",
                variant="baseline",
            )
            access = make_access(
                {
                    "REMOTE_SNR_BASELINE": "12",
                    "REMOTE_BATCH_BASELINE": "1",
                    "INFERENCE_CURRENT_EXPECTED_SHA256": "",
                    "INFERENCE_BASELINE_EXPECTED_SHA256": "",
                    inference_runner.DEMO_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_SIGNED_MANIFEST_FILE_ENV: str(current_bundle_path),
                    inference_runner.DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(current_public_key),
                    inference_runner.DEMO_BASELINE_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV: str(baseline_bundle_path),
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(baseline_public_key),
                }
            )

            support = inference_runner.describe_demo_variant_support(access, variant="baseline")

        self.assertEqual(support["status"], "ready")
        self.assertEqual(support["mode"], "signed_manifest_v1")
        self.assertTrue(support["launch_allowed"])
        self.assertEqual(support["label"], "PyTorch signed live 已支持")
        self.assertIn("PyTorch signed-admission live path is supported.", support["note"])

    def test_describe_demo_variant_support_marks_baseline_expected_sha_live_without_legacy_user_label(self) -> None:
        access = make_access(
            {
                "REMOTE_SNR_BASELINE": "12",
                "REMOTE_BATCH_BASELINE": "1",
                "INFERENCE_BASELINE_EXPECTED_SHA256": "b" * 64,
            }
        )

        support = inference_runner.describe_demo_variant_support(access, variant="baseline")

        self.assertEqual(support["status"], "ready")
        self.assertEqual(support["mode"], "legacy_sha")
        self.assertEqual(support["label"], "PyTorch live 已支持")
        self.assertEqual(support["tone"], "neutral")
        self.assertTrue(support["launch_allowed"])
        self.assertIn("expected-SHA admission (legacy_sha)", support["note"])
        self.assertIn("historical live evidence", support["note"])
        self.assertNotIn("legacy live", support["label"])

    def test_live_job_constructor_passes_generated_uint32_job_id_to_wrapper_and_hook(self) -> None:
        access = make_access(
            {
                "REMOTE_PROJECT_ROOT": "/tmp/openamp_demo/project",
                "INFERENCE_CURRENT_CMD": "bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant current --max-inputs 1",
            }
        )

        with (
            patch("inference_runner.generate_live_job_id", return_value="4242"),
            patch("inference_runner.tempfile.mkdtemp", return_value="/tmp/openamp_demo_live_test"),
            patch("inference_runner.subprocess.Popen", return_value=object()) as popen_mock,
            patch("inference_runner.Thread") as thread_cls,
        ):
            thread_cls.return_value.start.return_value = None
            live_job = LiveRemoteReconstructionJob(access, variant="current")

        self.assertEqual(live_job.job_id, "4242")
        command = popen_mock.call_args.args[0]
        self.assertEqual(command[command.index("--job-id") + 1], "4242")
        self.assertEqual(
            command[command.index("--control-hook-timeout-sec") + 1],
            str(live_control_hook_timeout_sec(900.0)),
        )
        self.assertEqual(command[command.index("--heartbeat-interval-sec") + 1], "2.0")
        self.assertEqual(
            command[command.index("--expected-outputs") + 1],
            str(inference_runner.DEFAULT_MAX_INPUTS),
        )
        runner_cmd = command[command.index("--runner-cmd") + 1]
        self.assertIn(inference_runner.bash_path(REMOTE_RECONSTRUCTION_SCRIPT), runner_cmd)
        self.assertNotIn("run_remote_legacy_tvm_compat.sh", runner_cmd)
        self.assertIn(f"--max-inputs {inference_runner.DEFAULT_MAX_INPUTS}", runner_cmd)
        self.assertIn("--seed 0", runner_cmd)
        hook_command = command[command.index("--control-hook-cmd") + 1]
        self.assertIn("--remote-output-root", hook_command)
        self.assertIn("/tmp/openamp_demo_hook/4242", hook_command)
        env = popen_mock.call_args.kwargs["env"]
        self.assertEqual(env["OPENAMP_DEMO_MODE"], "1")
        self.assertEqual(env["OPENAMP_DEMO_MAX_INPUTS"], str(inference_runner.DEFAULT_MAX_INPUTS))

    def test_live_job_constructor_passes_signed_manifest_args_for_current_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            _, bundle_path, public_key, expected_sha256 = build_signed_bundle(temp_dir)
            access = make_access(
                {
                    "INFERENCE_CURRENT_EXPECTED_SHA256": "",
                    inference_runner.DEMO_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                    inference_runner.DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                }
            )

            with (
                patch("inference_runner.generate_live_job_id", return_value="4242"),
                patch("inference_runner.tempfile.mkdtemp", return_value="/tmp/openamp_demo_live_test"),
                patch(
                    "inference_runner.verify_signed_manifest_bundle",
                    return_value={
                        "admission_mode": "signed_manifest_v1",
                        "artifact_sha256": expected_sha256,
                        "variant": "current",
                        "deadline_ms": 300000,
                        "expected_outputs": inference_runner.DEFAULT_MAX_INPUTS,
                        "job_flags": "reconstruction",
                        "manifest_sha256": "c" * 64,
                        "key_id": "demo-live-20260316",
                        "signature_algorithm": "ecdsa-p256-sha256",
                        "verified_locally": True,
                        "artifact_match": True,
                    },
                ),
                patch("inference_runner.subprocess.Popen", return_value=object()) as popen_mock,
                patch("inference_runner.Thread") as thread_cls,
            ):
                thread_cls.return_value.start.return_value = None
                LiveRemoteReconstructionJob(access, variant="current")

        command = popen_mock.call_args.args[0]
        self.assertEqual(command[command.index("--expected-sha256") + 1], expected_sha256)
        self.assertEqual(command[command.index("--admission-mode") + 1], "signed_manifest_v1")
        self.assertEqual(command[command.index("--signed-manifest-file") + 1], str(bundle_path))
        self.assertEqual(command[command.index("--signed-manifest-public-key") + 1], str(public_key))

    def test_live_job_constructor_passes_signed_manifest_args_for_baseline_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            _, bundle_path, public_key, expected_sha256 = build_signed_bundle(temp_dir, variant="baseline")
            access = make_access(
                {
                    "REMOTE_SNR_BASELINE": "12",
                    "REMOTE_BATCH_BASELINE": "1",
                    "INFERENCE_BASELINE_EXPECTED_SHA256": "",
                    inference_runner.DEMO_BASELINE_ADMISSION_MODE_ENV: "signed_manifest_v1",
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV: str(bundle_path),
                    inference_runner.DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV: str(public_key),
                }
            )

            with (
                patch("inference_runner.generate_live_job_id", return_value="4242"),
                patch("inference_runner.tempfile.mkdtemp", return_value="/tmp/openamp_demo_live_test"),
                patch(
                    "inference_runner.verify_signed_manifest_bundle",
                    return_value={
                        "admission_mode": "signed_manifest_v1",
                        "artifact_sha256": expected_sha256,
                        "variant": "baseline",
                        "deadline_ms": 300000,
                        "expected_outputs": inference_runner.DEFAULT_MAX_INPUTS,
                        "job_flags": "reconstruction",
                        "manifest_sha256": "c" * 64,
                        "key_id": "demo-live-baseline-20260316",
                        "signature_algorithm": "ecdsa-p256-sha256",
                        "verified_locally": True,
                        "artifact_match": True,
                    },
                ),
                patch("inference_runner.subprocess.Popen", return_value=object()) as popen_mock,
                patch("inference_runner.Thread") as thread_cls,
            ):
                thread_cls.return_value.start.return_value = None
                LiveRemoteReconstructionJob(access, variant="baseline")

        command = popen_mock.call_args.args[0]
        self.assertEqual(command[command.index("--expected-sha256") + 1], expected_sha256)
        self.assertEqual(command[command.index("--admission-mode") + 1], "signed_manifest_v1")
        self.assertEqual(command[command.index("--signed-manifest-file") + 1], str(bundle_path))
        self.assertEqual(command[command.index("--signed-manifest-public-key") + 1], str(public_key))

    def test_live_job_current_signed_manifest_runs_wrapper_sideband_sequence(self) -> None:
        self.assert_live_signed_demo_trace(variant="current")

    def test_live_job_baseline_signed_manifest_runs_wrapper_sideband_sequence(self) -> None:
        self.assert_live_signed_demo_trace(variant="baseline")

    def test_live_job_control_hook_timeout_is_capped_at_runner_timeout_when_shorter(self) -> None:
        access = make_access()

        with (
            patch("inference_runner.generate_live_job_id", return_value="4242"),
            patch("inference_runner.tempfile.mkdtemp", return_value="/tmp/openamp_demo_live_test"),
            patch("inference_runner.subprocess.Popen", return_value=object()) as popen_mock,
            patch("inference_runner.Thread") as thread_cls,
        ):
            thread_cls.return_value.start.return_value = None
            LiveRemoteReconstructionJob(access, variant="current", timeout_sec=12.0)

        command = popen_mock.call_args.args[0]
        self.assertEqual(
            command[command.index("--control-hook-timeout-sec") + 1],
            str(live_control_hook_timeout_sec(12.0)),
        )

    def test_permission_gate_failure_surfaces_explicit_live_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"

            summary_path.write_text(
                json.dumps({"result": "denied_by_control_hook"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-15T20:00:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "source": "replayed_live_status_resp",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                            "rx_frame": {
                                "status_resp": {
                                    "guard_state_name": "READY",
                                    "last_fault_name": "NONE",
                                }
                            },
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:00:01+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4242, "expected_sha256": "abcd" * 16},
                    "hook_result": {
                        "returncode": 2,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "DENY",
                            "fault_code": 0,
                            "fault_name": "NONE",
                            "guard_state": 0,
                            "guard_state_name": "BOOT",
                            "source": "linux_bridge_permission_guard",
                            "transport_status": "permission_gate",
                            "protocol_semantics": "not_attempted",
                            "note": (
                                "JOB_REQ could not access /dev/rpmsg0: [Errno 13] Permission denied: "
                                "'/dev/rpmsg0'. The board-side bridge needs root or passwordless sudo "
                                "for RPMsg device access."
                            ),
                            "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                            "rpmsg_dev": "/dev/rpmsg0",
                            "device_status": {
                                "rpmsg_ctrl": {"path": "/dev/rpmsg_ctrl0", "exists": True},
                                "rpmsg_dev": {"path": "/dev/rpmsg0", "exists": True},
                            },
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:00:01+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4242,
                        "decision": "DENY",
                        "fault_code": 0,
                        "fault_name": "NONE",
                        "guard_state": 0,
                        "guard_state_name": "BOOT",
                        "source": "linux_bridge_permission_guard",
                        "transport_status": "permission_gate",
                        "protocol_semantics": "not_attempted",
                        "note": (
                            "JOB_REQ could not access /dev/rpmsg0: [Errno 13] Permission denied: "
                            "'/dev/rpmsg0'. The board-side bridge needs root or passwordless sudo "
                            "for RPMsg device access."
                        ),
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = output_dir / "runner.log"
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = (summary_path.read_text(encoding="utf-8"), "")
            fake_process.returncode = 2
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "permission_error")
            self.assertIn("root 或 passwordless sudo", snapshot["message"])
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["transport_status"], "permission_gate")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["rpmsg_dev"], "/dev/rpmsg0")
            self.assertIn("板端权限门禁", snapshot["progress"]["stages"][2]["detail"])
            self.assertIn("/dev/rpmsg0", snapshot["progress"]["stages"][2]["detail"])
            self.assertIn("transport=permission_gate", snapshot["progress"]["event_log"][2])

    def test_tx_ok_rx_timeout_marks_control_stages_as_failed_and_keeps_zero_progress(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"

            summary_path.write_text(
                json.dumps({"result": "denied_by_control_hook"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-16T11:24:03+0800",
                    "phase": "STATUS_REQ",
                    "payload": {
                        "job_id": 4203105938,
                        "variant": "current_reconstruction",
                        "expected_sha256": "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
                        "job_flags": "reconstruction",
                    },
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "tx_ok_rx_timeout",
                            "protocol_semantics": "not_verified",
                            "note": (
                                "write to /dev/rpmsg0 succeeded but no response arrived before timeout. "
                                "Do not claim STATUS_RESP semantics from this result."
                            ),
                        },
                    },
                },
                {
                    "at": "2026-03-16T11:24:06+0800",
                    "phase": "JOB_REQ",
                    "payload": {
                        "job_id": 4203105938,
                        "expected_sha256": "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1",
                        "deadline_ms": 300000,
                        "expected_outputs": 300,
                        "job_flags": "reconstruction",
                        "runner_cmd": (
                            "bash /home/tianxing/tvm_metaschedule_execution_project/"
                            "session_bootstrap/scripts/run_remote_current_real_reconstruction.sh "
                            "--variant current --max-inputs 300 --seed 0"
                        ),
                    },
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "DENY",
                            "fault_code": 0,
                            "fault_name": "NONE",
                            "guard_state": 0,
                            "guard_state_name": "BOOT",
                            "source": "linux_bridge_transport_guard",
                            "transport_status": "tx_ok_rx_timeout",
                            "protocol_semantics": "not_verified",
                            "note": (
                                "JOB_REQ was written to /dev/rpmsg0 but no JOB_ACK arrived before timeout. "
                                "The wrapper must deny locally instead of assuming admission."
                            ),
                        },
                    },
                },
                {
                    "at": "2026-03-16T11:24:09+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4203105938,
                        "decision": "DENY",
                        "source": "linux_bridge_transport_guard",
                        "fault_code": 0,
                        "fault_name": "NONE",
                        "guard_state": 0,
                        "guard_state_name": "BOOT",
                        "transport_status": "tx_ok_rx_timeout",
                        "protocol_semantics": "not_verified",
                        "note": (
                            "JOB_REQ was written to /dev/rpmsg0 but no JOB_ACK arrived before timeout. "
                            "The wrapper must deny locally instead of assuming admission."
                        ),
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4203105938"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = output_dir / "runner.log"
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 2
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertFalse(snapshot["control_handshake_complete"])
            self.assertIn("STATUS_REQ 已写入 RPMsg", snapshot["message"])
            self.assertIn("JOB_REQ 已写入 RPMsg", snapshot["message"])
            self.assertEqual(snapshot["progress"]["count_label"], f"0 / {inference_runner.DEFAULT_MAX_INPUTS}")
            self.assertEqual(snapshot["progress"]["count_source"], "runner_log.missing")
            self.assertEqual(snapshot["progress"]["label"], "握手未完成，已回退")
            self.assertEqual(snapshot["progress"]["stages"][0]["status"], "error")
            self.assertEqual(snapshot["progress"]["stages"][1]["status"], "error")
            self.assertEqual(snapshot["progress"]["stages"][2]["status"], "error")
            self.assertEqual(snapshot["progress"]["current_stage"], "连接失败")
            self.assertIn("transport=tx_ok_rx_timeout", snapshot["progress"]["event_log"][0])
            self.assertIn("transport=tx_ok_rx_timeout", snapshot["progress"]["event_log"][1])
            self.assertIn("tx_ok_rx_timeout", snapshot["progress"]["event_log"][2])

    def test_success_snapshot_keeps_control_hook_timeout_as_diagnostic_not_runner_timeout(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            summary_path.write_text(
                json.dumps({"result": "success"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-16T10:00:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "timed_out": False,
                        "duration_ms": 820,
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                        },
                    },
                },
                {
                    "at": "2026-03-16T10:00:02+0800",
                    "phase": "HEARTBEAT",
                    "payload": {"job_id": 4242, "elapsed_ms": 2000, "runtime_state": "RUNNING"},
                    "hook_result": {
                        "returncode": None,
                        "timed_out": True,
                        "timeout_sec": 30.0,
                        "duration_ms": 30012,
                        "response": {
                            "phase": "HEARTBEAT",
                            "source": "openamp_control_wrapper",
                            "transport_status": "hook_timeout",
                            "protocol_semantics": "not_verified",
                            "note": "HEARTBEAT control hook timed out after 30.0s.",
                        },
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )
            runner_log_path.write_text(
                json.dumps(
                    {
                        "processed_count": 300,
                        "input_count": 300,
                        "load_ms": 2.9,
                        "vm_init_ms": 0.5,
                        "run_median_ms": 230.339,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["status_category"], "success")
            self.assertIn("hook 超时", snapshot["message"])
            self.assertEqual(snapshot["diagnostics"]["control_hook_stats"]["timeout_count"], 1)
            self.assertEqual(snapshot["diagnostics"]["control_hook_stats"]["heartbeat_event_count"], 1)
            self.assertAlmostEqual(snapshot["runner_summary"]["run_median_ms"], 230.339)

    def test_current_live_job_surfaces_slowdown_message_when_heartbeat_hooks_are_expensive(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            summary_path.write_text(
                json.dumps({"result": "success"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-16T10:28:32+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "timed_out": False,
                        "duration_ms": 2955,
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                        },
                    },
                },
                {
                    "at": "2026-03-16T10:28:35+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "timed_out": False,
                        "duration_ms": 2876,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "ALLOW",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                        },
                    },
                },
                {
                    "at": "2026-03-16T10:28:35+0800",
                    "phase": "JOB_ACK",
                    "payload": {"job_id": 4242, "decision": "ALLOW", "guard_state_name": "JOB_ACTIVE"},
                },
            ]
            for offset, duration_ms in enumerate((3521, 3375, 3470, 2818, 3463, 3550, 3410, 3605, 3342), start=1):
                trace_events.append(
                    {
                        "at": f"2026-03-16T10:29:{offset:02d}+0800",
                        "phase": "HEARTBEAT",
                        "payload": {"job_id": 4242, "elapsed_ms": offset * 4000, "runtime_state": "RUNNING"},
                        "hook_result": {
                            "returncode": 0,
                            "timed_out": False,
                            "duration_ms": duration_ms,
                            "response": {
                                "phase": "HEARTBEAT",
                                "acknowledged": True,
                                "heartbeat_ok": 1,
                                "guard_state_name": "JOB_ACTIVE",
                                "source": "firmware_heartbeat_ack",
                                "transport_status": "heartbeat_ack_received",
                                "protocol_semantics": "implemented",
                            },
                        },
                    }
                )
            trace_events.append(
                {
                    "at": "2026-03-16T10:30:54+0800",
                    "phase": "JOB_DONE",
                    "payload": {"job_id": 4242, "elapsed_ms": 134774, "result_code": 0, "runner_exit_code": 0},
                    "hook_result": {
                        "returncode": 0,
                        "timed_out": False,
                        "duration_ms": 2899,
                        "response": {
                            "phase": "JOB_DONE",
                            "acknowledged": True,
                            "transport_status": "job_done_status_received",
                            "protocol_semantics": "implemented",
                        },
                    },
                }
            )
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )
            runner_log_path.write_text(
                json.dumps(
                    {
                        "processed_count": 300,
                        "input_count": 300,
                        "load_ms": 2.718,
                        "vm_init_ms": 0.473,
                        "run_median_ms": 370.274,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "success")
            self.assertIn("370.274 ms", snapshot["message"])
            self.assertIn("230.339 ms", snapshot["message"])
            self.assertIn("HEARTBEAT hook", snapshot["message"])
            self.assertTrue(snapshot["diagnostics"]["performance_regression"]["control_plane_interference_suspected"])
            self.assertEqual(snapshot["diagnostics"]["performance_regression"]["heartbeat_event_count"], 9)
            self.assertGreater(snapshot["diagnostics"]["control_hook_stats"]["heartbeat_duration_total_ms"], 30000)

    def test_baseline_live_job_ack_artifact_mismatch_is_not_mislabeled_as_permission_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"

            summary_path.write_text(
                json.dumps({"result": "denied_by_control_hook"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-15T20:20:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "source": "firmware_status_resp",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable STATUS_RESP frame.",
                            "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                            "rpmsg_dev": "/dev/rpmsg0",
                            "rx_frame": {
                                "status_resp": {
                                    "guard_state_name": "READY",
                                    "last_fault_name": "ARTIFACT_SHA_MISMATCH",
                                }
                            },
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:20:01+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4242, "expected_sha256": "abcd" * 16},
                    "hook_result": {
                        "returncode": 2,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "DENY",
                            "fault_code": 1,
                            "fault_name": "ARTIFACT_SHA_MISMATCH",
                            "guard_state": 1,
                            "guard_state_name": "READY",
                            "source": "firmware_job_ack",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable JOB_ACK frame from firmware.",
                            "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                            "rpmsg_dev": "/dev/rpmsg0",
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:20:01+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4242,
                        "decision": "DENY",
                        "fault_code": 1,
                        "fault_name": "ARTIFACT_SHA_MISMATCH",
                        "guard_state": 1,
                        "guard_state_name": "READY",
                        "source": "firmware_job_ack",
                        "transport_status": "job_ack_received",
                        "protocol_semantics": "implemented",
                        "note": "Received a decodable JOB_ACK frame from firmware.",
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "baseline"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = output_dir / "runner.log"
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 2
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "artifact_mismatch")
            self.assertIn("PyTorch generator checkpoint", snapshot["message"])
            self.assertNotIn("passwordless sudo", snapshot["message"])
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["fault_name"], "ARTIFACT_SHA_MISMATCH")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["transport_status"], "job_ack_received")
            self.assertIn("ARTIFACT_SHA_MISMATCH", snapshot["progress"]["stages"][2]["detail"])

    def test_live_runner_log_artifact_mismatch_is_promoted_into_status_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            summary_path.write_text(
                json.dumps({"result": "runner_failed"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            artifact_path = "/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so"
            expected_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
            actual_sha = "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849"
            runner_log_path.write_text(
                "\n".join(
                    [
                        "[2026-03-16T02:40:43+0800] openamp wrapper start",
                        "runner_cmd=bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300 --seed 0",
                        (
                            "ERROR: artifact sha256 mismatch "
                            f"path={artifact_path} expected={expected_sha} actual={actual_sha}"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-16T02:40:39+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 1200412253},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "source": "firmware_status_resp",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable STATUS_RESP frame.",
                        },
                    },
                },
                {
                    "at": "2026-03-16T02:40:40+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 1200412253, "expected_sha256": expected_sha},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "ALLOW",
                            "fault_name": "NONE",
                            "guard_state_name": "JOB_ACTIVE",
                            "source": "firmware_job_ack",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable JOB_ACK frame from firmware.",
                        },
                    },
                },
                {
                    "at": "2026-03-16T02:40:40+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 1200412253,
                        "decision": "ALLOW",
                        "fault_name": "NONE",
                        "guard_state_name": "JOB_ACTIVE",
                        "source": "firmware_job_ack",
                        "transport_status": "job_ack_received",
                        "protocol_semantics": "implemented",
                        "note": "Received a decodable JOB_ACK frame from firmware.",
                    },
                },
                {
                    "at": "2026-03-16T02:40:56+0800",
                    "phase": "JOB_DONE",
                    "payload": {
                        "job_id": 1200412253,
                        "elapsed_ms": 13056,
                        "result_code": 1,
                        "runner_exit_code": 1,
                        "timed_out": False,
                    },
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "JOB_DONE",
                            "reported_result_code": 1,
                            "reported_output_count": 0,
                            "reported_success": False,
                            "guard_state_name": "READY",
                            "last_fault_name": "OUTPUT_INCOMPLETE",
                            "source": "firmware_job_done_status",
                            "transport_status": "job_done_status_received",
                            "protocol_semantics": "implemented",
                            "note": "Received STATUS_RESP after failed JOB_DONE.",
                        },
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "1200412253"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 1
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "artifact_mismatch")
            self.assertIn("trusted current SHA 不一致", snapshot["message"])
            self.assertEqual(snapshot["diagnostics"]["artifact_path"], artifact_path)
            self.assertEqual(snapshot["diagnostics"]["expected_sha256"], expected_sha)
            self.assertEqual(snapshot["diagnostics"]["actual_sha256"], actual_sha)
            self.assertIn("artifact sha256 mismatch", snapshot["diagnostics"]["runner_log_tail"])
            self.assertEqual(snapshot["progress"]["count_label"], f"0 / {inference_runner.DEFAULT_MAX_INPUTS}")

    def test_live_runner_log_tail_is_attached_for_generic_runner_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            summary_path.write_text(
                json.dumps({"result": "runner_failed"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            runner_log_path.write_text(
                "\n".join(
                    [
                        "[2026-03-16T03:55:46+0800] openamp wrapper start",
                        "runner_cmd=bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300 --seed 0",
                        '  File "<string>", line 1',
                        "    import",
                        "         ^",
                        "SyntaxError: invalid syntax",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            trace_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "at": "2026-03-16T03:55:45+0800",
                                "phase": "JOB_ACK",
                                "payload": {
                                    "job_id": 1118993338,
                                    "decision": "ALLOW",
                                    "fault_name": "NONE",
                                    "guard_state_name": "JOB_ACTIVE",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "at": "2026-03-16T03:55:48+0800",
                                "phase": "JOB_DONE",
                                "payload": {
                                    "job_id": 1118993338,
                                    "elapsed_ms": 2023,
                                    "result_code": 1,
                                    "runner_exit_code": 1,
                                    "timed_out": False,
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "1118993338"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 1
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "error")
            self.assertIn("SyntaxError: invalid syntax", snapshot["diagnostics"]["runner_log_tail"])

    def test_duplicate_job_ack_is_not_mislabeled_as_permission_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"

            summary_path.write_text(
                json.dumps({"result": "denied_by_control_hook"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-16T02:27:47+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4072741809},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "source": "firmware_status_resp",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable STATUS_RESP frame.",
                            "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                            "rpmsg_dev": "/dev/rpmsg0",
                            "rx_frame": {
                                "status_resp": {
                                    "guard_state_name": "READY",
                                    "last_fault_name": "NONE",
                                }
                            },
                        },
                    },
                },
                {
                    "at": "2026-03-16T02:27:52+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4072741809, "expected_sha256": "abcd" * 16},
                    "hook_result": {
                        "returncode": 2,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "DENY",
                            "fault_code": 8,
                            "fault_name": "DUPLICATE_JOB_ID",
                            "guard_state": 2,
                            "guard_state_name": "JOB_ACTIVE",
                            "source": "firmware_job_ack",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable JOB_ACK frame from firmware.",
                            "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                            "rpmsg_dev": "/dev/rpmsg0",
                        },
                    },
                },
                {
                    "at": "2026-03-16T02:27:52+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4072741809,
                        "decision": "DENY",
                        "fault_code": 8,
                        "fault_name": "DUPLICATE_JOB_ID",
                        "guard_state": 2,
                        "guard_state_name": "JOB_ACTIVE",
                        "source": "firmware_job_ack",
                        "transport_status": "job_ack_received",
                        "protocol_semantics": "implemented",
                        "note": "Received a decodable JOB_ACK frame from firmware.",
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4072741809"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = output_dir / "runner.log"
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 2
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "board_busy")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["fault_name"], "DUPLICATE_JOB_ID")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["guard_state_name"], "JOB_ACTIVE")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["rpmsg_dev"], "/dev/rpmsg0")
            self.assertNotIn("passwordless sudo", snapshot["message"])
            self.assertIn("guard_state=JOB_ACTIVE", snapshot["message"])
            self.assertIn("不会自动 SAFE_STOP", snapshot["message"])
            self.assertIn("板端已有活动作业", snapshot["progress"]["stages"][2]["detail"])

    def test_ssh_bridge_launch_failure_surfaces_host_env_error_and_stage_gate(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"

            summary_path.write_text(
                json.dumps({"result": "denied_by_control_hook"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-15T20:10:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 255,
                        "response": {
                            "phase": "STATUS_REQ",
                            "source": "openamp_demo_remote_hook_proxy",
                            "transport_status": "ssh_bridge_launch_failed",
                            "protocol_semantics": "not_verified",
                            "note": "远端 bridge 启动失败，rc=255。",
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:10:01+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4242, "expected_sha256": "abcd" * 16},
                    "hook_result": {
                        "returncode": 255,
                        "response": {
                            "phase": "JOB_REQ",
                            "source": "openamp_demo_remote_hook_proxy",
                            "transport_status": "ssh_bridge_launch_failed",
                            "protocol_semantics": "not_verified",
                            "note": "远端 bridge 启动失败，rc=255。",
                        },
                    },
                },
                {
                    "at": "2026-03-15T20:10:01+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4242,
                        "decision": "DENY",
                        "fault_code": 0,
                        "fault_name": "NONE",
                        "guard_state": 0,
                        "guard_state_name": "UNKNOWN",
                        "source": "openamp_demo_remote_hook_proxy",
                        "transport_status": "ssh_bridge_launch_failed",
                        "protocol_semantics": "not_verified",
                        "note": "远端 bridge 启动失败，rc=255。",
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = output_dir / "runner.log"
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = (
                "",
                "socket: Operation not permitted\nssh: connect to host demo-board port 22: failure\n",
            )
            fake_process.returncode = 2
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "error")
            self.assertEqual(snapshot["status_category"], "host_env_error")
            self.assertIn("当前主机环境禁止建立 SSH socket", snapshot["message"])
            self.assertNotIn("passwordless sudo", snapshot["message"])
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["transport_status"], "ssh_bridge_launch_failed")
            self.assertEqual(snapshot["progress"]["current_stage"], "连接失败")
            self.assertEqual(snapshot["progress"]["stages"][0]["status"], "error")
            self.assertEqual(snapshot["progress"]["stages"][1]["status"], "error")
            self.assertEqual(snapshot["progress"]["stages"][0]["detail"], "远端 bridge 启动失败，rc=255。")
            self.assertEqual(snapshot["progress"]["stages"][1]["detail"], "远端 bridge 启动失败，rc=255。")

    def test_runner_only_compat_mode_reports_live_success_without_claiming_control_handshake(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            summary_path.write_text(
                json.dumps({"result": "success"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            trace_events = [
                {
                    "at": "2026-03-17T10:00:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 501},
                },
                {
                    "at": "2026-03-17T10:00:01+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 501, "expected_sha256": "abcd" * 16},
                },
                {
                    "at": "2026-03-17T10:00:01+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 501,
                        "decision": "ALLOW",
                        "guard_state_name": "COMPAT_MODE",
                        "fault_name": "NONE",
                    },
                },
                {
                    "at": "2026-03-17T10:00:02+0800",
                    "phase": "JOB_DONE",
                    "payload": {
                        "job_id": 501,
                        "runner_exit_code": 0,
                        "result_code": 0,
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )
            runner_log_path.write_text(
                json.dumps(
                    {
                        "load_ms": 12.0,
                        "vm_init_ms": 34.0,
                        "run_median_ms": 56.0,
                        "processed_count": inference_runner.DEFAULT_MAX_INPUTS,
                        "input_count": inference_runner.DEFAULT_MAX_INPUTS,
                        "artifact_sha256": "a" * 64,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "501"
            job.variant = "baseline"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None
            job._expected_outputs = inference_runner.DEFAULT_MAX_INPUTS
            job._control_transport = inference_runner.CONTROL_TRANSPORT_NONE
            job._control_preflight = {
                "status": "timeout",
                "status_category": "timeout",
                "message": "远端状态查询超时，请确认板卡在线后重试。",
            }
            job._admission = {"mode": "signed_manifest_v1"}

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None

    def test_wait_for_completion_repairs_missing_job_done_via_hook(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            output_dir = Path(temp_dir)
            trace_path = output_dir / "control_trace.jsonl"
            runner_log_path = output_dir / "runner.log"

            trace_events = [
                {
                    "at": "2026-04-21T13:45:22+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 501},
                    "hook_result": {
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                        },
                        "timed_out": False,
                        "timeout_sec": 30.0,
                        "duration_ms": 10,
                    },
                },
                {
                    "at": "2026-04-21T13:45:24+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 501, "expected_sha256": "a" * 64},
                    "hook_result": {
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "ALLOW",
                            "fault_name": "NONE",
                            "guard_state_name": "JOB_ACTIVE",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                        },
                        "timed_out": False,
                        "timeout_sec": 30.0,
                        "duration_ms": 10,
                    },
                },
                {
                    "at": "2026-04-21T13:45:24+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 501,
                        "decision": "ALLOW",
                        "fault_name": "NONE",
                        "guard_state_name": "JOB_ACTIVE",
                        "transport_status": "job_ack_received",
                        "protocol_semantics": "implemented",
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )
            runner_log_path.write_text(
                json.dumps(
                    {
                        "load_ms": 10.0,
                        "vm_init_ms": 20.0,
                        "run_median_ms": 30.0,
                        "processed_count": 1,
                        "input_count": 1,
                        "artifact_sha256": "b" * 64,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "501"
            job.variant = "current"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = output_dir / "wrapper_summary.json"
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None
            job._expected_outputs = 1
            job._control_transport = inference_runner.CONTROL_TRANSPORT_HOOK
            job._hook_cmd = "python3 fake_hook.py"
            job._hook_timeout_sec = 30.0
            job._control_preflight = None
            job._admission = {"mode": "legacy_sha"}

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            repair_response = {
                "phase": "JOB_DONE",
                "transport_status": "job_done_status_received",
                "protocol_semantics": "implemented",
                "note": "Received STATUS_RESP after JOB_DONE and firmware reported the active job as cleared.",
                "guard_state_name": "READY",
            }

            with patch(
                "inference_runner.subprocess.run",
                return_value=Mock(returncode=0, stdout=json.dumps(repair_response, ensure_ascii=False), stderr=""),
            ) as hook_run:
                job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["execution_mode"], "live")
            phases = [
                json.loads(line)["phase"]
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(phases[-1], "JOB_DONE")
            self.assertEqual(phases.count("JOB_DONE"), 1)
            hook_run.assert_called_once()
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["execution_mode"], "live")
            self.assertEqual(snapshot["control_transport"], "hook")
            self.assertTrue(snapshot["control_handshake_complete"])
            self.assertEqual(snapshot["message"], "OpenAMP 控制面已完成作业下发、板端执行与结果回收。")
            self.assertEqual(snapshot["diagnostics"]["control_hook"]["transport_status"], "job_done_status_received")
            self.assertEqual(snapshot["progress"]["label"], "真实在线推进")
            self.assertEqual(snapshot["progress"]["stages"][0]["detail"], "STATUS_RESP: status_resp_received / fault=UNKNOWN")
            self.assertIn("STATUS_REQ -> guard=", snapshot["progress"]["event_log"][0])


if __name__ == "__main__":
    unittest.main()
