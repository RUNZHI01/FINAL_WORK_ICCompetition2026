from __future__ import annotations

from pathlib import Path


DOCKER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DOCKER_DIR.parent


def read_script(name: str) -> str:
    return (DOCKER_DIR / name).read_text(encoding="utf-8")


def test_start_electron_has_tvm250_profile_and_fast_iq_defaults() -> None:
    script = read_script("start-electron-prod-demo.sh")

    assert "ICCOMP_COCKPIT_PROFILE" in script
    assert "tvm250-prerecorded" in script
    assert 'OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"' in script
    assert 'MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-tcp}"' in script
    assert 'MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-0}"' in script
    assert 'MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"' in script
    assert 'JSCC_LINK_MODE="${JSCC_LINK_MODE:-iq-direct}"' in script
    assert 'ANALOG_REMOTE_DECODE_RESULT_MODE="${ANALOG_REMOTE_DECODE_RESULT_MODE:-remote-dir}"' in script
    assert 'ANALOG_IN_PROCESS_LOCAL_CODEC="${ANALOG_IN_PROCESS_LOCAL_CODEC:-1}"' in script
    assert 'ANALOG_WARMUP_LOCAL_CODEC="${ANALOG_WARMUP_LOCAL_CODEC:-1}"' in script
    assert 'ANALOG_SPS="${ANALOG_SPS:-2}"' in script
    assert 'ANALOG_AMPLITUDE="${ANALOG_AMPLITUDE:-6000}"' in script
    assert 'ANALOG_RX_TAIL_SEC="${ANALOG_RX_TAIL_SEC:-0.05}"' in script
    assert 'PERSISTENT_RX_TX_DELAY="${PERSISTENT_RX_TX_DELAY:-0}"' in script
    assert 'ANALOG_MIN_SYNC_METRIC="${ANALOG_MIN_SYNC_METRIC:-0.05}"' in script
    assert 'ANALOG_ROBUST_SYNC="${ANALOG_ROBUST_SYNC:-0}"' in script
    assert 'ANALOG_REMOTE_CLEANUP_MODE="${ANALOG_REMOTE_CLEANUP_MODE:-skip}"' in script
    assert 'ANALOG_REMOTE_DECODE_WORKER="${ANALOG_REMOTE_DECODE_WORKER:-1}"' in script
    assert 'USRP_MAX_ARQ_ROUNDS="${USRP_MAX_ARQ_ROUNDS:-1}"' in script
    assert 'REMOTE_USRP_DECODE_PYTHON="${REMOTE_USRP_DECODE_PYTHON:-/home/user/venv/bin/python}"' in script
    assert 'OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"' in script


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
        "REMOTE_USRP_RX_DIR",
        "REMOTE_USRP_DECODE_PYTHON",
        "OPENAMP_DEMO_REMOTE_DECODE_PYTHON",
        "JSCC_LINK_MODE",
        "OPENAMP_DEMO_LINK_MODE",
        "ANALOG_IN_PROCESS_LOCAL_CODEC",
        "ANALOG_WARMUP_LOCAL_CODEC",
        "ANALOG_SPS",
        "ANALOG_AMPLITUDE",
        "ANALOG_RX_TAIL_SEC",
        "PERSISTENT_RX_TX_DELAY",
        "ANALOG_REMOTE_CLEANUP_MODE",
        "ANALOG_REMOTE_DECODE_WORKER",
        "ANALOG_REMOTE_DECODE_RESULT_MODE",
        "ANALOG_REMOTE_DECODED_OUTPUT_DIR",
        "ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_SEC",
        "ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC",
        "ANALOG_MIN_SYNC_METRIC",
        "ANALOG_ROBUST_SYNC",
        "USRP_MAX_ARQ_ROUNDS",
        "MLKEM_USRP_MAX_ARQ_ROUNDS",
        "MLKEM_TRANSPORT_MODE",
        "MLKEM_AUTH_ENABLED",
        "MLKEM_AUTH_SIG_POLICY",
        "OPENAMP_SSH_RUNNER",
        "OPENAMP_SSH_DOCKER_IMAGE",
        "SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER",
        "OPENAMP_USRP_TX_RUNNER",
        "OPENAMP_USRP_TX_DOCKER_IMAGE",
        "OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET",
        "OPENAMP_TVM_BATCH_RUNNER",
        "OPENAMP_DEMO_TVM_BATCH_RUNNER",
        "OPENAMP_TVM_BATCH_EXIT_GRACE_SEC",
    }

    for name in required_env:
        assert name in shell_script
        assert name in powershell_script


def test_run_demo_tailscale_defaults_match_current_cockpit_usrp_tvm_profile() -> None:
    shell_script = read_script("run-demo-tailscale.sh")
    powershell_script = read_script("run-demo-tailscale.ps1")

    shell_defaults = (
        'REMOTE_HOST="${REMOTE_HOST:-100.121.87.73}"',
        'REMOTE_USER="${REMOTE_USER:-user}"',
        'REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"',
        'OPENAMP_SSH_RUNNER="${OPENAMP_SSH_RUNNER:-paramiko}"',
        'SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER="${SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER:-1}"',
        'OPENAMP_USRP_TX_RUNNER="${OPENAMP_USRP_TX_RUNNER:-docker}"',
        'OPENAMP_USRP_TX_DOCKER_IMAGE="${OPENAMP_USRP_TX_DOCKER_IMAGE:-iccomp-usrp-tx:latest}"',
        'OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET="${OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET:-/host_workspace}"',
        'REMOTE_USRP_RX_DIR="${REMOTE_USRP_RX_DIR:-/home/user/cockpit_usrp_rx}"',
        'REMOTE_RX_RUN_ROOT="${REMOTE_RX_RUN_ROOT:-/tmp/usrp292x_remote_runs}"',
        'REMOTE_USRP_PROJECT_ROOT="${REMOTE_USRP_PROJECT_ROOT:-/home/user}"',
        'REMOTE_USRP_DECODE_PYTHON="${REMOTE_USRP_DECODE_PYTHON:-/home/user/venv/bin/python}"',
        'OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"',
        'JSCC_LINK_MODE="${JSCC_LINK_MODE:-iq-direct}"',
        'ANALOG_REMOTE_DECODE_RESULT_MODE="${ANALOG_REMOTE_DECODE_RESULT_MODE:-remote-dir}"',
        'ANALOG_SPS="${ANALOG_SPS:-2}"',
        'ANALOG_AMPLITUDE="${ANALOG_AMPLITUDE:-6000}"',
        'ANALOG_RX_TAIL_SEC="${ANALOG_RX_TAIL_SEC:-0.05}"',
        'PERSISTENT_RX_TX_DELAY="${PERSISTENT_RX_TX_DELAY:-0}"',
        'ANALOG_MIN_SYNC_METRIC="${ANALOG_MIN_SYNC_METRIC:-0.05}"',
        'ANALOG_ROBUST_SYNC="${ANALOG_ROBUST_SYNC:-0}"',
        'ANALOG_REMOTE_CLEANUP_MODE="${ANALOG_REMOTE_CLEANUP_MODE:-skip}"',
        'USRP_MAX_ARQ_ROUNDS="${USRP_MAX_ARQ_ROUNDS:-1}"',
        'OPENAMP_TVM_BATCH_RUNNER="${OPENAMP_TVM_BATCH_RUNNER:-biglittle}"',
    )
    powershell_defaults = (
        '$env:REMOTE_HOST = "100.121.87.73"',
        '$env:REMOTE_USER = "user"',
        '$env:REMOTE_SSH_PORT = "22"',
        '$env:OPENAMP_SSH_RUNNER = "paramiko"',
        '$env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER = "1"',
        '$env:OPENAMP_USRP_TX_RUNNER = "docker"',
        '$env:OPENAMP_USRP_TX_DOCKER_IMAGE = "iccomp-usrp-tx:latest"',
        '$env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET = "/host_workspace"',
        '$env:REMOTE_USRP_RX_DIR = "/home/user/cockpit_usrp_rx"',
        '$env:REMOTE_RX_RUN_ROOT = "/tmp/usrp292x_remote_runs"',
        '$env:REMOTE_USRP_PROJECT_ROOT = "/home/user"',
        '$env:REMOTE_USRP_DECODE_PYTHON = "/home/user/venv/bin/python"',
        '$env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON = "/home/user/venv/bin/python"',
        '$env:JSCC_LINK_MODE = "iq-direct"',
        '$env:ANALOG_REMOTE_DECODE_RESULT_MODE = "remote-dir"',
        '$env:ANALOG_SPS = "2"',
        '$env:ANALOG_AMPLITUDE = "6000"',
        '$env:ANALOG_RX_TAIL_SEC = "0.05"',
        '$env:PERSISTENT_RX_TX_DELAY = "0"',
        '$env:ANALOG_MIN_SYNC_METRIC = "0.05"',
        '$env:ANALOG_ROBUST_SYNC = "0"',
        '$env:ANALOG_REMOTE_CLEANUP_MODE = "skip"',
        '$env:USRP_MAX_ARQ_ROUNDS = "1"',
        '$env:OPENAMP_TVM_BATCH_RUNNER = "biglittle"',
    )

    for expected in shell_defaults:
        assert expected in shell_script
    for expected in powershell_defaults:
        assert expected in powershell_script


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


def test_prepare_iq_board_sync_manifest_activates_board_tvm_env_for_validation() -> None:
    script = (PROJECT_ROOT / "scripts" / "prepare_iq_board_sync.sh").read_text(encoding="utf-8")
    validation_section = script.split("## 同步后板端验证", 1)[1]

    assert "conda activate tvm310_safe" in validation_section
    assert "python -m pytest test_analog_latent_link.py -v" in validation_section
    assert "python /home/user/USRP292x/RunAnalogLatentBatch.py --help | head -3" in validation_section
    assert "python3 -m pytest test_analog_latent_link.py -v" not in validation_section


def test_prepare_iq_board_sync_powershell_wrapper_runs_docker_packager() -> None:
    script = read_script("prepare-iq-board-sync.ps1")

    assert "iccomp-ubuntu-minimal" in script
    assert '"/workspace"' in script
    assert "REPO_ROOT=/workspace" in script
    assert "OUT_TAR=/workspace/artifacts/iq_board_sync.tar.gz" in script
    assert "OUT_MANIFEST=/workspace/artifacts/iq_board_sync_manifest.txt" in script
    assert "scripts/prepare_iq_board_sync.sh" in script


def test_big_little_wrapper_intermediate_json_is_ascii_safe() -> None:
    script = (PROJECT_ROOT / "Semantic-Communication" / "session_bootstrap" / "scripts" / "run_big_little_pipeline.sh").read_text(
        encoding="utf-8"
    )

    assert "json.dumps(payload, ensure_ascii=True)" in script
