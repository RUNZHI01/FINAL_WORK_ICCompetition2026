from __future__ import annotations

import unittest

from openamp_mock.demo import (
    MockSession,
    run_allow_scenario,
    run_input_contract_deny_scenario,
    run_timeout_scenario,
    run_wrong_sha_deny_scenario,
)


class OpenAmpMockTest(unittest.TestCase):
    def test_allow_scenario(self) -> None:
        _, result = run_allow_scenario()
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "ALLOW")
        self.assertEqual(result["orchestrator_state"], "DONE")
        self.assertEqual(result["guard_state"], "READY")

    def test_wrong_sha_denied(self) -> None:
        _, result = run_wrong_sha_deny_scenario()
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["last_fault_code"], "F001")

    def test_input_contract_denied(self) -> None:
        _, result = run_input_contract_deny_scenario()
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(result["last_fault_code"], "F002")

    def test_heartbeat_timeout_safe_stop(self) -> None:
        _, result = run_timeout_scenario()
        self.assertTrue(result["passed"])
        self.assertEqual(result["last_fault_code"], "F003")
        self.assertEqual(result["orchestrator_state"], "SAFE_STOPPED")
        self.assertEqual(result["guard_state"], "FAULT_LATCHED")

    def test_reset_ack_recovers_guard(self) -> None:
        session, _ = run_timeout_scenario()
        session.reset_guard()
        self.assertEqual(session.guard.state.value, "READY")
        self.assertEqual(session.orchestrator.state.value, "IDLE")


if __name__ == "__main__":
    unittest.main()
