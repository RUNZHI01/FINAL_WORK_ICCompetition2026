from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import textwrap
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "refresh_fused_conv2d_transpose1_add9_checked_in_seed.py"
)

spec = importlib.util.spec_from_file_location(
    "refresh_fused_conv2d_transpose1_add9_checked_in_seed",
    SCRIPT,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RefreshFusedConv2dTranspose1Add9CheckedInSeedTest(unittest.TestCase):
    def test_refresh_writes_manifest_readme_and_editable_tir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            seed_json = temp_dir / "seed.json"
            seed_tir = temp_dir / "seed_tir.py"
            task_log = temp_dir / "task.log"
            output_dir = temp_dir / "checked_in"

            write_text(
                seed_json,
                json.dumps(
                    {
                        "operator": "fused_conv2d_transpose1_add9",
                        "reference_staging_sha256": "abc123",
                        "reference_profile_json": "/tmp/profile.json",
                        "argument_shapes": (
                            "float32[1, 48, 64, 64], "
                            "float32[48, 24, 3, 3], "
                            "float32[1, 24, 1, 1], "
                            "float32[1, 24, 128, 128]"
                        ),
                        "phase": "pre_compile",
                        "task_row": {
                            "rank": 16,
                            "task_name": "fused_conv2d_transpose1_add9",
                        },
                        "prim_func_capture": [{"name": "main"}],
                        "seed_capture_kind": "pre_compile_selected_operator_snapshot",
                    },
                    indent=2,
                )
                + "\n",
            )
            write_text(seed_tir, "# captured relax seed\n")
            write_text(
                task_log,
                textwrap.dedent(
                    """\
                    2026-03-31 03:16:06 [INFO] [task_scheduler.cc:172] Initializing Task #0: "fused_conv2d_transpose1_add9"
                    2026-03-31 03:16:06 [INFO] [task_scheduler.cc:45]
                    # from tvm.script import ir as I
                    # from tvm.script import tir as T

                    @I.ir_module
                    class Module:
                        @T.prim_func
                        def main():
                            T.evaluate(0)
                    2026-03-31 03:16:06 [INFO] [multi_level_tiling_with_intrin.cc:57] The workload cannot be tensorized.
                    """
                ),
            )

            rc = module.main(
                [
                    "--seed-json",
                    str(seed_json),
                    "--seed-tir",
                    str(seed_tir),
                    "--task-log",
                    str(task_log),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            self.assertEqual(rc, 0)

            editable_tir = (
                output_dir / "fused_conv2d_transpose1_add9_editable_seed_tir.py"
            ).read_text(encoding="utf-8")
            manifest = json.loads(
                (output_dir / "seed_manifest.json").read_text(encoding="utf-8")
            )
            readme = (output_dir / "README.md").read_text(encoding="utf-8")

            self.assertIn("Checked-in editable seed", editable_tir)
            self.assertIn("from tvm.script import ir as I", editable_tir)
            self.assertIn("class Module:", editable_tir)
            self.assertIn("def main():", editable_tir)

            self.assertEqual(manifest["operator"], "fused_conv2d_transpose1_add9")
            self.assertEqual(manifest["reference_staging_sha256"], "abc123")
            self.assertEqual(manifest["task_row"]["rank"], 16)
            self.assertEqual(
                manifest["source_files"]["captured_seed_json"], str(seed_json)
            )
            self.assertEqual(
                manifest["checked_in_hook_target"],
                str(output_dir / "fused_conv2d_transpose1_add9_manual_candidate.py"),
            )

            self.assertIn("Hook-facing candidate path", readme)
            self.assertIn(
                "refresh_fused_conv2d_transpose1_add9_checked_in_seed.py", readme
            )
            self.assertIn(
                "refresh_fused_conv2d_transpose1_add9_post_db_scheduled_seed.py",
                readme,
            )
            self.assertIn("manual_candidate.py", readme)
            self.assertIn(
                "post_db_scheduled_reference_seed_tir.py",
                readme,
            )
            self.assertIn(
                "post_db_scheduled_reference_seed_manifest.json",
                readme,
            )
            self.assertIn(
                "refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py",
                readme,
            )
            self.assertIn(
                "scheduled_form_candidate_v1_working_copy_tir.py",
                readme,
            )
            self.assertIn(
                "scheduled_form_candidate_v1_working_copy_manifest.json",
                readme,
            )
            self.assertIn("Hook wiring diagnostic through the existing manual hook", readme)
            self.assertIn("Preferred local schedule-preserving build path", readme)
            self.assertIn("run_transpose1_post_db_local_build_and_sync.py", readme)
            self.assertIn("run_transpose1_post_db_local_build.py", readme)
            self.assertIn("transpose1_post_db_swap_local_build", readme)
            self.assertIn(
                "schedule_context_preserving_evaluation",
                readme,
            )


if __name__ == "__main__":
    unittest.main()
