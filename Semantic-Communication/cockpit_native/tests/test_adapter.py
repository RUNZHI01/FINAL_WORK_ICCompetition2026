from __future__ import annotations

from pathlib import Path
import unittest

from cockpit_native.adapter import DemoRepoAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DemoRepoAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DemoRepoAdapter(project_root=PROJECT_ROOT)

    def test_latest_snapshot_path_uses_current_archive(self) -> None:
        snapshot_path = self.adapter.latest_snapshot_path()
        self.assertEqual(snapshot_path.name, "state_snapshot.json")
        self.assertTrue(snapshot_path.parent.name.startswith("session_"))
        self.assertTrue(snapshot_path.is_file())

    def test_load_contract_bundle_reads_repo_backed_sources(self) -> None:
        bundle = self.adapter.load_contract_bundle()

        self.assertTrue(str(bundle.snapshot["aggregate"]["session_id"]).startswith("session_"))
        self.assertIsInstance(bundle.snapshot["reason"], str)
        self.assertTrue(bundle.snapshot["reason"])
        self.assertEqual(bundle.aircraft_position["contract_version"], "aircraft_position.v1")
        self.assertEqual(bundle.aircraft_position["source_api_path"], "/api/aircraft-position")
        self.assertEqual(bundle.weak_network["recommended_scenario_id"], "snr10_bestcurrent")
        self.assertEqual(len(bundle.weak_network["scenarios"]), 3)

    def test_ui_state_exposes_expected_zones(self) -> None:
        ui_state = self.adapter.load_contract_bundle().ui_state
        center_panel = ui_state["zones"]["center_tactical_view"]
        footer_note = ui_state["zones"]["bottom_action_strip"]["footer_note"]

        self.assertIn("zones", ui_state)
        self.assertEqual(ui_state["meta"]["launch_hint"], "bash ./session_bootstrap/scripts/run_cockpit_native.sh")
        self.assertIn("left_status_panel", ui_state["zones"])
        self.assertIn("center_tactical_view", ui_state["zones"])
        self.assertIn("right_weak_network_panel", ui_state["zones"])
        self.assertIn("bottom_action_strip", ui_state["zones"])
        self.assertIn("run_cockpit_native.sh", footer_note)
        self.assertEqual(center_panel["mission_call_sign"], "M9-DEMO")
        self.assertEqual(center_panel["feed_contract"]["api_path"], "/api/aircraft-position")
        self.assertEqual(center_panel["feed_contract"]["active_source_kind"], "backend_stub")
        self.assertGreater(len(center_panel["track"]), 0)
        self.assertAlmostEqual(center_panel["position"]["latitude"], 30.572815)
        self.assertAlmostEqual(center_panel["position"]["longitude"], 104.066801)

    def test_load_contract_bundle_defaults_degradation_status_to_not_connected(self) -> None:
        ui_state = self.adapter.load_contract_bundle().ui_state
        left_rows = ui_state["zones"]["left_status_panel"]["rows"]
        actions = ui_state["zones"]["bottom_action_strip"]["actions"]

        degradation_row = next(row for row in left_rows if row["label"] == "退化模式")
        degradation_action = next(action for action in actions if action["action_id"] == "degradation_status")

        self.assertEqual(degradation_row["value"], "未接入")
        self.assertEqual(degradation_row["tone"], "neutral")
        self.assertEqual(degradation_action["note"], "退化引擎未接入。")
        self.assertFalse(degradation_action["enabled"])
        self.assertFalse(degradation_action["interactive"])

    def test_load_contract_bundle_injects_degradation_status(self) -> None:
        status = {
            "current_mode": "ROI_ONLY",
            "payload_strategy": "roi_latent",
            "is_link_lost": False,
            "mode_transitions": 2,
        }
        ui_state = self.adapter.load_contract_bundle(degradation_status=status).ui_state
        left_rows = ui_state["zones"]["left_status_panel"]["rows"]
        actions = ui_state["zones"]["bottom_action_strip"]["actions"]

        degradation_row = next(row for row in left_rows if row["label"] == "退化模式")
        degradation_action = next(action for action in actions if action["action_id"] == "degradation_status")

        self.assertEqual(degradation_row["value"], "ROI_ONLY")
        self.assertEqual(degradation_row["tone"], "degraded")
        self.assertIn("当前模式 ROI_ONLY", degradation_action["note"])
        self.assertIn("发送策略 roi_latent", degradation_action["note"])
        self.assertEqual(degradation_action["tone"], "degraded")


if __name__ == "__main__":
    unittest.main()
