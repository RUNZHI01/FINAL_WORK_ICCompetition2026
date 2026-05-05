from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy.py"
)

spec = importlib.util.spec_from_file_location(
    "refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy",
    SCRIPT_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RefreshFusedVariance4Add13TirSqrt4ScheduledFormWorkingCopyTest(
    unittest.TestCase
):
    def test_main_writes_distinct_working_copy_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "checked_in"
            reference_tir = (
                output_dir
                / "fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py"
            )
            reference_manifest = (
                output_dir / "post_db_scheduled_reference_seed_manifest.json"
            )
            write_text(
                reference_tir,
                "\n".join(
                    [
                        "# scheduled reference header",
                        "from tvm.script import ir as I",
                        "from tvm.script import tir as T",
                        "",
                        "@I.ir_module",
                        "class Module:",
                        "    @T.prim_func",
                        "    def fused_variance4_add13_tir_sqrt4():",
                        "        T.func_attr({\"tir.noalias\": True})",
                        "        T.evaluate(0)",
                        "",
                    ]
                ),
            )
            write_text(
                reference_manifest,
                json.dumps(
                    {
                        "operator": "fused_variance4_add13_tir_sqrt4",
                        "phase": "post_db_meta_schedule_apply",
                        "seed_capture_kind": "post_db_schedule_preserving_reference_seed",
                        "source": {"source_seam_id": "post_database_scheduled_primfunc_swap"},
                        "task_rows": {
                            "task_summary_row": {"rank": 26},
                            "reconstructed_task_row": {"rank": 26},
                        },
                    },
                    indent=2,
                )
                + "\n",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = module.main(
                    [
                        "--reference-tir",
                        str(reference_tir),
                        "--reference-manifest",
                        str(reference_manifest),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            self.assertEqual(rc, 0)

            result = json.loads(stdout.getvalue())
            working_copy_tir_path = (
                output_dir
                / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy_tir.py"
            )
            working_copy_manifest_path = (
                output_dir / "scheduled_form_candidate_v1_working_copy_manifest.json"
            )
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["local_only"])
            self.assertTrue(result["diagnostic_only"])
            self.assertEqual(result["working_copy_tir_path"], str(working_copy_tir_path))
            self.assertEqual(
                result["working_copy_manifest_path"], str(working_copy_manifest_path)
            )

            working_copy_tir = working_copy_tir_path.read_text(encoding="utf-8")
            working_copy_manifest = json.loads(
                working_copy_manifest_path.read_text(encoding="utf-8")
            )

            self.assertIn("Editable scheduled-form candidate v1 working copy", working_copy_tir)
            self.assertIn("checked-in scheduled reference seed", working_copy_tir)
            self.assertIn("start here for variance4 scheduled-form handwritten edits", working_copy_tir)
            self.assertIn("from tvm.script import ir as I", working_copy_tir)
            self.assertIn("tir.noalias", working_copy_tir)

            self.assertEqual(
                working_copy_manifest["working_copy_role"],
                "editable_scheduled_form_candidate_v1_working_copy",
            )
            self.assertEqual(
                working_copy_manifest["working_copy_contract"]["path_kind"],
                "diagnostic_scheduled_form_candidate_v1_working_copy",
            )
            self.assertFalse(
                working_copy_manifest["working_copy_contract"]["performance_claims"]
            )
            self.assertEqual(
                working_copy_manifest["source_reference_seed"][
                    "reference_seed_capture_kind"
                ],
                "post_db_schedule_preserving_reference_seed",
            )
            self.assertEqual(
                working_copy_manifest["related_files"]["scheduled_reference_tir"],
                str(reference_tir),
            )
            self.assertEqual(
                working_copy_manifest["related_files"]["scheduled_reference_manifest"],
                str(reference_manifest),
            )

    def test_main_requires_allow_overwrite_for_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "checked_in"
            output_dir.mkdir()
            write_text(
                output_dir
                / "fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py",
                "from tvm.script import ir as I\nfrom tvm.script import tir as T\n",
            )
            write_text(
                output_dir / "post_db_scheduled_reference_seed_manifest.json",
                json.dumps({"operator": "fused_variance4_add13_tir_sqrt4"}) + "\n",
            )
            write_text(
                output_dir
                / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy_tir.py",
                "# existing\n",
            )

            with self.assertRaises(SystemExit) as ctx:
                module.main(["--output-dir", str(output_dir)])
            self.assertIn("allow-overwrite", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
