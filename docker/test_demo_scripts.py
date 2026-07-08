from __future__ import annotations

from pathlib import Path


DOCKER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DOCKER_DIR.parent


def read_script(name: str) -> str:
    return (DOCKER_DIR / name).read_text(encoding="utf-8")


def test_start_electron_has_tvm250_prerecorded_profile() -> None:
    script = read_script("start-electron-prod-demo.sh")

    assert "ICCOMP_COCKPIT_PROFILE" in script
    assert "tvm250-prerecorded" in script
    assert 'OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"' in script
    assert 'MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-tcp}"' in script
    assert 'MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-0}"' in script
    assert 'JSCC_LINK_MODE="${JSCC_LINK_MODE:-qpsk}"' in script
    assert 'ANALOG_IN_PROCESS_LOCAL_CODEC="${ANALOG_IN_PROCESS_LOCAL_CODEC:-1}"' in script
    assert 'ANALOG_WARMUP_LOCAL_CODEC="${ANALOG_WARMUP_LOCAL_CODEC:-1}"' in script


def test_run_demo_wrappers_forward_board_and_profile_environment() -> None:
    shell_script = read_script("run-demo.sh")
    powershell_script = read_script("run-demo.ps1")
    required_env = {
        "ICCOMP_COCKPIT_PROFILE",
        "REMOTE_HOST",
        "PHYTIUM_PI_HOST",
        "REMOTE_USER",
        "PHYTIUM_PI_USER",
        "REMOTE_PASS",
        "PHYTIUM_PI_PASSWORD",
        "REMOTE_SSH_PORT",
        "PHYTIUM_PI_PORT",
        "OPENAMP_DEMO_INPUT_SOURCE_MODE",
        "JSCC_LINK_MODE",
        "OPENAMP_DEMO_LINK_MODE",
        "ANALOG_IN_PROCESS_LOCAL_CODEC",
        "ANALOG_WARMUP_LOCAL_CODEC",
        "MLKEM_TRANSPORT_MODE",
        "MLKEM_AUTH_ENABLED",
        "OPENAMP_SSH_RUNNER",
        "OPENAMP_SSH_DOCKER_IMAGE",
    }

    for name in required_env:
        assert name in shell_script
        assert name in powershell_script


def test_prepare_iq_board_sync_manifest_avoids_password_placeholder_and_lists_all_files() -> None:
    script = (PROJECT_ROOT / "scripts" / "prepare_iq_board_sync.sh").read_text(encoding="utf-8")
    extract_section = script.split("## 板端解压命令", 1)[1].split("## 同步后板端验证", 1)[0]

    assert "SSHPASS=user" not in script
    assert "SSHPASS=<board password>" not in script
    for rel_path in (
        "USRP292x/RunAnalogLatentBatch.py",
        "USRP292x/AnalogLatentLink.py",
        "USRP292x/test_analog_latent_link.py",
        "host_pic_to_latent/jscc/src/test_model.py",
        "scripts/tvm_inference_helper.py",
        "scripts/latent_transport.py",
    ):
        assert rel_path in script
        assert rel_path in extract_section


def test_prepare_iq_board_sync_powershell_wrapper_runs_docker_packager() -> None:
    script = read_script("prepare-iq-board-sync.ps1")

    assert "iccomp-ubuntu-minimal" in script
    assert '"/workspace"' in script
    assert "REPO_ROOT=/workspace" in script
    assert "OUT_TAR=/workspace/artifacts/iq_board_sync.tar.gz" in script
    assert "OUT_MANIFEST=/workspace/artifacts/iq_board_sync_manifest.txt" in script
    assert "scripts/prepare_iq_board_sync.sh" in script
