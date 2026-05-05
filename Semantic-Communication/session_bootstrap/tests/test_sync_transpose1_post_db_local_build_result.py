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
    / "sync_transpose1_post_db_local_build_result.py"
)

spec = importlib.util.spec_from_file_location(
    "sync_transpose1_post_db_local_build_result",
    SCRIPT,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SyncTranspose1PostDbLocalBuildResultTest(unittest.TestCase):
    def test_sync_updates_scaffold_files_from_local_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            scaffold_dir = temp_dir / "scaffold"
            output_dir = temp_dir / "local_build"
            output_dir.mkdir(parents=True)

            artifact_path = output_dir / "fused_conv2d_transpose1_add9_post_db_swap.so"
            artifact_path.write_bytes(b"fake-post-db-artifact\n")
            artifact_sha = module.file_sha256(artifact_path)
            report_path = output_dir / "fused_conv2d_transpose1_add9_post_db_swap_report.json"
            write_text(
                report_path,
                json.dumps(
                    {
                        "operator": module.OPERATOR_NAME,
                        "post_db_scheduled_swap": {
                            "swap_succeeded": True,
                            "build_status": "built",
                        },
                        "local_build_output": {
                            "output_dir": str(output_dir),
                            "artifact_path": str(artifact_path),
                            "report_path": str(report_path),
                            "artifact_exists": True,
                            "artifact_size_bytes": artifact_path.stat().st_size,
                            "export_status": "exported",
                        },
                    },
                    indent=2,
                )
                + "\n",
            )

            bookkeeping_json = scaffold_dir / "bookkeeping.json"
            validation_template = scaffold_dir / "validation_report_template.md"
            validate_env = scaffold_dir / "manual_validate_inference.env"
            profile_env = scaffold_dir / "manual_profile.env"

            write_text(
                bookkeeping_json,
                json.dumps(
                    {
                        "operator": module.OPERATOR_NAME,
                        "commands": {
                            "local_schedule_preserving_build": "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir ./old/out"
                        },
                        "preferred_local_post_db_build": {
                            "command": "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir ./old/out",
                            "output_dir": "./old/out",
                            "artifact_name": "old.so",
                            "report_name": "old.json",
                            "artifact_path": "./old/out/old.so",
                            "report_path": "./old/out/old.json",
                            "output_naming_note": "old note",
                        },
                    },
                    indent=2,
                )
                + "\n",
            )
            write_text(
                validation_template,
                "\n".join(
                    [
                        "# Validation record: fused_conv2d_transpose1_add9",
                        "- candidate_sha256: `<fill_after_build>`",
                        "- local_build_command: `<fill>`",
                        "- preferred_local_build_output_dir: `<fill>`",
                        "- preferred_local_build_report_json: `<fill>`",
                        "- local_build_swap_result: `<fill>`",
                        "- preferred_local_build_artifact: `<fill>`",
                        "- local_build_notes: `<fill>`",
                    ]
                )
                + "\n",
            )
            write_text(
                validate_env,
                "# Fill INFERENCE_CURRENT_EXPECTED_SHA256 after the handwritten artifact is built and before remote validation/profile.\nINFERENCE_CURRENT_EXPECTED_SHA256=\n",
            )
            write_text(
                profile_env,
                "# Fill INFERENCE_CURRENT_EXPECTED_SHA256 after the handwritten artifact is built and before remote validation/profile.\nINFERENCE_CURRENT_EXPECTED_SHA256=\n",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = module.main(
                    [
                        "--scaffold-dir",
                        str(scaffold_dir),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(rc, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "ok")
            self.assertEqual(
                result["artifact_path"],
                module.repo_native(artifact_path),
            )
            self.assertEqual(result["artifact_sha256"], artifact_sha)
            self.assertEqual(
                result["latest_local_build_sync_snapshot"],
                str(scaffold_dir / module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME),
            )
            self.assertTrue(result["diagnostic_only"])

            bookkeeping = json.loads(bookkeeping_json.read_text(encoding="utf-8"))
            expected_output_dir = module.repo_native(output_dir)
            expected_artifact_path = module.repo_native(artifact_path)
            expected_report_path = module.repo_native(report_path)
            self.assertEqual(bookkeeping["manual_artifact_sha256"], artifact_sha)
            self.assertEqual(
                bookkeeping["preferred_local_build_output_dir"],
                expected_output_dir,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_artifact_path"],
                expected_artifact_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_report_path"],
                expected_report_path,
            )
            self.assertEqual(
                bookkeeping["preferred_local_build_output_names"],
                {
                    "artifact": artifact_path.name,
                    "report": report_path.name,
                },
            )
            self.assertEqual(
                bookkeeping["generated_files"][module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME],
                str(scaffold_dir / module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME),
            )
            self.assertEqual(
                bookkeeping["latest_local_post_db_build"]["build_status"],
                "built",
            )
            self.assertTrue(bookkeeping["latest_local_post_db_build"]["swap_succeeded"])
            self.assertEqual(
                bookkeeping["commands"]["local_build_and_sync"],
                (
                    "python3 ./session_bootstrap/scripts/"
                    "run_transpose1_post_db_local_build_and_sync.py "
                    f"--scaffold-dir {module.repo_native(scaffold_dir)} "
                    f"--output-dir {expected_output_dir}"
                ),
            )
            self.assertEqual(
                bookkeeping["commands"]["local_schedule_preserving_build"],
                f"python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir {expected_output_dir}",
            )
            self.assertIn(
                "run_transpose1_post_db_local_build_and_sync.py",
                bookkeeping["commands"]["local_build_and_sync"],
            )
            self.assertEqual(
                bookkeeping["commands"]["sync_local_build_result"],
                f"python3 ./session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py --scaffold-dir {module.repo_native(scaffold_dir)} --output-dir {expected_output_dir}",
            )

            validation_text = validation_template.read_text(encoding="utf-8")
            self.assertIn(f"- candidate_sha256: `{artifact_sha}`", validation_text)
            self.assertIn(
                f"- local_build_command: `{bookkeeping['commands']['local_schedule_preserving_build']}`",
                validation_text,
            )
            self.assertIn(
                f"- local_build_sync_command: `{bookkeeping['commands']['sync_local_build_result']}`",
                validation_text,
            )
            self.assertIn(
                f"- preferred_local_build_report_json: `{expected_report_path}`",
                validation_text,
            )
            self.assertIn(
                f"- preferred_local_build_artifact: `{expected_artifact_path}`",
                validation_text,
            )
            self.assertIn("swap_succeeded=True, build_status=built, export_status=exported", validation_text)
            self.assertIn(f"artifact_sha256={artifact_sha}", validation_text)

            self.assertIn(
                f"INFERENCE_CURRENT_EXPECTED_SHA256={artifact_sha}",
                validate_env.read_text(encoding="utf-8"),
            )
            self.assertIn(
                f"INFERENCE_CURRENT_EXPECTED_SHA256={artifact_sha}",
                profile_env.read_text(encoding="utf-8"),
            )
            self.assertIn(
                module.SYNC_COMMENT,
                validate_env.read_text(encoding="utf-8"),
            )
            self.assertIn(
                module.SYNC_COMMENT,
                profile_env.read_text(encoding="utf-8"),
            )

            latest_snapshot = (
                scaffold_dir / module.LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME
            ).read_text(encoding="utf-8")
            self.assertIn(
                "- snapshot_status: `synced_local_build_result`",
                latest_snapshot,
            )
            self.assertIn(f"- report_path: `{expected_report_path}`", latest_snapshot)
            self.assertIn(f"- artifact_path: `{expected_artifact_path}`", latest_snapshot)
            self.assertIn(f"- artifact_sha256: `{artifact_sha}`", latest_snapshot)
            self.assertIn("- artifact_exists: `true`", latest_snapshot)
            self.assertIn("- build_status: `built`", latest_snapshot)
            self.assertIn("- swap_succeeded: `true`", latest_snapshot)
            self.assertIn("- export_status: `exported`", latest_snapshot)
            self.assertIn(
                "sync_transpose1_post_db_local_build_result.py",
                latest_snapshot,
            )


if __name__ == "__main__":
    unittest.main()
