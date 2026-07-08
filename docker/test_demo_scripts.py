from __future__ import annotations

from pathlib import Path


DOCKER_DIR = Path(__file__).resolve().parent


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
        "MLKEM_TRANSPORT_MODE",
        "MLKEM_AUTH_ENABLED",
        "OPENAMP_SSH_RUNNER",
        "OPENAMP_SSH_DOCKER_IMAGE",
    }

    for name in required_env:
        assert name in shell_script
        assert name in powershell_script
