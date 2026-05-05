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
    / "run_transpose1_post_db_local_build_and_sync.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location(
    "run_transpose1_post_db_local_build_and_sync",
    SCRIPT_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunTranspose1PostDbLocalBuildAndSyncTest(unittest.TestCase):
    def test_parse_args_defaults_to_local_build_v1_candidate(self) -> None:
        args = module.parse_args([])
        self.assertEqual(args.candidate_impl, module.local_build.DEFAULT_CANDIDATE_IMPL)
        self.assertEqual(
            args.candidate_impl.name,
            "fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py",
        )

    def test_main_runs_build_then_sync_and_emits_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            scaffold_dir = temp_dir / "scaffold"
            task_summary = temp_dir / "task_summary.json"
            database_dir = temp_dir / "db"
            candidate_impl = temp_dir / "candidate_impl.py"
            output_dir = temp_dir / "out"
            task_summary.write_text("{}\n", encoding="utf-8")
            database_dir.mkdir()
            candidate_impl.write_text("# fake candidate\n", encoding="utf-8")

            run_calls: list[list[str]] = []

            def fake_run(argv, check, capture_output, text):
                self.assertFalse(check)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                run_calls.append(list(argv))
                script_name = Path(argv[1]).name
                if script_name == "run_transpose1_post_db_local_build.py":
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        stdout=json.dumps(
                            {
                                "status": "ok",
                                "preferred_local_build_output_dir": str(output_dir),
                                "preferred_local_build_artifact_path": str(output_dir / "artifact.so"),
                                "preferred_local_build_report_path": str(output_dir / "report.json"),
                            }
                        ),
                        stderr="",
                    )
                if script_name == "sync_transpose1_post_db_local_build_result.py":
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        stdout=json.dumps(
                            {
                                "status": "ok",
                                "report_json": str(output_dir / "report.json"),
                                "artifact_path": "./artifact.so",
                                "artifact_sha256": "abc123",
                                "bookkeeping_json": str(scaffold_dir / "bookkeeping.json"),
                                "validation_report_template": str(scaffold_dir / "validation_report_template.md"),
                                "latest_local_build_sync_snapshot": str(
                                    scaffold_dir / "latest_local_build_sync_snapshot.md"
                                ),
                            }
                        ),
                        stderr="",
                    )
                raise AssertionError(f"unexpected script invocation: {argv}")

            output_json = temp_dir / "summary.json"
            fake_python = temp_dir / "fake-python"
            fake_python.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                rc = module.main(
                    [
                        "--scaffold-dir",
                        str(scaffold_dir),
                        "--task-summary",
                        str(task_summary),
                        "--database-dir",
                        str(database_dir),
                        "--candidate-impl",
                        str(candidate_impl),
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
                [
                    [
                        str(fake_python),
                        str(Path(module.local_build.__file__).resolve()),
                        "--task-summary",
                        str(task_summary),
                        "--database-dir",
                        str(database_dir),
                        "--candidate-impl",
                        str(candidate_impl),
                        "--output-dir",
                        str(output_dir),
                    ],
                    [
                        str(fake_python),
                        str(Path(module.sync_result.__file__).resolve()),
                        "--scaffold-dir",
                        str(scaffold_dir),
                        "--output-dir",
                        str(output_dir),
                    ],
                ],
            )
            summary = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "ok")
            self.assertTrue(summary["diagnostic_only"])
            self.assertTrue(summary["local_only"])
            self.assertEqual(summary["scaffold_dir"], module.sync_result.repo_native(scaffold_dir))
            self.assertEqual(summary["artifact_sha256"], "abc123")
            self.assertEqual(summary["report_json"], module.sync_result.repo_native(output_dir / "report.json"))
            self.assertEqual(summary["bookkeeping_json"], module.sync_result.repo_native(scaffold_dir / "bookkeeping.json"))
            self.assertEqual(
                summary["latest_local_build_sync_snapshot"],
                module.sync_result.repo_native(
                    scaffold_dir / "latest_local_build_sync_snapshot.md"
                ),
            )


if __name__ == "__main__":
    unittest.main()
