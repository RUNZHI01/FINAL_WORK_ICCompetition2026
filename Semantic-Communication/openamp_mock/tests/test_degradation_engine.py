from __future__ import annotations

import unittest

from openamp_mock.degradation_engine import DegradationEngine
from openamp_mock.link_health import LinkHealthSimulator
from openamp_mock.protocol import ServiceMode

class DegradationEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DegradationEngine()
        self.sim = LinkHealthSimulator()

    def test_full_to_roi(self) -> None:
        for _ in range(3):
            mode = self.engine.update(self.sim.degraded())

        self.assertEqual(mode, ServiceMode.ROI_ONLY)
        self.assertEqual(self.engine.current_mode, ServiceMode.ROI_ONLY)

    def test_roi_to_alert(self) -> None:
        for _ in range(3):
            self.engine.update(self.sim.degraded())
        for _ in range(3):
            mode = self.engine.update(self.sim.severe())

        self.assertEqual(mode, ServiceMode.ALERT_ONLY)
        self.assertEqual(self.engine.current_mode, ServiceMode.ALERT_ONLY)

    def test_burst_loss_emergency(self) -> None:
        mode = self.engine.update(self.sim.burst_loss())

        self.assertEqual(mode, ServiceMode.ALERT_ONLY)
        self.assertEqual(self.engine.current_mode, ServiceMode.ALERT_ONLY)

    def test_recovery_roi_to_full(self) -> None:
        for _ in range(3):
            self.engine.update(self.sim.degraded())
        for _ in range(5):
            mode = self.engine.update(self.sim.normal())

        self.assertEqual(mode, ServiceMode.FULL_FRAME)
        self.assertEqual(self.engine.current_mode, ServiceMode.FULL_FRAME)

    def test_link_lost(self) -> None:
        mode = self.engine.update(self.sim.lost())

        self.assertTrue(self.engine.is_link_lost)
        self.assertEqual(mode, ServiceMode.ALERT_ONLY)
        self.assertEqual(self.engine.current_mode, ServiceMode.ALERT_ONLY)

    def test_hysteresis_no_flap(self) -> None:
        self.engine.update(self.sim.degraded())
        self.engine.update(self.sim.degraded())
        self.engine.update(self.sim.normal())
        self.engine.update(self.sim.degraded())
        self.engine.update(self.sim.degraded())

        self.assertEqual(self.engine.current_mode, ServiceMode.FULL_FRAME)

    def test_payload_strategy(self) -> None:
        self.assertEqual(self.engine.payload_strategy, "full_latent")

        for _ in range(3):
            self.engine.update(self.sim.degraded())
        self.assertEqual(self.engine.payload_strategy, "roi_latent")

        for _ in range(3):
            self.engine.update(self.sim.severe())
        self.assertEqual(self.engine.payload_strategy, "alert_metadata")

    def test_snapshot(self) -> None:
        for _ in range(3):
            self.engine.update(self.sim.degraded())

        snapshot = self.engine.snapshot()

        self.assertEqual(snapshot["current_mode"], "ROI_ONLY")
        self.assertEqual(snapshot["current_mode_value"], int(ServiceMode.ROI_ONLY))
        self.assertEqual(snapshot["payload_strategy"], "roi_latent")
        self.assertFalse(snapshot["is_link_lost"])
        self.assertIn("degrade_window_count", snapshot)
        self.assertIn("upgrade_window_count", snapshot)
        self.assertEqual(snapshot["mode_transitions"], 1)
        self.assertIsInstance(snapshot["last_transition"], dict)

    def test_reset(self) -> None:
        for _ in range(3):
            self.engine.update(self.sim.degraded())

        self.engine.reset()

        self.assertEqual(self.engine.current_mode, ServiceMode.FULL_FRAME)
        self.assertEqual(self.engine.payload_strategy, "full_latent")
        self.assertFalse(self.engine.is_link_lost)
        snapshot = self.engine.snapshot()
        self.assertEqual(snapshot["degrade_window_count"], 0)
        self.assertEqual(snapshot["upgrade_window_count"], 0)


if __name__ == "__main__":
    unittest.main()
