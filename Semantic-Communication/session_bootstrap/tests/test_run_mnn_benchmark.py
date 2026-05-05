from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_mnn_benchmark.sh"


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


def resolve_python_with_numpy() -> str | None:
    candidates = [sys.executable, "python3", "/usr/bin/python3"]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        completed = subprocess.run(
            [candidate, "-c", "import numpy; print('ok')"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return candidate
    return None


def write_mock_inputs(input_dir: Path, count: int) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    python_with_numpy = resolve_python_with_numpy()
    if python_with_numpy is None:
        raise unittest.SkipTest("no local Python with numpy is available")
    subprocess.run(
        [
            python_with_numpy,
            "-c",
            (
                "import numpy as np, pathlib, sys; "
                "root = pathlib.Path(sys.argv[1]); "
                "count = int(sys.argv[2]); "
                "root.mkdir(parents=True, exist_ok=True); "
                "[(np.save(root / f'sample_{i:03d}.npy', np.full((1,32,32,32), fill_value=(i+1)/10.0, dtype=np.float32))) for i in range(count)]"
            ),
            str(input_dir),
            str(count),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def write_mock_artifact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


class RunMnnBenchmarkWrapperTest(unittest.TestCase):
    def test_local_dry_run_generates_matrix_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            python_with_numpy = resolve_python_with_numpy()
            if python_with_numpy is None:
                self.skipTest("no local Python with numpy is available")
            temp_dir = Path(temp_dir_raw)
            log_dir = temp_dir / "logs"
            report_dir = temp_dir / "reports"
            input_dir = temp_dir / "inputs"
            output_base = temp_dir / "outputs"
            env_file = temp_dir / "mnn.env"
            fp32_model = temp_dir / "models" / "decoder_fp32.mnn"
            fp16_model = temp_dir / "models" / "decoder_fp16.mnn"
            write_mock_inputs(input_dir, count=4)
            write_mock_artifact(fp32_model, b"fp32")
            write_mock_artifact(fp16_model, b"fp16")

            env_file.write_text(
                "\n".join(
                    [
                        f"LOG_DIR={shlex.quote(str(log_dir))}",
                        f"REPORT_DIR={shlex.quote(str(report_dir))}",
                        "REMOTE_MODE=local",
                        f"REMOTE_MNN_PYTHON={shlex.quote(python_with_numpy)}",
                        f"REMOTE_INPUT_DIR={shlex.quote(str(input_dir))}",
                        f"REMOTE_OUTPUT_BASE={shlex.quote(str(output_base))}",
                        "REMOTE_SNR_CURRENT=10",
                        f"MNN_FP32_MODEL={shlex.quote(str(fp32_model))}",
                        f"MNN_FP16_MODEL={shlex.quote(str(fp16_model))}",
                        "MNN_INTERPRETER_COUNTS=1,2",
                        "MNN_THREAD_COUNTS=1",
                        "MNN_PRECISIONS=normal",
                        "MNN_SHAPE_MODES=dynamic",
                        "MNN_WARMUP_INPUTS=1",
                        "MNN_MAX_INPUTS=4",
                        "MNN_SEED=0",
                        "MNN_QUALITY_MODE=off",
                        "MNN_MOCK_INFER_MS=5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "bash",
                    str(WRAPPER),
                    "--env",
                    str(env_file),
                    "--run-id",
                    "unit_mnn_matrix",
                    "--allow-overwrite",
                    "--dry-run",
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["run_id"], "unit_mnn_matrix")
            self.assertEqual(payload["config_count"], 4)
            self.assertEqual(payload["ok_count"], 4)
            self.assertTrue((report_dir / "unit_mnn_matrix.json").is_file())
            self.assertTrue((report_dir / "unit_mnn_matrix.md").is_file())
            self.assertTrue((report_dir / "unit_mnn_matrix_raw.jsonl").is_file())
            self.assertIsNotNone(payload["best_overall"])


if __name__ == "__main__":
    unittest.main()
