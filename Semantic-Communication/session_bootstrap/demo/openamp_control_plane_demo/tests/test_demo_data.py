from __future__ import annotations

from pathlib import Path
import sys
import unittest


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from demo_data import build_aircraft_position_snapshot, build_prerecorded_inference_result, build_snapshot  # noqa: E402


class DemoDataTest(unittest.TestCase):
    def test_snapshot_contains_expected_verdicts(self) -> None:
        snapshot = build_snapshot()
        self.assertIn("P0", snapshot["project"]["final_verdict"])
        self.assertEqual(snapshot["project"]["trusted_current_sha"], "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1")
        fit_by_id = {fit["fit_id"]: fit for fit in snapshot["fits"]}
        self.assertEqual(fit_by_id["FIT-01"]["status"], "PASS")
        self.assertEqual(fit_by_id["FIT-02"]["status"], "PASS")
        self.assertEqual(fit_by_id["FIT-03"]["status"], "PASS")
        self.assertEqual(fit_by_id["FIT-03"]["history"]["status"], "FAIL")

    def test_snapshot_uses_chunk4_performance_alignment(self) -> None:
        snapshot = build_snapshot()
        performance = snapshot["performance"]
        self.assertEqual(performance["artifact_sha"], snapshot["project"]["trusted_current_sha"])
        self.assertAlmostEqual(performance["micro_summary"]["payload_current_ms"], 130.219)
        self.assertAlmostEqual(performance["micro_summary"]["end_to_end_current_ms"], 230.339)
        self.assertAlmostEqual(performance["micro_summary"]["incremental_speedup_x"], 16.272)

    def test_live_probe_switches_mode(self) -> None:
        snapshot = build_snapshot(
            live_probe={
                "requested_at": "2026-03-15T12:00:00+0800",
                "reachable": True,
                "summary": "board reachable",
                "details": {"remoteproc": [{"name": "remoteproc0", "state": "running"}]},
            }
        )
        self.assertEqual(snapshot["mode"]["effective_label"], "在线读数可用")
        self.assertTrue(snapshot["board"]["current_status"]["reachable"])

    def test_cached_live_probe_is_labeled_as_saved(self) -> None:
        snapshot = build_snapshot(
            live_probe={
                "requested_at": "2026-03-15T12:00:00+0800",
                "reachable": True,
                "status": "success",
                "summary": "board reachable",
                "details": {"remoteproc": [{"name": "remoteproc0", "state": "running"}]},
                "_loaded_from_cache": True,
            }
        )
        self.assertIn("恢复最近一次只读 ssh 结果", snapshot["mode"]["summary"].lower())
        self.assertEqual(snapshot["board"]["current_status"]["label"], "保存的只读 SSH 探板")
        self.assertIn("上一次成功探板的保存记录", snapshot["board"]["current_status"]["summary"])

    def test_guided_demo_snapshot_contains_comparison_and_sample_catalog(self) -> None:
        snapshot = build_snapshot()
        guided_demo = snapshot["guided_demo"]

        self.assertIn("comparison", guided_demo)
        self.assertIn("compare_viewer", guided_demo)
        self.assertIn("sample_catalog", guided_demo)
        self.assertGreaterEqual(len(guided_demo["sample_catalog"]), 1)
        self.assertAlmostEqual(guided_demo["comparison"]["payload"]["baseline_ms"], 436.722)
        self.assertEqual(guided_demo["comparison"]["baseline_source"]["label"], "PyTorch 参考基线")
        self.assertAlmostEqual(guided_demo["comparison"]["end_to_end"]["current_ms"], 230.339)
        self.assertIn("先提供并排 compare viewer", guided_demo["compare_viewer"]["mode_note"])
        self.assertIn("页面刷新后若系统状态保留最近一次已完成结果", guided_demo["compare_viewer"]["fallback_note"])
        self.assertEqual(guided_demo["compare_viewer"]["samples"][0]["current"]["source_label"], "Current 归档重建图")
        self.assertEqual(guided_demo["compare_viewer"]["samples"][0]["baseline"]["source_label"], "PyTorch 参考 archive")

    def test_snapshot_surfaces_latest_live_dualpath_status_report(self) -> None:
        snapshot = build_snapshot()
        latest = snapshot["latest_live_status"]

        self.assertEqual(latest["report_date"], "2026-03-17")
        self.assertEqual(latest["valid_instance"], "8115")
        self.assertEqual(latest["current"]["completed"], "300 / 300")
        self.assertEqual(latest["baseline"]["label"], "PyTorch 参考基线")
        self.assertEqual(latest["baseline"]["completed"], "300 / 300 (archive)")
        self.assertEqual(
            latest["report"]["path"],
            "session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md",
        )
        self.assertEqual(snapshot["docs"][0]["path"], latest["report"]["path"])
        self.assertEqual(snapshot["docs"][1]["path"], "session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/pytorch_reference_manifest.json")

    def test_snapshot_contains_mission_dashboard_archive_timeline(self) -> None:
        snapshot = build_snapshot()
        mission = snapshot["mission"]

        self.assertEqual(mission["batch_target"], 300)
        self.assertIn("OpenAMP / RPMsg", mission["control_plane_note"])
        self.assertIn("3-core Linux + RTOS demo mode", mission["mode_split_note"])
        self.assertGreaterEqual(len(mission["archive_timeline"]), 4)
        self.assertEqual(mission["archive_timeline"][0]["title"], "Current live 300 / 300 已归档")

    def test_snapshot_contains_real_weak_network_console(self) -> None:
        snapshot = build_snapshot()
        weak_network = snapshot["weak_network"]
        scenarios = {item["scenario_id"]: item for item in weak_network["scenarios"]}

        self.assertEqual(weak_network["recommended_scenario_id"], "snr10_bestcurrent")
        self.assertEqual(weak_network["live_anchor"]["valid_instance"], "8115")
        self.assertAlmostEqual(scenarios["snr12_real_compare"]["channel"]["snr_db"], 12.0)
        self.assertAlmostEqual(scenarios["snr10_real_compare"]["comparison"]["throughput_uplift_pct"], 35.298)
        self.assertAlmostEqual(scenarios["snr10_bestcurrent"]["comparison"]["throughput_uplift_pct"], 56.077)
        self.assertEqual(scenarios["snr10_bestcurrent"]["topology"]["big_cores"], [2])
        self.assertEqual(len(scenarios["snr10_bestcurrent"]["stage_timings"]), 4)

    def test_snapshot_contains_backend_aircraft_position_contract(self) -> None:
        snapshot = build_snapshot()
        aircraft = snapshot["aircraft_position"]

        self.assertEqual(aircraft["contract_version"], "aircraft_position.v1")
        self.assertEqual(aircraft["source_api_path"], "/api/aircraft-position")
        self.assertEqual(aircraft["source_kind"], "backend_stub")
        self.assertEqual(aircraft["source_status"], "stub")
        self.assertEqual(aircraft["source_label"], "Backend stub contract")
        self.assertIn("upper-computer/backend contract", aircraft["ownership_note"])
        self.assertNotIn("browser geolocation", aircraft["ownership_note"])
        self.assertEqual(aircraft["sample"]["sequence"], 0)
        self.assertEqual(aircraft["sample"]["transport"], "backend_http_post")
        self.assertFalse(aircraft["feed_contract"]["primary_source"]["active"])
        self.assertTrue(aircraft["feed_contract"]["fallback_source"]["active"])
        self.assertEqual(aircraft["feed_contract"]["active_source_label"], "Backend Stub Contract")
        self.assertAlmostEqual(aircraft["position"]["latitude"], 30.572815)
        self.assertAlmostEqual(aircraft["position"]["longitude"], 104.066801)
        self.assertEqual(len(aircraft["track"]), 6)

    def test_build_aircraft_position_snapshot_accepts_live_override(self) -> None:
        aircraft = build_aircraft_position_snapshot(
            {
                "source_kind": "upper_computer_gps",
                "source_status": "live",
                "source_label": "Upper Computer GPS live feed",
                "position": {"latitude": 31.111111, "longitude": 121.222222},
                "kinematics": {"heading_deg": 135.2, "ground_speed_kph": 266.4, "altitude_m": 2401.5},
                "fix": {"type": "RTK", "confidence_m": 1.8, "satellites": 18},
                "sample": {
                    "captured_at": "2026-03-20T12:34:56+0800",
                    "sequence": 7,
                    "transport": "backend_http_post",
                    "producer_id": "upper-computer-gps-daemon",
                },
            }
        )

        self.assertEqual(aircraft["source_kind"], "upper_computer_gps")
        self.assertEqual(aircraft["source_status"], "live")
        self.assertEqual(aircraft["fix"]["type"], "RTK")
        self.assertAlmostEqual(aircraft["position"]["latitude"], 31.111111)
        self.assertAlmostEqual(aircraft["position"]["longitude"], 121.222222)
        self.assertAlmostEqual(aircraft["kinematics"]["heading_deg"], 135.2)
        self.assertAlmostEqual(aircraft["kinematics"]["ground_speed_kph"], 266.4)
        self.assertEqual(aircraft["sample"]["sequence"], 7)
        self.assertEqual(aircraft["sample"]["captured_at"], "2026-03-20T12:34:56+0800")
        self.assertTrue(aircraft["feed_contract"]["primary_source"]["active"])
        self.assertFalse(aircraft["feed_contract"]["fallback_source"]["active"])
        self.assertEqual(aircraft["feed_contract"]["active_source_label"], "Upper Computer GPS")

    def test_prerecorded_baseline_uses_pytorch_reference_manifest(self) -> None:
        payload = build_prerecorded_inference_result(0, "baseline")

        self.assertEqual(payload["execution_mode"], "reference")
        self.assertEqual(payload["source_label"], "PyTorch 参考基线")
        self.assertIn("PyTorch reference manifest", payload["message"])
        self.assertIn("session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions/", payload["image_sources"]["reconstructed_path"])
        self.assertIsNotNone(payload["quality"]["psnr_db"])
        self.assertEqual(
            payload["evidence"][0]["path"],
            "session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/pytorch_reference_manifest.json",
        )


if __name__ == "__main__":
    unittest.main()
