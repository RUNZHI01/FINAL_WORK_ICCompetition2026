from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from cockpit_native.availability import is_pyside6_available


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AvailabilityTest(unittest.TestCase):
    def test_is_pyside6_available_matches_importlib_probe(self) -> None:
        self.assertEqual(is_pyside6_available(), importlib.util.find_spec("PySide6") is not None)

    def test_smoke_import_check_passes_without_qt_runtime(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cockpit_native", "--smoke-import-check"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("available", payload)
        self.assertEqual(payload["aircraft_contract"], "aircraft_position.v1")
        self.assertEqual(payload["recommended_scenario_id"], "snr10_bestcurrent")
        self.assertEqual(payload["launch_hint"], "bash ./session_bootstrap/scripts/run_cockpit_native.sh")
        self.assertEqual(
            payload["smoke_check_hint"],
            "bash ./session_bootstrap/scripts/run_cockpit_native.sh --smoke-import-check",
        )


if __name__ == "__main__":
    unittest.main()
