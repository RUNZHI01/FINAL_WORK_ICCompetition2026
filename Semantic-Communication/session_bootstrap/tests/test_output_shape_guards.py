from __future__ import annotations

import json
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
COMPUTE_RUNNER = SCRIPTS_DIR / "compute_image_quality_metrics.py"
BENCHMARK_RUNNER = SCRIPTS_DIR / "run_inference_benchmark.sh"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_python_with_module(module_name: str) -> str | None:
    candidates: list[str] = []
    for raw_candidate in [sys.executable, "python3", "python"]:
        candidate = shutil.which(raw_candidate) if Path(raw_candidate).name == raw_candidate else raw_candidate
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        completed = subprocess.run(
            [candidate, "-c", f"import {module_name}"],
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return candidate
    return None


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def write_png(path: Path, *, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixel = bytes(rgb)
    rows = [b"\x00" + pixel * width for _ in range(height)]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr),
            png_chunk(b"IDAT", zlib.compress(b"".join(rows))),
            png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(payload)


def write_payload_script(path: Path, *, output_shape: list[int]) -> None:
    payload = {
        "load_ms": 1.25,
        "vm_init_ms": 2.5,
        "run_median_ms": 3.75,
        "run_mean_ms": 3.75,
        "run_min_ms": 3.75,
        "run_max_ms": 3.75,
        "run_variance_ms2": 0.0,
        "run_count": 1,
        "output_shape": output_shape,
        "output_dtype": "float32",
        "artifact_path": "/tmp/fake_optimized_model.so",
        "artifact_sha256": "abc123",
        "artifact_sha256_expected": "abc123",
        "artifact_sha256_match": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        f"printf '%s\\n' {shlex.quote(json.dumps(payload, ensure_ascii=False))}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def write_benchmark_env(
    path: Path,
    *,
    log_dir: Path,
    report_dir: Path,
    run_id: str,
    policy: str,
    baseline_script: Path,
    current_script: Path,
) -> None:
    lines = [
        "MODEL_NAME=jscc",
        f"TARGET={shlex.quote('{\"kind\":\"llvm\"}')}",
        "SHAPE_BUCKETS=1x3x224x224,1x3x256x256",
        "TUNE_INPUT_SHAPE=1,32,32,32",
        "TUNE_INPUT_DTYPE=float32",
        f"LOG_DIR={shlex.quote(str(log_dir))}",
        f"REPORT_DIR={shlex.quote(str(report_dir))}",
        f"INFERENCE_EXECUTION_ID={shlex.quote(run_id)}",
        "ALLOW_REPORT_OVERWRITE=1",
        "INFERENCE_TIMEOUT_SEC=0",
        "INFERENCE_REPEAT=1",
        "INFERENCE_WARMUP_RUNS=0",
        f"INFERENCE_COMPARE_SHAPE_POLICY={policy}",
        f"INFERENCE_BASELINE_CMD={shlex.quote(f'bash {baseline_script}')}",
        f"INFERENCE_CURRENT_CMD={shlex.quote(f'bash {current_script}')}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ComputeImageQualityMetricsShapeGuardTest(unittest.TestCase):
    def test_default_top_left_normalization_sets_warning_status(self) -> None:
        python_with_numpy = find_python_with_module("numpy")
        if python_with_numpy is None:
            self.skipTest("numpy is unavailable in local Python interpreters")
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            ref_dir = temp_dir / "ref"
            test_dir = temp_dir / "test"
            report_prefix = temp_dir / "reports" / "quality_shape_guard"
            write_png(ref_dir / "sample.png", width=4, height=4, rgb=(10, 20, 30))
            write_png(test_dir / "sample.png", width=6, height=6, rgb=(10, 20, 30))

            completed = subprocess.run(
                [
                    python_with_numpy,
                    str(COMPUTE_RUNNER),
                    "--ref-dir",
                    str(ref_dir),
                    "--test-dir",
                    str(test_dir),
                    "--comparison-label",
                    "unit_shape_guard",
                    "--lpips",
                    "off",
                    "--report-prefix",
                    str(report_prefix),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = load_json(report_prefix.with_suffix(".json"))
            self.assertEqual(payload["status"], "success_shape_mismatch_warned")
            self.assertEqual(payload["size_mismatch_mode"], "crop-top-left")
            self.assertEqual(payload["size_mismatch_mode_resolved"], "crop-top-left")
            self.assertEqual(payload["shape_mismatch_status"], "normalized_warning")
            self.assertEqual(payload["shape_mismatch_count"], 1)
            self.assertIn("Normalized 1 shape-mismatched pair(s) via crop-top-left", payload["shape_mismatch_message"])
            self.assertEqual(payload["shape_mismatch_patterns"][0]["anchor"], "top-left")
            self.assertIn("Shape mismatch: normalized_warning", completed.stdout)
            self.assertIn("crop-top-left", completed.stdout)


class InferenceBenchmarkOutputShapeGuardTest(unittest.TestCase):
    def test_warn_policy_keeps_run_successful_but_marks_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            env_file = temp_dir / "warn.env"
            baseline_script = temp_dir / "baseline.sh"
            current_script = temp_dir / "current.sh"
            run_id = "unit_inference_shape_warn"
            write_payload_script(baseline_script, output_shape=[1, 3, 249, 249])
            write_payload_script(current_script, output_shape=[1, 3, 256, 256])
            write_benchmark_env(
                env_file,
                log_dir=log_dir,
                report_dir=report_dir,
                run_id=run_id,
                policy="warn",
                baseline_script=baseline_script,
                current_script=current_script,
            )

            completed = subprocess.run(
                ["bash", str(BENCHMARK_RUNNER), "--env", str(env_file)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            report_text = (report_dir / f"{run_id}.md").read_text(encoding="utf-8")
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("WARN: Baseline/current output shape mismatch under policy=warn", completed.stderr)
            self.assertIn("- status: success_shape_mismatch_warned", report_text)
            self.assertIn("- output_shape_compare_policy: warn", report_text)
            self.assertIn("- output_shape_compare_status: mismatch_warned", report_text)
            self.assertIn("- output_shape_compare_relation: spatial_mismatch", report_text)
            self.assertIn("- output_shape_compare_common_shape: [1, 3, 249, 249]", report_text)

    def test_fail_policy_stops_on_output_shape_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            env_file = temp_dir / "fail.env"
            baseline_script = temp_dir / "baseline.sh"
            current_script = temp_dir / "current.sh"
            run_id = "unit_inference_shape_fail"
            write_payload_script(baseline_script, output_shape=[1, 3, 249, 249])
            write_payload_script(current_script, output_shape=[1, 3, 256, 256])
            write_benchmark_env(
                env_file,
                log_dir=log_dir,
                report_dir=report_dir,
                run_id=run_id,
                policy="fail",
                baseline_script=baseline_script,
                current_script=current_script,
            )

            completed = subprocess.run(
                ["bash", str(BENCHMARK_RUNNER), "--env", str(env_file)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            report_text = (report_dir / f"{run_id}.md").read_text(encoding="utf-8")
            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            self.assertIn("ERROR: Baseline/current output shape mismatch under policy=fail", completed.stderr)
            self.assertIn("Inference benchmark failed in output-shape gate", completed.stdout)
            self.assertIn("- status: failed_output_shape_mismatch", report_text)
            self.assertIn("- output_shape_compare_policy: fail", report_text)
            self.assertIn("- output_shape_compare_status: mismatch_failed", report_text)
            self.assertIn("- output_shape_compare_relation: spatial_mismatch", report_text)


if __name__ == "__main__":
    unittest.main()
