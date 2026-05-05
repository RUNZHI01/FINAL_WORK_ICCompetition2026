from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "run_transpose1_post_db_local_build.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location(
    "run_transpose1_post_db_local_build",
    SCRIPT_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunTranspose1PostDbLocalBuildTest(unittest.TestCase):
    def test_parse_args_defaults_to_checked_in_v1_candidate(self) -> None:
        args = module.parse_args([])
        self.assertEqual(args.candidate_impl, module.DEFAULT_CANDIDATE_IMPL)
        self.assertEqual(
            args.candidate_impl.name,
            "fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py",
        )

    def test_main_uses_operator_defaults_and_writes_adjacent_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            task_summary = temp_dir / "task_summary.json"
            database_dir = temp_dir / "db"
            candidate_impl = temp_dir / "candidate_impl.py"
            output_dir = temp_dir / "out"
            task_summary.write_text("{}\n", encoding="utf-8")
            database_dir.mkdir()
            candidate_impl.write_text("# fake candidate\n", encoding="utf-8")

            report = {
                "operator": module.seam_probe.DEFAULT_OPERATOR,
                "local_build_output": {
                    "report_path": str(output_dir / "fused_conv2d_transpose1_add9_post_db_swap_report.json")
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

            written: list[tuple[str | None, str | None, str]] = []

            def fake_write_report_outputs(payload, *, output_json, adjacent_report_path):
                written.append(
                    (
                        None if output_json is None else str(output_json),
                        None if adjacent_report_path is None else str(adjacent_report_path),
                        payload,
                    )
                )

            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                with mock.patch.object(module.seam_probe, "write_report_outputs", side_effect=fake_write_report_outputs):
                    rc = module.main(
                        [
                            "--task-summary",
                            str(task_summary),
                            "--database-dir",
                            str(database_dir),
                            "--candidate-impl",
                            str(candidate_impl),
                            "--output-dir",
                            str(output_dir),
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
                    "--candidate-impl",
                    str(candidate_impl),
                    "--build-standalone-scheduled-task",
                    "--output-dir",
                    str(output_dir),
                ]],
            )
            self.assertEqual(len(written), 1)
            self.assertIsNone(written[0][0])
            self.assertEqual(
                written[0][1],
                str(output_dir / "fused_conv2d_transpose1_add9_post_db_swap_report.json"),
            )
            self.assertEqual(json.loads(written[0][2])["operator"], module.seam_probe.DEFAULT_OPERATOR)


if __name__ == "__main__":
    unittest.main()
