from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "check_baseline_fair_compare_guard.py"
INSPECTOR_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "inspect_baseline_lineage.py"

spec = importlib.util.spec_from_file_location("check_baseline_fair_compare_guard", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_compare_fixture(
    project_root: Path,
    *,
    fixture_id: str,
    baseline_runtime_command: str,
    current_runtime_command: str,
    compare_env_name: str,
    rebuild_report_name: str,
) -> tuple[Path, Path, Path]:
    compare_env = project_root / "session_bootstrap" / "tmp" / compare_env_name
    compare_log = project_root / "session_bootstrap" / "logs" / f"{fixture_id}.log"
    rebuild_report = project_root / "session_bootstrap" / "reports" / rebuild_report_name

    write_text(
        compare_env,
        "\n".join(
            [
                "REMOTE_TVM_PYTHON='env /opt/current-safe/bin/python'",
                f"INFERENCE_EXECUTION_ID={fixture_id}",
                "INFERENCE_BASELINE_ARCHIVE=/remote/baseline",
                "INFERENCE_CURRENT_ARCHIVE=/remote/current",
                f"INFERENCE_BASELINE_CMD={baseline_runtime_command!r}",
                f"INFERENCE_CURRENT_CMD={current_runtime_command!r}",
            ]
        )
        + "\n",
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
        "report_id": fixture_id,
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


class CheckBaselineFairCompareGuardTest(unittest.TestCase):
    def capture_main(
        self,
        project_root: Path,
        argv: list[str] | None = None,
    ) -> tuple[int, str, str]:
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            rc = module.main(
                argv or [],
                project_root=project_root,
                inspector_script=INSPECTOR_SCRIPT,
            )
        return rc, stdout_buffer.getvalue(), stderr_buffer.getvalue()

    def test_uses_latest_defaults_and_auto_probe_for_blocked_verdict(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            write_compare_fixture(
                project_root,
                fixture_id="older_run",
                baseline_runtime_command=(
                    "REMOTE_TVM_PYTHON=/opt/compat/bin/python "
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline"
                ),
                current_runtime_command=(
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current"
                ),
                compare_env_name="inference_compare_scheme_a_fair_run_fixed_20260320_1700.env",
                rebuild_report_name="phytium_baseline_style_current_rebuild_20260320_1700.json",
            )
            write_text(
                project_root
                / "session_bootstrap"
                / "reports"
                / "baseline_current_safe_probe_20260320_1700.log",
                "RUN_OK [1, 3, 256, 256] float32\n",
            )

            newer_compare_env, _, newer_rebuild_report = write_compare_fixture(
                project_root,
                fixture_id="newer_run",
                baseline_runtime_command=(
                    "REMOTE_TVM_PYTHON=/opt/compat/bin/python "
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline"
                ),
                current_runtime_command=(
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current"
                ),
                compare_env_name="inference_compare_scheme_a_fair_run_fixed_20260320_1800.env",
                rebuild_report_name="phytium_baseline_style_current_rebuild_20260320_1800.json",
            )
            newer_probe_log = (
                project_root
                / "session_bootstrap"
                / "reports"
                / "baseline_current_safe_probe_20260320_1800.log"
            )
            write_text(
                newer_probe_log,
                "\n".join(
                    [
                        "LOAD_OK library",
                        "Traceback (most recent call last):",
                        'AttributeError: Module has no function "vm_load_executable"',
                    ]
                )
                + "\n",
            )

            rc, stdout, stderr = self.capture_main(project_root)

            self.assertEqual(rc, 2, msg=stderr)
            self.assertEqual(stderr, "")
            self.assertIn(
                "guard: blocked_baseline_current_safe_abi_incompatible (claim_allowed=false, exit=2)",
                stdout,
            )
            self.assertIn("baseline: legacy_compat_only [baseline=legacy/compat-only]", stdout)
            self.assertIn(
                "probe/runtime: current_safe_abi_incompatible / compat_vs_current_safe",
                stdout,
            )
            self.assertIn(
                "compare_env: session_bootstrap/tmp/"
                + newer_compare_env.name,
                stdout,
            )
            self.assertIn(
                "rebuild_report: session_bootstrap/reports/" + newer_rebuild_report.name,
                stdout,
            )
            self.assertIn(
                "probe_log: session_bootstrap/reports/" + newer_probe_log.name,
                stdout,
            )

    def test_allows_same_runtime_verdict_without_probe_when_auto_probe_disabled(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            compare_env, compare_log, rebuild_report = write_compare_fixture(
                project_root,
                fixture_id="allowed_run",
                baseline_runtime_command=(
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline"
                ),
                current_runtime_command=(
                    "bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current"
                ),
                compare_env_name="compare.env",
                rebuild_report_name="rebuild.json",
            )

            rc, stdout, stderr = self.capture_main(
                project_root,
                [
                    "--compare-env",
                    str(compare_env),
                    "--compare-log",
                    str(compare_log),
                    "--current-rebuild-report",
                    str(rebuild_report),
                    "--no-auto-probe",
                ],
            )

            self.assertEqual(rc, 0, msg=stderr)
            self.assertEqual(stderr, "")
            self.assertIn("guard: allowed (claim_allowed=true, exit=0)", stdout)
            self.assertIn("baseline: inconclusive [baseline=unclassified]", stdout)
            self.assertIn("probe/runtime: not_provided / same_runtime_line", stdout)
            self.assertIn("probe_log: none", stdout)


if __name__ == "__main__":
    unittest.main()
