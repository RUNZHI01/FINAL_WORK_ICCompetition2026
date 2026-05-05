from __future__ import annotations

from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
