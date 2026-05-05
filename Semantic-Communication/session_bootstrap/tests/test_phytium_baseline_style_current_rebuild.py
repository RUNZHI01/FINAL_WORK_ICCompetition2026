from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_RUNNER = PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_phytium_baseline_style_current_rebuild.sh"

EXPECTED_BASELINE_CMD = "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline"
EXPECTED_CURRENT_CMD = "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current"


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


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_rebuild_env(path: Path, *, total_trials: int) -> None:
    write_text(path, f"TUNE_TOTAL_TRIALS={total_trials}\n")


def write_inference_env(
    path: Path,
    *,
    remote_mode: str = "ssh",
    baseline_cmd: str = EXPECTED_BASELINE_CMD,
    current_cmd: str = EXPECTED_CURRENT_CMD,
) -> None:
    write_text(
        path,
        "\n".join(
            [
                f"REMOTE_MODE={remote_mode}",
                f"INFERENCE_BASELINE_CMD={baseline_cmd!r}",
                f"INFERENCE_CURRENT_CMD={current_cmd!r}",
            ]
        )
        + "\n",
    )


def write_fake_one_shot_script(path: Path) -> None:
    write_text(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -Eeuo pipefail
            python3 - "$@" <<'PY'
            import json
            import os
            import sys

            keys = [
                "PHYTIUM_ONE_SHOT_REPORT_PREFIX",
                "PHYTIUM_ONE_SHOT_REPORT_TITLE",
                "PHYTIUM_ONE_SHOT_START_LABEL",
                "PHYTIUM_ONE_SHOT_COMPLETE_LABEL",
                "PHYTIUM_ONE_SHOT_MODE_LOG_DESCRIPTION",
                "PHYTIUM_ONE_SHOT_MODE_REBUILD_DESCRIPTION",
                "PHYTIUM_ONE_SHOT_MODE_INCREMENTAL_DESCRIPTION",
                "PHYTIUM_ONE_SHOT_INFERENCE_SECTION_TITLE",
                "PHYTIUM_ONE_SHOT_INFERENCE_RUNTIME_LABEL",
            ]
            print(json.dumps(
                {
                    "args": sys.argv[1:],
                    "env": {key: os.environ.get(key) for key in keys},
                },
                ensure_ascii=False,
            ))
            PY
            """
        ),
    )


class PhytiumBaselineStyleCurrentRebuildTest(unittest.TestCase):
    def test_rejects_nonzero_rebuild_trials(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            rebuild_env = temp_dir / "rebuild.env"
            inference_env = temp_dir / "inference.env"
            write_rebuild_env(rebuild_env, total_trials=1)
            write_inference_env(inference_env)

            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER_RUNNER),
                    "--rebuild-env",
                    str(rebuild_env),
                    "--inference-env",
                    str(inference_env),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TUNE_TOTAL_TRIALS=0", result.stderr)

    def test_rejects_legacy_compat_inference_command(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            rebuild_env = temp_dir / "rebuild.env"
            inference_env = temp_dir / "inference.env"
            write_rebuild_env(rebuild_env, total_trials=0)
            write_inference_env(
                inference_env,
                baseline_cmd="bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline",
            )

            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER_RUNNER),
                    "--rebuild-env",
                    str(rebuild_env),
                    "--inference-env",
                    str(inference_env),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy compat flow", result.stderr)

    def test_rejects_non_ssh_remote_mode(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            rebuild_env = temp_dir / "rebuild.env"
            inference_env = temp_dir / "inference.env"
            write_rebuild_env(rebuild_env, total_trials=0)
            write_inference_env(inference_env, remote_mode="local")

            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER_RUNNER),
                    "--rebuild-env",
                    str(rebuild_env),
                    "--inference-env",
                    str(inference_env),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("REMOTE_MODE=ssh expected", result.stderr)

    def test_delegates_to_one_shot_with_fair_path_labels_and_args(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            rebuild_env = temp_dir / "rebuild.env"
            inference_env = temp_dir / "inference.env"
            fake_one_shot = temp_dir / "fake_one_shot.sh"
            write_rebuild_env(rebuild_env, total_trials=0)
            write_inference_env(inference_env)
            write_fake_one_shot_script(fake_one_shot)

            env = os.environ.copy()
            env["PHYTIUM_BASELINE_STYLE_ONE_SHOT_SCRIPT"] = str(fake_one_shot)

            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER_RUNNER),
                    "--rebuild-env",
                    str(rebuild_env),
                    "--inference-env",
                    str(inference_env),
                    "--target",
                    '{"kind":"llvm"}',
                    "--output-dir",
                    "/tmp/fair-output",
                    "--remote-archive-dir",
                    "/tmp/remote-archive",
                    "--report-id",
                    "unit_fair_rebuild",
                    "--repeat",
                    "7",
                    "--warmup-runs",
                    "3",
                    "--entry",
                    "main",
                    "--upload-db",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = parse_last_json(result.stdout)
            self.assertEqual(
                payload["args"],
                [
                    "--rebuild-env",
                    str(rebuild_env),
                    "--inference-env",
                    str(inference_env),
                    "--target",
                    '{"kind":"llvm"}',
                    "--output-dir",
                    "/tmp/fair-output",
                    "--remote-archive-dir",
                    "/tmp/remote-archive",
                    "--report-id",
                    "unit_fair_rebuild",
                    "--repeat",
                    "7",
                    "--warmup-runs",
                    "3",
                    "--entry",
                    "main",
                    "--upload-db",
                ],
            )
            self.assertEqual(
                payload["env"]["PHYTIUM_ONE_SHOT_REPORT_PREFIX"],
                "phytium_baseline_style_current_rebuild",
            )
            self.assertEqual(
                payload["env"]["PHYTIUM_ONE_SHOT_INFERENCE_SECTION_TITLE"],
                "Payload-Symmetric Inference",
            )
            self.assertEqual(
                payload["env"]["PHYTIUM_ONE_SHOT_INFERENCE_RUNTIME_LABEL"],
                "payload-symmetric runtime path: load_module() once -> VM init once -> warmup -> repeated main()",
            )
            self.assertEqual(
                payload["env"]["PHYTIUM_ONE_SHOT_MODE_LOG_DESCRIPTION"],
                "baseline-style current rebuild-only + payload-symmetric runtime",
            )


if __name__ == "__main__":
    unittest.main()
