from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_remote_mnn_reconstruction.sh"


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
            [
                candidate,
                "-c",
                "import numpy; print('ok')",
            ],
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


def write_mock_artifact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mock-mnn-artifact")


class RunRemoteMnnReconstructionTest(unittest.TestCase):
    def test_local_dry_run_emits_summary_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "model.mnn"
            input_dir = temp_dir / "inputs"
            output_base = temp_dir / "outputs"
            write_mock_artifact(artifact_path)
            write_mock_inputs(input_dir, count=3)

            python_with_numpy = resolve_python_with_numpy()
            if python_with_numpy is None:
                self.skipTest("no local Python with numpy is available")

            env = {
                **dict(os.environ),
                "REMOTE_MODE": "local",
                "REMOTE_MNN_PYTHON": python_with_numpy,
                "REMOTE_INPUT_DIR": str(input_dir),
                "REMOTE_OUTPUT_BASE": str(output_base),
                "REMOTE_SNR_CURRENT": "10",
            }

            completed = subprocess.run(
                [
                    "bash",
                    str(RUNNER),
                    "--variant",
                    "current",
                    "--model-path",
                    str(artifact_path),
                    "--output-prefix",
                    "unit_mnn_outputs",
                    "--max-inputs",
                    "3",
                    "--interpreter-count",
                    "2",
                    "--session-threads",
                    "4",
                    "--precision",
                    "low",
                    "--shape-mode",
                    "dynamic",
                    "--warmup-inputs",
                    "1",
                    "--dry-run",
                    "--mock-infer-ms",
                    "5",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = parse_last_json(completed.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["processed_count"], 2)
            self.assertEqual(payload["warmup_count"], 1)
            self.assertEqual(payload["interpreter_count"], 2)
            self.assertTrue((output_base / "unit_mnn_outputs" / "summary.json").is_file())
            self.assertTrue((output_base / "unit_mnn_outputs" / "summary.md").is_file())


if __name__ == "__main__":
    unittest.main()
