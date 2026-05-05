from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "build_baseline_export_bridge.py"
)

spec = importlib.util.spec_from_file_location("build_baseline_export_bridge", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_workload_record(payload_json: str) -> str:
    raw = (b"\x00" * 8) + payload_json.encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii").rstrip("=")
    return json.dumps(["123", encoded], ensure_ascii=False)


def write_source_db(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    workload_payload = '{"root_index": 1, "nodes": []}'
    write_text(path / "database_workload.json", make_workload_record(workload_payload) + "\n")
    write_text(path / "database_tuning_record.json", '{"record":"baseline"}\n')


def write_rebuild_env(path: Path, *, builder_python: str, onnx_model: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                f"LOCAL_TVM_PYTHON={builder_python}",
                f"TVM_PYTHON={builder_python}",
                f"ONNX_MODEL_PATH={onnx_model}",
                'TARGET={"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72"}',
                "TUNE_INPUT_SHAPE=1,32,32,32",
                "TUNE_INPUT_NAME=input",
                "TUNE_INPUT_DTYPE=float32",
                "TUNE_SESSION_TIMEOUT=120",
                "TUNE_NUM_TRIALS_PER_ITER=64",
                "REMOTE_HOST=100.121.87.73",
                "REMOTE_USER=user",
                "REMOTE_PASS=user",
                "REMOTE_SSH_PORT=22",
                "REMOTE_TVM_PYTHON=env /opt/current-safe/bin/python",
                "REMOTE_TVM_PRIMARY_DIR=/home/user/Downloads/5.1TVM优化结果",
                "REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc",
            ]
        )
        + "\n",
    )


def write_fake_builder(path: Path) -> None:
    write_text(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            from pathlib import Path
            import shutil
            import sys

            args = sys.argv[1:]

            def take(flag):
                idx = args.index(flag)
                return args[idx + 1]

            output_dir = Path(take("--output-dir"))
            existing_db = Path(take("--existing-db"))
            target = take("--target")
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "tuning_logs").mkdir(parents=True, exist_ok=True)
            (output_dir / "optimized_model.so").write_bytes(b"fake-so-bytes")
            shutil.copy2(existing_db / "database_workload.json", output_dir / "tuning_logs" / "database_workload.json")
            shutil.copy2(existing_db / "database_tuning_record.json", output_dir / "tuning_logs" / "database_tuning_record.json")
            (output_dir / "tune_report.json").write_text(
                json.dumps(
                    {
                        "target": target,
                        "runner": "local",
                        "total_trials": 0,
                        "elapsed_sec": 0.5,
                        "tuning_logs_dir": str(output_dir / "tuning_logs"),
                        "task_summary_json": str(output_dir / "task_summary.json"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (output_dir / "task_summary.json").write_text(
                json.dumps(
                    {
                        "raw_import_total_tasks": 1,
                        "tuned_stage_total_tasks": 1,
                        "selected_op_names": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            """
        ),
    )
    path.chmod(0o755)


def write_fake_payload_runner(path: Path) -> None:
    write_text(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -Eeuo pipefail
            archive="${INFERENCE_BASELINE_ARCHIVE:-}"
            if [[ -z "$archive" ]]; then
              echo "missing archive" >&2
              exit 1
            fi
            python3 - "$archive" <<'PY'
            import hashlib
            import json
            import os
            import sys
            from pathlib import Path

            archive = Path(sys.argv[1])
            artifact = archive / "tvm_tune_logs" / "optimized_model.so"
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            print(
                json.dumps(
                    {
                        "variant": "baseline",
                        "archive": str(archive),
                        "artifact_path": str(artifact),
                        "artifact_sha256": digest,
                        "artifact_sha256_expected": os.environ.get("INFERENCE_BASELINE_EXPECTED_SHA256"),
                        "artifact_sha256_match": digest == os.environ.get("INFERENCE_BASELINE_EXPECTED_SHA256"),
                        "tvm_version": "0.24.dev0",
                        "device": "cpu:0",
                        "output_shape": [1, 3, 256, 256],
                        "output_dtype": "float32",
                    },
                    ensure_ascii=False,
                )
            )
            PY
            """
        ),
    )
    path.chmod(0o755)


class BuildBaselineExportBridgeTest(unittest.TestCase):
    def patch_project_root(self, project_root: Path) -> None:
        original_root = module.PROJECT_ROOT
        module.PROJECT_ROOT = project_root
        self.addCleanup(setattr, module, "PROJECT_ROOT", original_root)

    def test_builds_candidate_archive_from_source_archive_and_emits_board_stage_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            self.patch_project_root(project_root)

            source_archive = project_root / "baseline_archive"
            source_db = source_archive / "tuning_logs"
            write_source_db(source_db)

            onnx_model = project_root / "model.onnx"
            write_text(onnx_model, "fake-onnx")
            rebuild_env = project_root / "rebuild.env"
            write_rebuild_env(rebuild_env, builder_python=sys.executable, onnx_model=onnx_model)

            fake_builder = project_root / "fake_rpc_tune.py"
            fake_payload = project_root / "fake_payload_runner.sh"
            write_fake_builder(fake_builder)
            write_fake_payload_runner(fake_payload)

            rc = module.main(
                [
                    "--rebuild-env",
                    str(rebuild_env),
                    "--source-archive",
                    str(source_archive),
                    "--report-id",
                    "unit_baseline_export_bridge",
                    "--output-dir",
                    str(project_root / "output"),
                    "--rpc-tune-script",
                    str(fake_builder),
                    "--payload-runner",
                    str(fake_payload),
                ]
            )

            self.assertEqual(rc, 0)
            summary_path = (
                project_root / "session_bootstrap" / "reports" / "unit_baseline_export_bridge.json"
            )
            board_stage_path = (
                project_root
                / "session_bootstrap"
                / "reports"
                / "unit_baseline_export_bridge_board_stage.sh"
            )
            candidate_root = (
                project_root / "output" / "baseline_candidate_archive"
            )
            self.assertTrue(summary_path.is_file())
            self.assertTrue(board_stage_path.is_file())
            self.assertTrue((candidate_root / "tvm_tune_logs" / "optimized_model.so").is_file())
            self.assertTrue((candidate_root / "tuning_logs" / "database_workload.json").is_file())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["source_lineage"]["source_archive"], str(source_archive))
            self.assertEqual(
                summary["local_current_safe_probe"]["output_shape"],
                [1, 3, 256, 256],
            )
            self.assertTrue(summary["local_current_safe_probe"]["output_contract_match"])
            self.assertIn(
                "/home/user/Downloads/baseline_current_safe_bridge/unit_baseline_export_bridge",
                summary["board_stage"]["remote_archive_dir"],
            )

            board_stage_text = board_stage_path.read_text(encoding="utf-8")
            self.assertIn("run_remote_tvm_inference_payload.sh", board_stage_text)
            self.assertIn("INFERENCE_BASELINE_ARCHIVE", board_stage_text)
            self.assertIn("baseline_current_safe_bridge/unit_baseline_export_bridge", board_stage_text)

    def test_requires_local_source_db_or_archive_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            self.patch_project_root(project_root)

            onnx_model = project_root / "model.onnx"
            write_text(onnx_model, "fake-onnx")
            rebuild_env = project_root / "rebuild.env"
            write_rebuild_env(rebuild_env, builder_python=sys.executable, onnx_model=onnx_model)

            with self.assertRaises(SystemExit) as ctx:
                module.main(
                    [
                        "--rebuild-env",
                        str(rebuild_env),
                    ]
                )

            self.assertIn("no local baseline lineage DB is available", str(ctx.exception))

    def test_rejects_legacy_workload_json_format_before_rpc_tune(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            project_root = Path(temp_dir_raw)
            self.patch_project_root(project_root)

            source_archive = project_root / "baseline_archive"
            source_db = source_archive / "tuning_logs"
            source_db.mkdir(parents=True, exist_ok=True)
            write_text(
                source_db / "database_workload.json",
                '["123","7OQAAAAAAAB7CiAgInJvb3QiOiAxLCAKICAibm9kZXMiOiBbXX0="]\n',
            )
            write_text(source_db / "database_tuning_record.json", '{"record":"baseline"}\n')

            onnx_model = project_root / "model.onnx"
            write_text(onnx_model, "fake-onnx")
            rebuild_env = project_root / "rebuild.env"
            write_rebuild_env(rebuild_env, builder_python=sys.executable, onnx_model=onnx_model)

            with self.assertRaises(SystemExit) as ctx:
                module.main(
                    [
                        "--rebuild-env",
                        str(rebuild_env),
                        "--source-archive",
                        str(source_archive),
                    ]
                )

            self.assertIn("older JSON object-graph format", str(ctx.exception))
            self.assertIn("probe_legacy_baseline_db_bridge.py", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
