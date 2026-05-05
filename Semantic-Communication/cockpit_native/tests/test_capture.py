from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cockpit_native.capture import default_capture_output_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CaptureEntrypointTest(unittest.TestCase):
    def test_default_capture_output_path_is_repo_local(self) -> None:
        self.assertEqual(
            default_capture_output_path(PROJECT_ROOT),
            PROJECT_ROOT / "cockpit_native" / "runtime" / "captures" / "cockpit_native_latest.png",
        )

    @unittest.skipUnless(importlib.util.find_spec("PySide6") is not None, "PySide6 is required")
    def test_capture_module_writes_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "capture.png"
            result = subprocess.run(
                [sys.executable, "-m", "cockpit_native.capture", "--output", str(output_path)],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(Path(result.stdout.strip()), output_path.resolve())
            self.assertTrue(output_path.is_file())

            from PySide6.QtGui import QImage

            image = QImage(str(output_path))
            self.assertFalse(image.isNull())
            self.assertGreater(image.width(), 0)
            self.assertGreater(image.height(), 0)
