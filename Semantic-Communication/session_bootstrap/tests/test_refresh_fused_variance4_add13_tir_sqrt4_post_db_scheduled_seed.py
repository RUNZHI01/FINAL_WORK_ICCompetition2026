from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location(
    "refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed",
    SCRIPT_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RefreshFusedVariance4Add13TirSqrt4PostDbScheduledSeedTest(unittest.TestCase):
    def test_main_invokes_seam_probe_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            task_summary = temp_dir / "task_summary.json"
            database_dir = temp_dir / "db"
            output_dir = temp_dir / "checked_in"
            output_json = temp_dir / "summary.json"
            task_summary.write_text("{}\n", encoding="utf-8")
            database_dir.mkdir()

            report = {
                "operator": module.OPERATOR_NAME,
                "task_summary_json": str(task_summary),
                "database_dir": str(database_dir),
                "recommended_seam": {"seam_id": "post_database_scheduled_primfunc_swap"},
                "standalone_scheduled_task_build": {"status": "missing_scheduled_ir_module"},
                "post_database_apply": {"operator_present": True},
                "post_db_scheduled_seed": {
                    "requested": True,
                    "status": "written",
                    "reference_tir_path": str(
                        output_dir
                        / "fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py"
                    ),
                    "manifest_path": str(
                        output_dir / "post_db_scheduled_reference_seed_manifest.json"
                    ),
                },
            }
            run_calls: list[list[str]] = []
            fake_python = temp_dir / "fake-python"
            fake_python.write_text("#!/bin/sh\n", encoding="utf-8")

            def fake_run(argv, check, capture_output, text):
                self.assertFalse(check)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                run_calls.append(list(argv))
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps(report),
                    stderr="",
                )

            stdout = io.StringIO()
            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                with contextlib.redirect_stdout(stdout):
                    rc = module.main(
                        [
                            "--task-summary",
                            str(task_summary),
                            "--database-dir",
                            str(database_dir),
                            "--output-dir",
                            str(output_dir),
                            "--output-json",
                            str(output_json),
                            "--python-executable",
                            str(fake_python),
                        ]
                    )

            self.assertEqual(rc, 0)
            self.assertEqual(
                run_calls,
                [[
                    str(fake_python),
                    str(Path(module.seam_probe.__file__).resolve()),
                    "--task-summary",
                    str(task_summary),
                    "--database-dir",
                    str(database_dir),
                    "--operator",
                    module.OPERATOR_NAME,
                    "--skip-handwritten-candidate",
                    "--build-standalone-scheduled-task",
                    "--scheduled-seed-dir",
                    str(output_dir),
                ]],
            )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["diagnostic_only"])
            self.assertTrue(payload["local_only"])
            self.assertEqual(
                payload["post_db_scheduled_seed"]["reference_tir_path"],
                report["post_db_scheduled_seed"]["reference_tir_path"],
            )
            self.assertEqual(
                json.loads(output_json.read_text(encoding="utf-8"))["status"],
                "ok",
            )

    def test_main_requires_allow_overwrite_for_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "checked_in"
            output_dir.mkdir()
            (
                output_dir
                / "fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py"
            ).write_text("# existing\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as ctx:
                module.main(["--output-dir", str(output_dir)])
            self.assertIn("allow-overwrite", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
