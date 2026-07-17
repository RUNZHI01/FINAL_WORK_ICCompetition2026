import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[5]
ENCODE_LATENT_PATH = REPO_ROOT / "host_pic_to_latent" / "encode_latent.py"


def load_encode_latent_module():
    spec = importlib.util.spec_from_file_location("encode_latent_for_test", ENCODE_LATENT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HostPicToLatentTest(unittest.TestCase):
    def test_resolve_jscc_root_prefers_environment_override(self) -> None:
        module = load_encode_latent_module()

        with patch.dict("os.environ", {"HOST_PIC_TO_LATENT_JSCC_ROOT": "/tmp/board-jscc"}):
            resolved = module.resolve_jscc_root()

        self.assertEqual(resolved, str(Path("/tmp/board-jscc").resolve()))

    def test_resolve_checkpoint_path_falls_back_to_workspace_jscc_origin(self) -> None:
        module = load_encode_latent_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            script_dir = workspace / "FINAL_WORK_ICCompetition2026" / "host_pic_to_latent"
            local_ckpt_dir = script_dir / "checkpoint"
            workspace_ckpt_dir = workspace / "jscc-test" / "origin"
            workspace_ckpt_dir.mkdir(parents=True)
            expected = workspace_ckpt_dir / "1snr_lpips_6_6_6_6_6_6_6_openimages_gan.pt"
            expected.write_bytes(b"checkpoint")

            with patch.object(module, "SCRIPT_DIR", str(script_dir)):
                resolved = module.resolve_checkpoint_path(str(local_ckpt_dir), "6_6_6_6_6_6_6")

        self.assertEqual(resolved, str(expected))


if __name__ == "__main__":
    unittest.main()
