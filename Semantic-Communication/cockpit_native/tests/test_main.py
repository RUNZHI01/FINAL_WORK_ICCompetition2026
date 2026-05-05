from __future__ import annotations

import os
import unittest

from cockpit_native.__main__ import (
    COCKPIT_NATIVE_CHILD_ENV,
    COCKPIT_NATIVE_SOFTWARE_FALLBACK_ENV,
    build_child_command,
    build_child_env,
    parse_safe_area_insets,
)


class MainLauncherTest(unittest.TestCase):
    def test_parse_safe_area_insets_accepts_valid_input(self) -> None:
        self.assertEqual(
            parse_safe_area_insets("1,2,3,4"),
            {"left": 1, "top": 2, "right": 3, "bottom": 4},
        )

    def test_build_child_command_adds_single_software_flag(self) -> None:
        command = build_child_command(["--safe-area-insets", "0,0,0,0", "--software-render"], software_render=True)

        self.assertEqual(command[:3], [os.sys.executable, "-m", "cockpit_native"])
        self.assertEqual(command.count("--software-render"), 1)

    def test_build_child_env_marks_child_and_sets_software_renderer(self) -> None:
        env = build_child_env(software_render=True)

        self.assertEqual(env[COCKPIT_NATIVE_CHILD_ENV], "1")
        self.assertEqual(env[COCKPIT_NATIVE_SOFTWARE_FALLBACK_ENV], "1")
        self.assertEqual(env["QT_QUICK_BACKEND"], "software")
        self.assertEqual(env["QSG_RHI_BACKEND"], "software")
        self.assertEqual(env["QT_OPENGL"], "software")


if __name__ == "__main__":
    unittest.main()
