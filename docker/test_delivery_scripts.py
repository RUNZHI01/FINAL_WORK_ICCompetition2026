from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_local_pytorch_reference_defaults_stay_inside_checkout() -> None:
    script = (
        PROJECT_ROOT
        / "Semantic-Communication"
        / "session_bootstrap"
        / "scripts"
        / "run_remote_pytorch_reference_reconstruction.sh"
    ).read_text(encoding="utf-8")

    assert "/home/tianxing" not in script
    assert 'DEFAULT_LOCAL_JSCC_ROOT="$PACKAGE_ROOT/host_pic_to_latent/jscc"' in script
    assert 'DEFAULT_LOCAL_GENERATOR_CKPT="$PACKAGE_ROOT/board_deps/pytorch/compressed_gan.pt"' in script
