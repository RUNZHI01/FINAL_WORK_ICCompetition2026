from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "inspect_baseline_lineage.py"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class InspectBaselineLineageTest(unittest.TestCase):
    def write_compare_fixture(self, temp_dir: Path) -> tuple[Path, Path, Path]:
        compare_env = temp_dir / "compare.env"
        compare_log = temp_dir / "compare.log"
        rebuild_report = temp_dir / "rebuild.json"

        write_text(
            compare_env,
            textwrap.dedent(
                """\
                REMOTE_TVM_PYTHON='env /opt/current-safe/bin/python'
                INFERENCE_EXECUTION_ID=unit_compare
                INFERENCE_BASELINE_ARCHIVE=/remote/baseline
                INFERENCE_CURRENT_ARCHIVE=/remote/current
                INFERENCE_BASELINE_CMD='REMOTE_TVM_PYTHON=/opt/compat/bin/python bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline'
                INFERENCE_CURRENT_CMD='bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current'
                """
            ),
        )

        baseline_payload = {
            "variant": "baseline",
            "archive": "/remote/baseline",
            "artifact_path": "/remote/baseline/tvm_tune_logs/optimized_model.so",
            "artifact_sha256": "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
            "artifact_sha256_expected": "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
            "artifact_sha256_match": True,
            "artifact_size_bytes": 1438664,
            "tvm_version": "0.21.dev0",
            "device": "cpu(0)",
            "output_shape": [1, 3, 249, 249],
            "output_dtype": "float32",
        }
        current_payload = {
            "variant": "current",
            "archive": "/remote/current",
            "artifact_path": "/remote/current/tvm_tune_logs/optimized_model.so",
            "artifact_sha256": "1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644",
            "artifact_sha256_expected": "1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644",
            "artifact_sha256_match": True,
            "artifact_size_bytes": 1653592,
            "tvm_version": "0.24.dev0",
            "device": "cpu:0",
            "output_shape": [1, 3, 256, 256],
            "output_dtype": "float32",
        }
        write_text(
            compare_log,
            "\n".join(
                [
                    "prefix log line",
                    json.dumps(baseline_payload, ensure_ascii=False),
                    "middle log line",
                    json.dumps(current_payload, ensure_ascii=False),
                ]
            )
            + "\n",
        )

        rebuild_payload = {
            "mode": "baseline-style current rebuild-only + payload-symmetric runtime",
            "report_id": "unit_rebuild",
            "remote_artifact": {
                "archive_dir": "/remote/current",
                "optimized_model_so": "/remote/current/tvm_tune_logs/optimized_model.so",
                "optimized_model_sha256": "75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080",
                "optimized_model_size_bytes": 1675320,
                "hash_match": True,
            },
            "safe_runtime_inference": {
                "remote_tvm_python": "env /opt/current-safe/bin/python",
                "remote_tvm_version": "0.24.dev0",
                "device": "cpu",
                "payload": {
                    "variant": "current",
                    "archive": "/remote/current",
                    "artifact_path": "/remote/current/tvm_tune_logs/optimized_model.so",
                    "artifact_sha256": "75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080",
                    "artifact_sha256_expected": "75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080",
                    "artifact_sha256_match": True,
                    "artifact_size_bytes": 1675320,
                    "tvm_version": "0.24.dev0",
                    "device": "cpu:0",
                    "output_shape": [1, 3, 256, 256],
                    "output_dtype": "float32",
                },
            },
        }
        write_text(rebuild_report, json.dumps(rebuild_payload, indent=2, ensure_ascii=False))
        return compare_env, compare_log, rebuild_report

    def test_extracts_baseline_lineage_and_runtime_guard(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            compare_env, compare_log, rebuild_report = self.write_compare_fixture(temp_dir)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--compare-env",
                    str(compare_env),
                    "--compare-log",
                    str(compare_log),
                    "--current-rebuild-report",
                    str(rebuild_report),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(
                payload["baseline_compare"]["artifact_sha256"],
                "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
            )
            self.assertEqual(
                payload["baseline_compare"]["effective_remote_tvm_python"],
                "/opt/compat/bin/python",
            )
            self.assertEqual(
                payload["current_compare"]["effective_remote_tvm_python"],
                "env /opt/current-safe/bin/python",
            )
            self.assertEqual(payload["runtime_lineage"]["baseline_vs_current_compare"], "compat_vs_current_safe")
            self.assertEqual(payload["baseline_current_safe_probe"]["status"], "not_provided")
            self.assertFalse(payload["lineage_assessment"]["baseline_archive_touched_by_rebuild"])
            self.assertTrue(payload["lineage_assessment"]["current_archive_reused_between_compare_and_rebuild"])
            self.assertTrue(payload["lineage_assessment"]["current_outputs_match_between_compare_and_rebuild"])
            self.assertIn(
                "/remote/baseline/tvm_tune_logs/optimized_model.so",
                payload["lineage_assessment"]["most_likely_249_source"],
            )
            self.assertIn(
                "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
                payload["lineage_assessment"]["most_likely_249_source"],
            )
            self.assertEqual(
                payload["baseline_abi_assessment"]["status"],
                "runtime_line_mismatch_observed",
            )
            self.assertEqual(
                payload["baseline_abi_assessment"]["classification"],
                "inconclusive_without_current_safe_probe",
            )
            self.assertEqual(payload["fair_compare_guard"]["status"], "blocked_runtime_line_mismatch")
            self.assertFalse(payload["fair_compare_guard"]["claim_allowed"])
            self.assertIn("source", payload["next_board_probe"]["command"])
            self.assertIn("--variant baseline", payload["next_board_probe"]["command"])

    def test_classifies_vm_load_executable_probe_failure_as_legacy_compat_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            compare_env, compare_log, rebuild_report = self.write_compare_fixture(temp_dir)
            probe_log = temp_dir / "baseline_current_safe_probe.log"
            write_text(
                probe_log,
                textwrap.dedent(
                    """\
                    LOAD_OK library
                    Traceback (most recent call last):
                      File "<stdin>", line 1, in <module>
                    AttributeError: Module has no function "vm_load_executable"
                    """
                ),
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--compare-env",
                    str(compare_env),
                    "--compare-log",
                    str(compare_log),
                    "--current-rebuild-report",
                    str(rebuild_report),
                    "--baseline-current-safe-probe-log",
                    str(probe_log),
                    "--strict-fair-compare",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(
                payload["baseline_current_safe_probe"]["status"],
                "current_safe_abi_incompatible",
            )
            self.assertEqual(
                payload["baseline_current_safe_probe"]["error_signature"],
                "missing_vm_load_executable",
            )
            self.assertIn(
                "vm_load_executable",
                payload["baseline_current_safe_probe"]["error_excerpt"],
            )
            self.assertEqual(
                payload["baseline_abi_assessment"]["status"],
                "current_safe_abi_incompatible",
            )
            self.assertEqual(
                payload["baseline_abi_assessment"]["classification"],
                "legacy_compat_only",
            )
            self.assertEqual(
                payload["fair_compare_guard"]["status"],
                "blocked_baseline_current_safe_abi_incompatible",
            )
            self.assertFalse(payload["fair_compare_guard"]["claim_allowed"])


if __name__ == "__main__":
    unittest.main()
