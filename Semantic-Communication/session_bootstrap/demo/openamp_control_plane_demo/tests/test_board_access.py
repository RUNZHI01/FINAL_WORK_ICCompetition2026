from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from board_access import (  # noqa: E402
    DEFAULT_INFERENCE_ENV_CANDIDATES,
    apply_trusted_current_artifact_binding,
    build_board_access_config,
    build_demo_default_board_access,
    discover_demo_default_inference_env,
    choose_preloaded_inference_env,
    discover_trusted_baseline_expected_sha,
    discover_trusted_current_artifact_binding,
    discover_trusted_current_local_artifact_source,
    discover_validated_inference_env,
    discover_validated_openamp_remote_project_root,
    first_existing_env,
)


class DemoBoardAccessDefaultsTest(unittest.TestCase):
    def test_discover_validated_inference_env_uses_report_linked_env_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            env_path = temp_root / "trusted.env"
            report_path = temp_root / "trusted.md"
            env_path.write_text("REMOTE_HOST=demo-board\n", encoding="utf-8")
            report_path.write_text(f"- env_file: {env_path}\n", encoding="utf-8")

            discovered = discover_validated_inference_env((str(report_path),))

        self.assertEqual(discovered, env_path.resolve())

    def test_choose_preloaded_inference_env_falls_back_when_report_linked_env_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            incomplete_env = temp_root / "incomplete.env"
            complete_env = temp_root / "complete.env"
            report_path = temp_root / "trusted.md"
            incomplete_env.write_text("REMOTE_HOST=demo-board\n", encoding="utf-8")
            complete_env.write_text(
                "\n".join(
                    [
                        "REMOTE_TVM_PYTHON=/usr/bin/python3",
                        "REMOTE_INPUT_DIR=/tmp/input",
                        "REMOTE_OUTPUT_BASE=/tmp/output",
                        "REMOTE_JSCC_DIR=/tmp/jscc",
                        "REMOTE_SNR_BASELINE=10",
                        "REMOTE_SNR_CURRENT=10",
                        "REMOTE_BATCH_BASELINE=1",
                        "REMOTE_BATCH_CURRENT=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            report_path.write_text(f"- env_file: {incomplete_env}\n", encoding="utf-8")

            selected = choose_preloaded_inference_env((str(report_path),), (str(complete_env),))

        self.assertEqual(selected, complete_env.resolve())

    def test_discover_validated_openamp_remote_project_root_uses_run_manifest_board_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "run_manifest.json"
            manifest_path.write_text(
                json.dumps({"board_access": {"remote_project_root": "/tmp/openamp_demo/project"}}),
                encoding="utf-8",
            )

            discovered = discover_validated_openamp_remote_project_root((str(manifest_path),))

        self.assertEqual(discovered, "/tmp/openamp_demo/project")

    def test_discover_trusted_baseline_expected_sha_requires_matching_artifact_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            matching_report = temp_root / "matching.md"
            mismatched_report = temp_root / "mismatched.md"
            matching_report.write_text(
                "\n".join(
                    [
                        "- baseline_expected_sha256_configured: 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
                        "- baseline_artifact_path: /remote/baseline/tvm_tune_logs/optimized_model.so",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            mismatched_report.write_text(
                "\n".join(
                    [
                        "- baseline_expected_sha256_configured: 9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8",
                        "- baseline_artifact_path: /remote/other/tvm_tune_logs/optimized_model.so",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            discovered = discover_trusted_baseline_expected_sha(
                {"REMOTE_BASELINE_ARTIFACT": "/remote/baseline/tvm_tune_logs/optimized_model.so"},
                (str(mismatched_report), str(matching_report)),
            )

        self.assertEqual(discovered, "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849")

    def test_discover_pytorch_reference_expected_sha_falls_back_to_local_generator_checkpoint(self) -> None:
        access = build_demo_default_board_access(None)

        discovered = access.build_env().get("INFERENCE_BASELINE_EXPECTED_SHA256", "")

        self.assertEqual(discovered, "3afcebc7471695a23bba9448dbc96bf4c07eee84d2ddf5f808501cb583e87763")

    def test_discover_trusted_current_local_artifact_source_uses_matching_sha_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            trusted_local_artifact = temp_root / "trusted_current.so"
            trusted_local_artifact.write_bytes(b"trusted-current")
            matching_report = temp_root / "matching.json"
            mismatched_report = temp_root / "mismatched.json"
            expected_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
            matching_report.write_text(
                json.dumps(
                    {
                        "local_build": {
                            "optimized_model_so": str(trusted_local_artifact),
                            "optimized_model_sha256": expected_sha,
                        },
                        "remote_artifact": {
                            "optimized_model_so": "/remote/current/tvm_tune_logs/optimized_model.so",
                        },
                    }
                ),
                encoding="utf-8",
            )
            mismatched_report.write_text(
                json.dumps(
                    {
                        "local_build": {
                            "optimized_model_so": str(temp_root / "wrong.so"),
                            "optimized_model_sha256": "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849",
                        },
                        "remote_artifact": {
                            "optimized_model_so": "/remote/baseline/tvm_tune_logs/optimized_model.so",
                        },
                    }
                ),
                encoding="utf-8",
            )

            discovered = discover_trusted_current_local_artifact_source(
                {
                    "REMOTE_CURRENT_ARTIFACT": "/remote/current/tvm_tune_logs/optimized_model.so",
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                },
                (str(mismatched_report), str(matching_report)),
            )

        self.assertEqual(discovered, str(trusted_local_artifact.resolve()))

    def test_apply_trusted_current_artifact_binding_rebinds_current_from_baseline_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            trusted_local_artifact = temp_root / "trusted_current.so"
            trusted_local_artifact.write_bytes(b"trusted-current")
            report_path = temp_root / "chunk4.json"
            expected_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
            report_path.write_text(
                json.dumps(
                    {
                        "local_build": {
                            "optimized_model_so": str(trusted_local_artifact),
                            "optimized_model_sha256": expected_sha,
                        },
                        "remote_artifact": {
                            "archive_dir": "/remote/current",
                            "optimized_model_so": "/remote/current/tvm_tune_logs/optimized_model.so",
                            "optimized_model_sha256": expected_sha,
                        },
                    }
                ),
                encoding="utf-8",
            )

            binding = discover_trusted_current_artifact_binding(
                {
                    "REMOTE_CURRENT_ARTIFACT": "/remote/baseline/tvm_tune_logs/optimized_model.so",
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                },
                (str(report_path),),
            )
            corrected = apply_trusted_current_artifact_binding(
                {
                    "REMOTE_CURRENT_ARTIFACT": "/remote/baseline/tvm_tune_logs/optimized_model.so",
                    "REMOTE_TVM_JSCC_BASE_DIR": "/remote/baseline",
                    "REMOTE_CURRENT_ARTIFACT_STAGE_DIR": "/remote/baseline",
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                },
                (str(report_path),),
            )

        self.assertEqual(binding["remote_current_artifact"], "/remote/current/tvm_tune_logs/optimized_model.so")
        self.assertEqual(binding["remote_current_archive_dir"], "/remote/current")
        self.assertEqual(binding["local_current_artifact_source"], str(trusted_local_artifact.resolve()))
        self.assertEqual(corrected["REMOTE_CURRENT_ARTIFACT"], "/remote/current/tvm_tune_logs/optimized_model.so")
        self.assertEqual(corrected["INFERENCE_CURRENT_ARCHIVE"], "/remote/current")
        self.assertEqual(corrected["REMOTE_TVM_JSCC_BASE_DIR"], "/remote/current")
        self.assertEqual(corrected["REMOTE_CURRENT_ARTIFACT_STAGE_DIR"], "/remote/current")
        self.assertEqual(corrected["LOCAL_CURRENT_ARTIFACT_SOURCE"], str(trusted_local_artifact.resolve()))

    def test_demo_defaults_prefill_real_repo_files_without_password(self) -> None:
        access = build_demo_default_board_access(None)
        expected_inference_env = discover_demo_default_inference_env()
        expected_remote_project_root = discover_validated_openamp_remote_project_root()
        expected_torch_pythonpath = str(access.env_file_values.get("REMOTE_TORCH_PYTHONPATH") or "").strip()

        self.assertEqual(access.host, "100.121.87.73")
        self.assertEqual(access.user, "user")
        self.assertEqual(access.port, "22")
        self.assertEqual(
            access.preloaded_ssh_env_file,
            DEMO_ROOT.parents[2] / "session_bootstrap/config/phytium_pi_login.example.env",
        )
        self.assertEqual(
            access.preloaded_inference_env_file,
            expected_inference_env,
        )
        self.assertFalse(access.password)
        self.assertEqual(access.missing_connection_fields(), ["password"])
        self.assertEqual(access.missing_inference_fields("current"), ["password"])
        self.assertEqual(access.missing_inference_fields("baseline"), ["password"])
        self.assertNotIn("REMOTE_PASS", access.env_values)
        self.assertNotIn("PHYTIUM_PI_PASSWORD", access.env_values)
        self.assertEqual(access.build_env().get("REMOTE_PROJECT_ROOT", ""), expected_remote_project_root)
        self.assertRegex(
            access.build_env().get("INFERENCE_BASELINE_EXPECTED_SHA256", ""),
            r"^[0-9a-f]{64}$",
        )
        self.assertRegex(
            access.build_env().get("INFERENCE_CURRENT_EXPECTED_SHA256", ""),
            r"^[0-9a-f]{64}$",
        )
        self.assertEqual(
            access.build_env().get("LOCAL_CURRENT_ARTIFACT_SOURCE", ""),
            discover_trusted_current_local_artifact_source(access.build_env()),
        )
        self.assertIn(
            str(access.build_env().get("OPENAMP_DEMO_ADMISSION_MODE") or ""),
            {"", "signed_manifest_v1"},
        )
        self.assertTrue(access.build_env().get("INFERENCE_CURRENT_CMD", "").startswith("bash ./session_bootstrap/scripts/"))
        self.assertIn("--variant current", access.build_env().get("INFERENCE_CURRENT_CMD", ""))
        self.assertTrue(expected_torch_pythonpath)
        self.assertEqual(access.build_env().get("REMOTE_TORCH_PYTHONPATH", ""), expected_torch_pythonpath)

    def test_password_only_update_reuses_preloaded_ssh_and_inference_defaults(self) -> None:
        defaults = build_demo_default_board_access(None)

        access = build_board_access_config({"password": "demo-pass"}, fallback=defaults)

        self.assertEqual(access.host, defaults.host)
        self.assertEqual(access.user, defaults.user)
        self.assertEqual(access.port, defaults.port)
        self.assertEqual(access.env_file, defaults.env_file)
        self.assertEqual(access.password, "demo-pass")
        self.assertTrue(access.connection_ready)
        self.assertEqual(access.missing_inference_fields("current"), [])
        self.assertEqual(access.missing_inference_fields("baseline"), [])
        self.assertEqual(access.build_env()["REMOTE_PASS"], "demo-pass")
        self.assertEqual(
            access.build_env().get("REMOTE_PROJECT_ROOT", ""),
            defaults.build_env().get("REMOTE_PROJECT_ROOT", ""),
        )
        self.assertEqual(
            access.build_env().get("LOCAL_CURRENT_ARTIFACT_SOURCE", ""),
            defaults.build_env().get("LOCAL_CURRENT_ARTIFACT_SOURCE", ""),
        )
        self.assertEqual(access.field_sources["password"], "session")

    def test_demo_defaults_accept_runtime_password_override(self) -> None:
        access = build_demo_default_board_access(None, startup_env_overrides={"REMOTE_PASS": "demo-pass"})

        self.assertEqual(access.host, "100.121.87.73")
        self.assertEqual(access.user, "user")
        self.assertEqual(access.password, "demo-pass")
        self.assertTrue(access.connection_ready)
        self.assertEqual(access.missing_connection_fields(), [])
        self.assertEqual(access.build_env()["REMOTE_PASS"], "demo-pass")

    def test_explicit_env_file_preserves_validated_torch_sidecar_when_older_env_blanks_it(self) -> None:
        defaults = build_demo_default_board_access(None)
        validated_torch_pythonpath = defaults.build_env().get("REMOTE_TORCH_PYTHONPATH", "")

        self.assertTrue(validated_torch_pythonpath)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            env_path = temp_root / "older_current.env"
            env_path.write_text(
                "\n".join(
                    [
                        "REMOTE_TVM_PYTHON=/usr/bin/python3",
                        "REMOTE_INPUT_DIR=/tmp/input",
                        "REMOTE_OUTPUT_BASE=/tmp/output",
                        "REMOTE_SNR_CURRENT=10",
                        "REMOTE_BATCH_CURRENT=1",
                        "REMOTE_TORCH_PYTHONPATH=",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            access = build_board_access_config(
                {
                    "password": "demo-pass",
                    "env_file": str(env_path),
                },
                fallback=defaults,
            )

        self.assertEqual(access.build_env()["REMOTE_TORCH_PYTHONPATH"], validated_torch_pythonpath)

    def test_with_env_overrides_replaces_stale_current_expected_sha_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            env_path = temp_root / "demo.env"
            stale_sha = "1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644"
            trusted_sha = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
            env_path.write_text(
                "\n".join(
                    [
                        "REMOTE_TVM_PYTHON=/usr/bin/python3",
                        "REMOTE_INPUT_DIR=/tmp/input",
                        "REMOTE_OUTPUT_BASE=/tmp/output",
                        "REMOTE_SNR_CURRENT=12",
                        "REMOTE_BATCH_CURRENT=1",
                        f"INFERENCE_CURRENT_EXPECTED_SHA256={stale_sha}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            access = build_board_access_config(
                {
                    "host": "demo-board",
                    "user": "demo-user",
                    "password": "demo-pass",
                    "port": "22",
                    "env_file": str(env_path),
                }
            )
            corrected = access.with_env_overrides({"INFERENCE_CURRENT_EXPECTED_SHA256": trusted_sha})

        self.assertEqual(access.build_env()["INFERENCE_CURRENT_EXPECTED_SHA256"], stale_sha)
        self.assertEqual(corrected.build_env()["INFERENCE_CURRENT_EXPECTED_SHA256"], trusted_sha)

    def test_with_env_overrides_promotes_remote_pass_into_connection_state(self) -> None:
        access = build_demo_default_board_access(None)

        self.assertEqual(access.missing_connection_fields(), ["password"])
        corrected = access.with_env_overrides({"REMOTE_PASS": "demo-pass"})

        self.assertEqual(corrected.password, "demo-pass")
        self.assertTrue(corrected.connection_ready)
        self.assertEqual(corrected.missing_connection_fields(), [])
        self.assertEqual(corrected.build_env()["REMOTE_PASS"], "demo-pass")


if __name__ == "__main__":
    unittest.main()
