from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_trusted_artifacts.py"
WRAPPER_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_control_wrapper.py"


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


artifacts = load_module("openamp_trusted_artifacts_test", ARTIFACTS_PATH)
wrapper = load_module("openamp_control_wrapper_test", WRAPPER_PATH)

BASELINE_SHA = "85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849"
CURRENT_SHA = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"


class TrustedArtifactsTest(unittest.TestCase):
    def test_load_trusted_artifacts_has_enabled_baseline_and_current(self) -> None:
        trusted = {artifact.label: artifact for artifact in artifacts.load_trusted_artifacts()}

        self.assertEqual(set(trusted), {"baseline", "current"})
        self.assertTrue(trusted["baseline"].enabled)
        self.assertTrue(trusted["current"].enabled)
        self.assertEqual(trusted["baseline"].sha256, BASELINE_SHA)
        self.assertEqual(trusted["current"].sha256, CURRENT_SHA)

    def test_wrapper_resolves_variant_label_from_allowlist(self) -> None:
        args = SimpleNamespace(
            expected_sha256="",
            trusted_artifact_label="",
            trusted_artifacts_file=str(artifacts.DEFAULT_TRUSTED_ARTIFACTS_PATH),
            variant="baseline",
        )

        with mock.patch.dict(wrapper.os.environ, {}, clear=True):
            expected_sha256, trusted_artifact, source = wrapper.resolve_expected_sha256(args)

        self.assertEqual(expected_sha256, BASELINE_SHA)
        self.assertEqual(source, "--variant")
        self.assertIsNotNone(trusted_artifact)
        assert trusted_artifact is not None
        self.assertEqual(trusted_artifact["label"], "baseline")

    def test_wrapper_keeps_direct_sha_compatibility(self) -> None:
        args = SimpleNamespace(
            expected_sha256=BASELINE_SHA,
            trusted_artifact_label="",
            trusted_artifacts_file=str(artifacts.DEFAULT_TRUSTED_ARTIFACTS_PATH),
            variant="current",
        )

        with mock.patch.dict(wrapper.os.environ, {}, clear=True):
            expected_sha256, trusted_artifact, source = wrapper.resolve_expected_sha256(args)

        self.assertEqual(expected_sha256, BASELINE_SHA)
        self.assertEqual(source, "--expected-sha256")
        self.assertIsNone(trusted_artifact)

    def test_wrapper_rejects_mismatched_label_and_sha(self) -> None:
        args = SimpleNamespace(
            expected_sha256=BASELINE_SHA,
            trusted_artifact_label="current",
            trusted_artifacts_file=str(artifacts.DEFAULT_TRUSTED_ARTIFACTS_PATH),
            variant="current",
        )

        with self.assertRaises(SystemExit) as raised:
            wrapper.resolve_expected_sha256(args)

        self.assertIn("does not match", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
