from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import check_openamp_demo_session_readiness as readiness  # noqa: E402


class DemoSessionReadinessTest(unittest.TestCase):
    def test_repo_defaults_report_password_blocker(self) -> None:
        report = readiness.build_readiness_report()

        self.assertEqual(report["overall"]["mode"]["code"], "password_required")
        self.assertTrue(report["overall"]["docs_first_only"])
        self.assertFalse(report["overall"]["can_continue"]["live_probe"])
        self.assertFalse(report["overall"]["can_continue"]["live_inference"]["current"])
        self.assertFalse(report["overall"]["can_continue"]["live_inference"]["baseline"])
        self.assertEqual(report["session"]["missing_connection_fields"], ["password"])
        self.assertEqual(report["variants"]["current"]["missing_env_fields"], ["password"])
        self.assertEqual(report["variants"]["baseline"]["missing_env_fields"], ["password"])
        self.assertEqual(report["variants"]["current"]["control_plane"]["missing_fields"], [])
        self.assertEqual(report["variants"]["baseline"]["control_plane"]["missing_fields"], [])
        self.assertTrue(report["probe_env"]["ready_without_password"])
        self.assertEqual(readiness.exit_code_for_report(report), readiness.EXIT_BLOCKED)
        self.assertIn("缺少会话字段: password。", readiness.render_text(report))

    def test_runtime_password_unlocks_repo_defaults(self) -> None:
        report = readiness.build_readiness_report(password="demo-pass")

        self.assertTrue(report["overall"]["ready_for_live_operator_flow"])
        self.assertFalse(report["overall"]["docs_first_only"])
        self.assertTrue(report["overall"]["can_continue"]["live_probe"])
        self.assertTrue(report["overall"]["can_continue"]["live_inference"]["current"])
        self.assertTrue(report["overall"]["can_continue"]["live_inference"]["baseline"])
        self.assertEqual(report["session"]["missing_connection_fields"], [])
        self.assertEqual(report["variants"]["current"]["missing_env_fields"], [])
        self.assertEqual(report["variants"]["baseline"]["missing_env_fields"], [])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(readiness.exit_code_for_report(report), readiness.EXIT_READY)

    def test_usrp_readiness_is_inactive_for_prerecorded_defaults(self) -> None:
        report = readiness.build_readiness_report()

        self.assertFalse(report["overall"]["can_continue"]["live_usrp"])
        self.assertFalse(report["usrp"]["enabled"])
        self.assertFalse(report["usrp"]["ready"])
        self.assertEqual(report["usrp"]["missing_fields"], [])
        self.assertEqual(report["usrp"]["link_mode"], "qpsk")

    def test_usrp_iq_readiness_reports_missing_remote_rx_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "usrp.env"
            env_path.write_text(
                "\n".join(
                    [
                        "MLKEM_TRANSPORT_MODE=usrp",
                        "OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp",
                        "JSCC_LINK_MODE=iq-direct",
                        "REMOTE_TVM_PYTHON=/home/user/anaconda3/envs/mlkem/bin/python",
                        "REMOTE_INPUT_DIR=/home/user/Downloads/jscc-test/简化版latent",
                        "REMOTE_OUTPUT_BASE=/home/user/Downloads/jscc-test/jscc/infer_outputs",
                        "REMOTE_SNR_CURRENT=10",
                        "REMOTE_BATCH_CURRENT=300",
                        "REMOTE_JSCC_DIR=/home/user/Downloads/jscc-test/jscc",
                        "REMOTE_SNR_BASELINE=10",
                        "REMOTE_BATCH_BASELINE=300",
                    ]
                ),
                encoding="utf-8",
            )

            report = readiness.build_readiness_report(
                host="100.121.87.73",
                user="user",
                password="demo-pass",
                env_file=str(env_path),
            )

        self.assertTrue(report["usrp"]["enabled"])
        self.assertFalse(report["usrp"]["ready"])
        self.assertEqual(report["usrp"]["link_mode"], "iq-direct")
        self.assertIn("REMOTE_USRP_RX_DIR", report["usrp"]["missing_fields"])
        self.assertFalse(report["overall"]["can_continue"]["live_usrp"])
        self.assertTrue(any(blocker["scope"] == "usrp" for blocker in report["blockers"]))

    def test_usrp_iq_readiness_accepts_remote_rx_dir_and_reports_sync_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "usrp.env"
            env_path.write_text(
                "\n".join(
                    [
                        "MLKEM_TRANSPORT_MODE=usrp",
                        "OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp",
                        "JSCC_LINK_MODE=iq-direct",
                        "REMOTE_USRP_RX_DIR=/home/user/cockpit_usrp_rx",
                        "REMOTE_TVM_PYTHON=/home/user/anaconda3/envs/mlkem/bin/python",
                        "REMOTE_INPUT_DIR=/home/user/Downloads/jscc-test/简化版latent",
                        "REMOTE_OUTPUT_BASE=/home/user/Downloads/jscc-test/jscc/infer_outputs",
                        "REMOTE_SNR_CURRENT=10",
                        "REMOTE_BATCH_CURRENT=300",
                        "REMOTE_JSCC_DIR=/home/user/Downloads/jscc-test/jscc",
                        "REMOTE_SNR_BASELINE=10",
                        "REMOTE_BATCH_BASELINE=300",
                    ]
                ),
                encoding="utf-8",
            )

            report = readiness.build_readiness_report(
                host="100.121.87.73",
                user="user",
                password="demo-pass",
                env_file=str(env_path),
            )

        self.assertTrue(report["usrp"]["enabled"])
        self.assertTrue(report["usrp"]["ready"])
        self.assertTrue(report["overall"]["can_continue"]["live_usrp"])
        self.assertEqual(report["usrp"]["missing_fields"], [])
        self.assertTrue(report["usrp"]["iq_board_sync"]["script"].endswith("scripts/prepare_iq_board_sync.sh"))
        self.assertEqual(report["usrp"]["iq_board_sync"]["board_validation_env"], "tvm310_safe")
        self.assertTrue(report["usrp"]["iq_board_sync"]["manifest_activates_board_env"])
        self.assertIn("iq_env=tvm310_safe", readiness.render_text(report))


if __name__ == "__main__":
    unittest.main()
