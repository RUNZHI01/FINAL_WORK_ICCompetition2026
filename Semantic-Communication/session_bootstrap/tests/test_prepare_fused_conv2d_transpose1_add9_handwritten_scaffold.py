from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "prepare_fused_conv2d_transpose1_add9_handwritten_scaffold.py"
)

spec = importlib.util.spec_from_file_location(
    "prepare_fused_conv2d_transpose1_add9_handwritten_scaffold",
    SCRIPT,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class PrepareFusedConv2dTranspose1Add9HandwrittenScaffoldTest(unittest.TestCase):
    def test_generates_rebuild_validate_and_profile_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            candidate_json = temp_dir / "handwritten_candidates.json"
            rebuild_base_env = temp_dir / "rebuild_base.env"
            validate_base_env = temp_dir / "validate_base.env"
            profile_base_env = temp_dir / "profile_base.env"
            best_staging_db = temp_dir / "best_staging_db"
            output_dir = temp_dir / "scaffold"
            remote_archive = "/tmp/handwritten_fused_conv2d_transpose1_add9"
            sha256_value = "a" * 64

            write_text(
                candidate_json,
                json.dumps(
                    {
                        "current_best_staging": {
                            "artifact_sha256": "5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d",
                            "summary_md": "/tmp/current_best_staging.md",
                        },
                        "current_profile_json": "/tmp/current_profile.json",
                        "reference_profile_json": "/tmp/reference_profile.json",
                        "wave1_candidates": [
                            {
                                "name": "fused_conv2d_transpose1_add9",
                                "priority": 1,
                                "family": "deconv",
                                "current_mean_duration_us": 24275.26,
                                "current_mean_percent": 14.6,
                                "current_argument_shapes": (
                                    "float32[1, 48, 64, 64], "
                                    "float32[48, 24, 3, 3], "
                                    "float32[1, 24, 1, 1], "
                                    "float32[1, 24, 128, 128]"
                                ),
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
            )
            write_text(rebuild_base_env, "TUNE_TOTAL_TRIALS=0\n")
            write_text(validate_base_env, "INFERENCE_CURRENT_EXPECTED_SHA256=old\n")
            write_text(profile_base_env, "INFERENCE_CURRENT_EXPECTED_SHA256=old\n")
            best_staging_db.mkdir(parents=True, exist_ok=True)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = module.main(
                    [
                        "--candidate-json",
                        str(candidate_json),
                        "--rebuild-base-env",
                        str(rebuild_base_env),
                        "--validate-inference-base-env",
                        str(validate_base_env),
                        "--profile-base-env",
                        str(profile_base_env),
                        "--best-staging-db",
                        str(best_staging_db),
                        "--output-dir",
                        str(output_dir),
                        "--remote-archive-dir",
                        remote_archive,
                        "--manual-artifact-sha256",
                        sha256_value,
                    ]
                )

            self.assertEqual(rc, 0)
            result = json.loads(stdout.getvalue())
            preferred_output_dir = "./session_bootstrap/tmp/transpose1_post_db_swap_local_build"
            preferred_artifact_path = (
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/"
                "fused_conv2d_transpose1_add9_post_db_swap.so"
            )
            preferred_report_path = (
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/"
                "fused_conv2d_transpose1_add9_post_db_swap_report.json"
            )
            preferred_sync_command = (
                "python3 ./session_bootstrap/scripts/"
                "sync_transpose1_post_db_local_build_result.py "
                f"--scaffold-dir {output_dir} "
                "--output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build"
            )
            preferred_one_shot_command = (
                "python3 ./session_bootstrap/scripts/"
                "run_transpose1_post_db_local_build_and_sync.py "
                f"--scaffold-dir {output_dir} "
                "--output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build"
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["output_dir"], str(output_dir))
            self.assertEqual(result["preferred_local_build_output_dir"], preferred_output_dir)
            self.assertEqual(result["preferred_local_build_artifact_path"], preferred_artifact_path)
            self.assertEqual(result["preferred_local_build_report_path"], preferred_report_path)

            rebuild_env = (output_dir / "manual_rebuild.env").read_text(encoding="utf-8")
            validate_env = (output_dir / "manual_validate_inference.env").read_text(
                encoding="utf-8"
            )
            profile_env = (output_dir / "manual_profile.env").read_text(encoding="utf-8")
            validation_template = (output_dir / "validation_report_template.md").read_text(
                encoding="utf-8"
            )
            readme = (output_dir / "README.md").read_text(encoding="utf-8")
            latest_snapshot = (
                output_dir / module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME
            ).read_text(encoding="utf-8")
            bookkeeping = json.loads((output_dir / "bookkeeping.json").read_text(encoding="utf-8"))

            self.assertIn(f"source {str(rebuild_base_env)}", rebuild_env)
            self.assertIn(f"TUNE_EXISTING_DB={best_staging_db}", rebuild_env)
            self.assertIn("TUNE_TOTAL_TRIALS=0", rebuild_env)
            self.assertIn(f"REMOTE_TVM_JSCC_BASE_DIR={remote_archive}", rebuild_env)
            self.assertIn("HANDWRITTEN_TARGET_OP=fused_conv2d_transpose1_add9", rebuild_env)
            self.assertIn(
                "prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py",
                rebuild_env,
            )
            self.assertIn("checked-in candidate-v0 module", rebuild_env)

            self.assertIn(f"source {str(validate_base_env)}", validate_env)
            self.assertIn(f"INFERENCE_CURRENT_ARCHIVE={remote_archive}", validate_env)
            self.assertIn(
                f"REMOTE_CURRENT_ARTIFACT={remote_archive}/tvm_tune_logs/optimized_model.so",
                validate_env,
            )
            self.assertIn(f"INFERENCE_CURRENT_EXPECTED_SHA256={sha256_value}", validate_env)

            self.assertIn(f"source {str(profile_base_env)}", profile_env)
            self.assertIn(f"INFERENCE_CURRENT_ARCHIVE={remote_archive}", profile_env)
            self.assertIn(
                f"REMOTE_CURRENT_ARTIFACT={remote_archive}/tvm_tune_logs/optimized_model.so",
                profile_env,
            )
            self.assertIn(f"INFERENCE_CURRENT_EXPECTED_SHA256={sha256_value}", profile_env)

            self.assertEqual(bookkeeping["operator"], "fused_conv2d_transpose1_add9")
            self.assertEqual(bookkeeping["remote_archive_dir"], remote_archive)
            self.assertEqual(
                bookkeeping["default_workflow"],
                [
                    "prepare_manual_hook_overlay",
                    "local_build_and_sync",
                    "validate",
                    "profile",
                ],
            )
            self.assertEqual(
                bookkeeping["local_schedule_preserving_build_output_dir"],
                preferred_output_dir,
            )
            self.assertEqual(
                bookkeeping["preferred_local_post_db_build"]["output_dir"],
                preferred_output_dir,
            )
            self.assertEqual(
                bookkeeping["preferred_local_post_db_build"]["artifact_path"],
                preferred_artifact_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_post_db_build"]["report_path"],
                preferred_report_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_post_db_build"]["artifact_name"],
                "fused_conv2d_transpose1_add9_post_db_swap.so",
            )
            self.assertEqual(
                bookkeeping["preferred_local_post_db_build"]["report_name"],
                "fused_conv2d_transpose1_add9_post_db_swap_report.json",
            )
            self.assertIn(
                "--output-dir only changes the parent directory",
                bookkeeping["preferred_local_post_db_build"]["output_naming_note"],
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_output_dir"],
                preferred_output_dir,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_artifact_path"],
                preferred_artifact_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_report_path"],
                preferred_report_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_output_names"],
                {
                    "artifact": "fused_conv2d_transpose1_add9_post_db_swap.so",
                    "report": "fused_conv2d_transpose1_add9_post_db_swap_report.json",
                },
            )
            self.assertIn(
                "--output-dir only changes the parent directory",
                bookkeeping["preferred_local_build_output_naming_note"],
            )
            self.assertIn("schedule-preserving", bookkeeping["why_local_first"])
            self.assertIn("validation_report_template.md", bookkeeping["generated_files"])
            self.assertEqual(
                bookkeeping["generated_files"][module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME],
                str(output_dir / module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME),
            )
            self.assertIn(
                "run_transpose1_post_db_local_build.py",
                bookkeeping["commands"]["local_schedule_preserving_build"],
            )
            self.assertEqual(
                bookkeeping["commands"]["local_build_and_sync"],
                preferred_one_shot_command,
            )
            self.assertIn(
                "--output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
                bookkeeping["commands"]["local_schedule_preserving_build"],
            )
            self.assertEqual(
                bookkeeping["commands"]["sync_local_build_result"],
                preferred_sync_command,
            )
            self.assertIn(
                "run_phytium_current_safe_one_shot.sh",
                bookkeeping["commands"]["validate"],
            )
            self.assertIn(remote_archive, bookkeeping["commands"]["validate"])
            self.assertIn(
                "run_task_5_1_operator_profile.py",
                bookkeeping["commands"]["profile"],
            )

            self.assertIn("- candidate_sha256: `aaaaaaaa", validation_template)
            self.assertIn(
                f"- local_build_sync_command: `{preferred_sync_command}`",
                validation_template,
            )
            self.assertIn(
                f"- preferred_local_build_output_dir: `{preferred_output_dir}`",
                validation_template,
            )
            self.assertIn(
                f"- preferred_local_build_report_json: `{preferred_report_path}`",
                validation_template,
            )
            self.assertIn(
                f"- preferred_local_build_artifact: `{preferred_artifact_path}`",
                validation_template,
            )
            self.assertIn("- local_build_swap_result: `<fill>`", validation_template)
            self.assertIn(
                "run_transpose1_post_db_local_build.py",
                validation_template,
            )
            self.assertIn(f"- remote_staging_archive: `{remote_archive}`", validation_template)
            self.assertIn("- payload_result: `<fill>`", validation_template)
            self.assertIn("- reprobe_run_id: `<fill>`", validation_template)
            self.assertIn("- decision: `<keep_staging_only|drop>`", validation_template)

            self.assertIn(
                "- snapshot_status: `awaiting_first_local_build_sync`",
                latest_snapshot,
            )
            self.assertIn(f"- report_path: `{preferred_report_path}`", latest_snapshot)
            self.assertIn(f"- artifact_path: `{preferred_artifact_path}`", latest_snapshot)
            self.assertIn("- artifact_sha256: `<not_synced_yet>`", latest_snapshot)
            self.assertIn(
                "sync_transpose1_post_db_local_build_result.py",
                latest_snapshot,
            )

            self.assertIn("## Default workflow", readme)
            self.assertIn(
                "Run the preferred one-shot local build + sync wrapper",
                readme,
            )
            self.assertIn("The one-shot wrapper is still local-only and diagnostic-only", readme)
            self.assertIn("manual_hook_overlay.env` is hook wiring only", readme)
            self.assertIn(preferred_artifact_path, readme)
            self.assertIn(preferred_report_path, readme)
            self.assertIn("latest_local_build_sync_snapshot.md", readme)
            self.assertIn("Preferred local build artifact", readme)
            self.assertIn("Preferred local build report", readme)
            self.assertIn("Latest local build+sync snapshot", readme)
            self.assertIn("Wrapper output naming note", readme)
            self.assertIn("run_transpose1_post_db_local_build_and_sync.py", readme)
            self.assertIn("sync_transpose1_post_db_local_build_result.py", readme)
            self.assertIn("run_phytium_current_safe_one_shot.sh", readme)
            self.assertIn("run_task_5_1_operator_profile.py", readme)
            self.assertIn("validation_report_template.md", readme)
            self.assertIn(
                "prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py",
                readme,
            )
            self.assertIn("manual_hook_overlay.env", readme)
            self.assertIn("checked-in candidate-v0 module", readme)
            self.assertIn(
                "capture_fused_conv2d_transpose1_add9_manual_seed.sh",
                readme,
            )
            self.assertIn(
                "run_transpose1_post_db_local_build.py",
                readme,
            )
            self.assertIn(
                "The sync helper only records local build facts; it does not claim runtime or performance validity.",
                readme,
            )
            self.assertIn(
                "transpose1_post_db_swap_local_build",
                readme,
            )
            self.assertIn("## Optional staging validation", readme)
            self.assertIn("## Optional runtime reprobe", readme)
            self.assertIn("rpc_tune.py` already consumes `TVM_HANDWRITTEN_IMPL_PATH`", readme)


if __name__ == "__main__":
    unittest.main()
