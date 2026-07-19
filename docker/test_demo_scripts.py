from __future__ import annotations

import importlib.util
from pathlib import Path


DOCKER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DOCKER_DIR.parent


def load_tcp_forward_module():
    path = PROJECT_ROOT / "scripts" / "tcp_forward.py"
    spec = importlib.util.spec_from_file_location("tcp_forward", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tcp_forward_resolves_docker_bridge_gateway(tmp_path: Path) -> None:
    route = tmp_path / "route"
    route.write_text(
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
        "eth0\t00000000\t010011AC\t0003\t0\t0\t0\t00000000\n",
        encoding="ascii",
    )

    module = load_tcp_forward_module()

    assert module.resolve_target_host("docker-gateway", route_path=route) == "172.17.0.1"


def read_script(name: str) -> str:
    return (DOCKER_DIR / name).read_text(encoding="utf-8")


def test_start_electron_has_tvm250_profile_and_fast_iq_defaults() -> None:
    script = read_script("start-electron-prod-demo.sh")

    assert "ICCOMP_COCKPIT_PROFILE" in script
    assert "tvm250-prerecorded" in script
    assert 'OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"' in script
    assert 'MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-tcp}"' in script
    assert 'MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"' in script
    assert 'MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"' in script
    assert 'JSCC_LINK_MODE="${JSCC_LINK_MODE:-iq-direct}"' in script
    assert 'ANALOG_REMOTE_DECODE_RESULT_MODE="${ANALOG_REMOTE_DECODE_RESULT_MODE:-remote-dir}"' in script
    assert 'ANALOG_IN_PROCESS_LOCAL_CODEC="${ANALOG_IN_PROCESS_LOCAL_CODEC:-1}"' in script
    assert 'ANALOG_WARMUP_LOCAL_CODEC="${ANALOG_WARMUP_LOCAL_CODEC:-1}"' in script
    assert 'ANALOG_SPS="${ANALOG_SPS:-2}"' in script
    assert 'ANALOG_AMPLITUDE="${ANALOG_AMPLITUDE:-6000}"' in script
    assert 'ANALOG_RX_TAIL_SEC="${ANALOG_RX_TAIL_SEC:-0.05}"' in script
    assert 'ANALOG_RX_POST_QUANTIZE="${ANALOG_RX_POST_QUANTIZE:-0}"' in script
    assert 'PERSISTENT_RX_TX_DELAY="${PERSISTENT_RX_TX_DELAY:-0}"' in script
    assert 'ANALOG_MIN_SYNC_METRIC="${ANALOG_MIN_SYNC_METRIC:-0.05}"' in script
    assert 'ANALOG_ROBUST_SYNC="${ANALOG_ROBUST_SYNC:-0}"' in script
    assert 'ANALOG_REMOTE_CLEANUP_MODE="${ANALOG_REMOTE_CLEANUP_MODE:-async}"' in script
    assert 'ANALOG_REMOTE_DECODE_WORKER="${ANALOG_REMOTE_DECODE_WORKER:-1}"' in script
    assert 'ANALOG_DECODE_PIPELINE_WARMUP="${ANALOG_DECODE_PIPELINE_WARMUP:-1}"' in script
    assert 'OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="${OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT:-0}"' in script
    assert 'USRP_MAX_ARQ_ROUNDS="${USRP_MAX_ARQ_ROUNDS:-12}"' in script
    assert 'OPENAMP_IQ_SEGMENT_SIZE="${OPENAMP_IQ_SEGMENT_SIZE:-30}"' in script
    assert 'OPENAMP_IQ_SEGMENT_REPAIR_PASSES="${OPENAMP_IQ_SEGMENT_REPAIR_PASSES:-2}"' in script
    assert 'REMOTE_USRP_DECODE_PYTHON="${REMOTE_USRP_DECODE_PYTHON:-/home/user/venv/bin/python}"' in script
    assert 'OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"' in script


def test_start_dev_defaults_enable_auth_and_protect_remote_auth_paths_from_msys() -> None:
    script = (PROJECT_ROOT / "Semantic-Communication" / "cockpit_desktop" / "start-dev.sh").read_text(
        encoding="utf-8"
    )

    assert 'MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"' in script
    assert 'MLKEM_CIPHER_SUITE="${MLKEM_CIPHER_SUITE:-SM4_GCM}"' in script
    assert "run_startup_usrp_readiness" in script
    assert '"/api/usrp-control/start"' in script
    assert '"/api/crypto-status"' in script
    assert 'PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"' in script
    assert 'PYTHONUTF8="${PYTHONUTF8:-1}"' in script
    for expected in (
        'ANALOG_SYNC_PROFILE="${ANALOG_SYNC_PROFILE:-fast-first}"',
        'ANALOG_FAST_SYNC_CANDIDATES="${ANALOG_FAST_SYNC_CANDIDATES:-4}"',
        'ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS="${ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS:-1024}"',
        'ANALOG_FALLBACK_SYNC_CANDIDATES="${ANALOG_FALLBACK_SYNC_CANDIDATES:-4}"',
        'ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS="${ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS:-1024}"',
        'ANALOG_IQ_QUALITY_GATE="${ANALOG_IQ_QUALITY_GATE:-1}"',
        'ANALOG_IQ_QUALITY_MIN_SYNC_METRIC="${ANALOG_IQ_QUALITY_MIN_SYNC_METRIC:-0.75}"',
        'ANALOG_IQ_MIN_PILOT_GAIN_RATIO="${ANALOG_IQ_MIN_PILOT_GAIN_RATIO:-0.85}"',
        'ANALOG_IQ_MAX_EVM_RMS="${ANALOG_IQ_MAX_EVM_RMS:-0.75}"',
        'ANALOG_IQ_MIN_SNR_DB="${ANALOG_IQ_MIN_SNR_DB:-3.0}"',
        'OPENAMP_IQ_SEGMENT_SIZE="${OPENAMP_IQ_SEGMENT_SIZE:-30}"',
        'OPENAMP_IQ_SEGMENT_REPAIR_PASSES="${OPENAMP_IQ_SEGMENT_REPAIR_PASSES:-2}"',
    ):
        assert expected in script
    for name in (
        "MLKEM_AUTH_SERVER_SM2_KEY",
        "MLKEM_AUTH_SERVER_SM2_PUB",
        "MLKEM_AUTH_SERVER_MLDSA_KEY",
        "MLKEM_AUTH_SERVER_MLDSA_PUB",
    ):
        assert name in script.split('msys_env_exclusions="', 1)[1].split('"', 1)[0]


def test_start_demo_initializes_services_without_image_warmup() -> None:
    script = (PROJECT_ROOT / "scripts" / "demo" / "start.ps1").read_text(
        encoding="utf-8-sig"
    )

    assert "[int]$WarmupCount" not in script
    assert "[switch]$NoWarmup" not in script
    assert "COCKPIT_STARTUP_USRP_WARMUP" not in script
    assert "no image warmup" in script
    assert 'Set-DefaultEnv "OPENAMP_USRP_TX_DOCKER_NETWORK" "bridge"' in script

    shell_script = (
        PROJECT_ROOT / "Semantic-Communication" / "cockpit_desktop" / "start-dev.sh"
    ).read_text(encoding="utf-8")
    assert "run_startup_usrp_readiness" in shell_script
    assert "run_startup_usrp_readiness\nrun_startup_control_probe" in shell_script


def test_start_demo_recovers_board_usrp_network_before_cockpit_startup() -> None:
    script = (PROJECT_ROOT / "scripts" / "demo" / "start.ps1").read_text(
        encoding="utf-8-sig"
    )

    assert "ConfigureUsrp2922DemoNetwork.ps1" in script
    assert "-Target Board" in script
    assert "-BoardInterface eth0" in script
    assert "-Fast" in script
    assert "Board RX USRP network recovery" in script


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
        "RX_ARM_WAIT_MS",
        "RX_STOP_WAIT_MS",
        "REMOTE_USRP_DECODE_PYTHON",
        "OPENAMP_DEMO_REMOTE_DECODE_PYTHON",
        "JSCC_LINK_MODE",
        "OPENAMP_DEMO_LINK_MODE",
        "ANALOG_IN_PROCESS_LOCAL_CODEC",
        "ANALOG_WARMUP_LOCAL_CODEC",
        "ANALOG_SPS",
        "ANALOG_AMPLITUDE",
        "ANALOG_RX_TAIL_SEC",
        "ANALOG_RX_POST_QUANTIZE",
        "ANALOG_REMOTE_DECODED_FORMAT",
        "ANALOG_REMOTE_STALL_SNAPSHOT",
        "ANALOG_REMOTE_STALL_SNAPSHOT_THRESHOLD_SEC",
        "ANALOG_REMOTE_STALL_SNAPSHOT_LIMIT",
        "ANALOG_RX_WAIT_TIMEOUT_SEC",
        "ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC",
        "ANALOG_RX_ARM_STATUS_TIMEOUT_SEC",
        "ANALOG_RX_ARM_STATUS_POLL_SEC",
        "ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC",
        "ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC",
        "ANALOG_RX_STOP_DRAIN_POLL_SEC",
        "PERSISTENT_RX_TX_DELAY",
        "ANALOG_REMOTE_CLEANUP_MODE",
        "ANALOG_REMOTE_DECODE_WORKER",
        "ANALOG_REMOTE_DECODE_WORKER_PREFIX",
        "ANALOG_PRECONNECT_CONTROL",
        "ANALOG_PRECONNECT_RX_CAPTURE_CONTROL",
        "ANALOG_RX_SESSION_CONTROL",
        "ANALOG_RX_BATCH_SESSION_CONTROL",
        "ANALOG_RX_BATCH_SESSION_MAX_IMAGES",
        "ANALOG_PIPELINE_DEPTH",
        "OPENAMP_IQ_SEGMENT_SIZE",
        "OPENAMP_IQ_SEGMENT_REPAIR_PASSES",
        "ANALOG_DECODE_PIPELINE_WARMUP",
        "ANALOG_DECODE_WARMUP_SHAPE",
        "ANALOG_REMOTE_DECODE_RESULT_MODE",
        "ANALOG_REMOTE_DECODED_OUTPUT_DIR",
        "ANALOG_REMOTE_DECODE_RESPONSE_MODE",
        "ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY",
        "ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC",
        "ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_SEC",
        "ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC",
        "ANALOG_MIN_SYNC_METRIC",
        "ANALOG_ROBUST_SYNC",
        "OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT",
        "USRP_SHUTDOWN_CONTROL_AFTER_TRANSPORT",
        "USRP_MAX_ARQ_ROUNDS",
        "MLKEM_USRP_MAX_ARQ_ROUNDS",
        "MLKEM_TRANSPORT_MODE",
        "MLKEM_USRP_MODE",
        "MLKEM_CIPHER_SUITE",
        "MLKEM_AUTH_ENABLED",
        "MLKEM_AUTH_SIG_POLICY",
        "OPENAMP_SSH_RUNNER",
        "OPENAMP_SSH_DOCKER_IMAGE",
        "SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER",
        "OPENAMP_USRP_TX_RUNNER",
        "OPENAMP_USRP_TX_DOCKER_IMAGE",
        "OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET",
        "OPENAMP_USRP_TX_DOCKER_NETWORK",
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
        'OPENAMP_SSH_RUNNER="${OPENAMP_SSH_RUNNER:-docker}"',
        'OPENAMP_SSH_DOCKER_IMAGE="${OPENAMP_SSH_DOCKER_IMAGE:-iccomp-usrp-tx:latest}"',
        'SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER="${SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER:-1}"',
        'OPENAMP_USRP_TX_RUNNER="${OPENAMP_USRP_TX_RUNNER:-docker}"',
        'OPENAMP_USRP_TX_DOCKER_IMAGE="${OPENAMP_USRP_TX_DOCKER_IMAGE:-iccomp-usrp-tx:latest}"',
        'OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET="${OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET:-/host_workspace}"',
        'OPENAMP_USRP_TX_DOCKER_NETWORK="${OPENAMP_USRP_TX_DOCKER_NETWORK:-$default_tx_docker_network}"',
        'REMOTE_USRP_RX_DIR="${REMOTE_USRP_RX_DIR:-/home/user/cockpit_usrp_rx}"',
        'REMOTE_RX_RUN_ROOT="${REMOTE_RX_RUN_ROOT:-/dev/shm/usrp292x_remote_runs}"',
        'REMOTE_USRP_PROJECT_ROOT="${REMOTE_USRP_PROJECT_ROOT:-/home/user}"',
        'REMOTE_USRP_DECODE_PYTHON="${REMOTE_USRP_DECODE_PYTHON:-/home/user/venv/bin/python}"',
        'OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"',
        'MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-usrp}"',
        'MLKEM_USRP_MODE="${MLKEM_USRP_MODE:-ota}"',
        'OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-usrp}"',
        'JSCC_LINK_MODE="${JSCC_LINK_MODE:-iq-direct}"',
        'OPENAMP_DEMO_LINK_MODE="${OPENAMP_DEMO_LINK_MODE:-iq-direct}"',
        'MLKEM_CIPHER_SUITE="${MLKEM_CIPHER_SUITE:-SM4_GCM}"',
        'OPENAMP_IQ_STREAMING_TVM="${OPENAMP_IQ_STREAMING_TVM:-0}"',
        'OPENAMP_IQ_STREAMING_MIN_READY="${OPENAMP_IQ_STREAMING_MIN_READY:-10}"',
        'OPENAMP_IQ_SEGMENT_SIZE="${OPENAMP_IQ_SEGMENT_SIZE:-30}"',
        'OPENAMP_IQ_SEGMENT_REPAIR_PASSES="${OPENAMP_IQ_SEGMENT_REPAIR_PASSES:-2}"',
        'BIG_LITTLE_INPUT_CHUNK_SIZE="${BIG_LITTLE_INPUT_CHUNK_SIZE:-10}"',
        'ANALOG_REMOTE_DECODE_RESULT_MODE="${ANALOG_REMOTE_DECODE_RESULT_MODE:-remote-dir}"',
        'ANALOG_REMOTE_DECODE_RESPONSE_MODE="${ANALOG_REMOTE_DECODE_RESPONSE_MODE:-minimal}"',
        'ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY="${ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY:-1}"',
        'ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC="${ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC:-0.05}"',
        'ANALOG_REMOTE_DECODED_FORMAT="${ANALOG_REMOTE_DECODED_FORMAT:-npy}"',
        'ANALOG_SYNC_FFT_WARMUP="${ANALOG_SYNC_FFT_WARMUP:-0}"',
        'RX_ARM_WAIT_MS="${RX_ARM_WAIT_MS:-500}"',
        'RX_STOP_WAIT_MS="${RX_STOP_WAIT_MS:-8000}"',
        'ANALOG_PIPELINE_DEPTH="${ANALOG_PIPELINE_DEPTH:-1}"',
        'ANALOG_PIPELINE_RF_DECODE_OVERLAP="${ANALOG_PIPELINE_RF_DECODE_OVERLAP:-0}"',
        'ANALOG_SPS="${ANALOG_SPS:-2}"',
        'ANALOG_AMPLITUDE="${ANALOG_AMPLITUDE:-6000}"',
        'ANALOG_RX_POST_QUANTIZE="${ANALOG_RX_POST_QUANTIZE:-0}"',
        'ANALOG_RX_TAIL_SEC="${ANALOG_RX_TAIL_SEC:-0.040}"',
        'ANALOG_RX_SC16_MMAP="${ANALOG_RX_SC16_MMAP:-1}"',
        'ANALOG_RX_CLIPPING_DECIMATION="${ANALOG_RX_CLIPPING_DECIMATION:-8}"',
        'ANALOG_RX_WAIT_TIMEOUT_SEC="${ANALOG_RX_WAIT_TIMEOUT_SEC:-1.0}"',
        'ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC="${ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC:-1.0}"',
        'ANALOG_RX_ARM_STATUS_TIMEOUT_SEC="${ANALOG_RX_ARM_STATUS_TIMEOUT_SEC:-0.5}"',
        'ANALOG_RX_ARM_STATUS_POLL_SEC="${ANALOG_RX_ARM_STATUS_POLL_SEC:-0.025}"',
        'ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC="${ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC:-8.0}"',
        'ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC="${ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC:-1.5}"',
        'PERSISTENT_RX_TX_DELAY="${PERSISTENT_RX_TX_DELAY:-0}"',
        'ANALOG_MIN_SYNC_METRIC="${ANALOG_MIN_SYNC_METRIC:-0.05}"',
        'ANALOG_ROBUST_SYNC="${ANALOG_ROBUST_SYNC:-0}"',
        'ANALOG_REMOTE_CLEANUP_MODE="${ANALOG_REMOTE_CLEANUP_MODE:-skip}"',
        'ANALOG_PRECONNECT_CONTROL="${ANALOG_PRECONNECT_CONTROL:-1}"',
        'ANALOG_PRECONNECT_RX_CAPTURE_CONTROL="${ANALOG_PRECONNECT_RX_CAPTURE_CONTROL:-0}"',
        'ANALOG_RX_SESSION_CONTROL="${ANALOG_RX_SESSION_CONTROL:-1}"',
        'ANALOG_RX_BATCH_SESSION_CONTROL="${ANALOG_RX_BATCH_SESSION_CONTROL:-1}"',
        'ANALOG_RX_BATCH_SESSION_MAX_IMAGES="${ANALOG_RX_BATCH_SESSION_MAX_IMAGES:-16}"',
        'ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS="${ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS:-1}"',
        'ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK="${ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK:-80}"',
        'ANALOG_DECODE_PIPELINE_WARMUP="${ANALOG_DECODE_PIPELINE_WARMUP:-1}"',
        'OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="${OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT:-0}"',
        'USRP_MAX_ARQ_ROUNDS="${USRP_MAX_ARQ_ROUNDS:-12}"',
        'ANALOG_FALLBACK_SYNC_CANDIDATES="${ANALOG_FALLBACK_SYNC_CANDIDATES:-4}"',
        'ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS="${ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS:-1024}"',
        'ANALOG_IQ_QUALITY_GATE="${ANALOG_IQ_QUALITY_GATE:-1}"',
        'ANALOG_IQ_QUALITY_MIN_SYNC_METRIC="${ANALOG_IQ_QUALITY_MIN_SYNC_METRIC:-0.75}"',
        'ANALOG_IQ_MIN_PILOT_GAIN_RATIO="${ANALOG_IQ_MIN_PILOT_GAIN_RATIO:-0.85}"',
        'ANALOG_IQ_MAX_EVM_RMS="${ANALOG_IQ_MAX_EVM_RMS:-0.75}"',
        'ANALOG_IQ_MIN_SNR_DB="${ANALOG_IQ_MIN_SNR_DB:-3.0}"',
        'OPENAMP_TVM_BATCH_RUNNER="${OPENAMP_TVM_BATCH_RUNNER:-biglittle}"',
        'OPENAMP_DEMO_TVM_BATCH_RUNNER="${OPENAMP_DEMO_TVM_BATCH_RUNNER:-biglittle}"',
        'MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"',
        'MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"',
    )
    powershell_defaults = (
        '$env:REMOTE_HOST = "100.121.87.73"',
        '$env:REMOTE_USER = "user"',
        '$env:REMOTE_SSH_PORT = "22"',
        '$env:OPENAMP_SSH_RUNNER = "docker"',
        '$env:OPENAMP_SSH_DOCKER_IMAGE = "iccomp-usrp-tx:latest"',
        '$env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER = "1"',
        '$env:OPENAMP_USRP_TX_RUNNER = "docker"',
        '$env:OPENAMP_USRP_TX_DOCKER_IMAGE = "iccomp-usrp-tx:latest"',
        '$env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET = "/host_workspace"',
        '$env:OPENAMP_USRP_TX_DOCKER_NETWORK = "bridge"',
        '$env:REMOTE_USRP_RX_DIR = "/home/user/cockpit_usrp_rx"',
        '$env:REMOTE_RX_RUN_ROOT = "/dev/shm/usrp292x_remote_runs"',
        '$env:REMOTE_USRP_PROJECT_ROOT = "/home/user"',
        '$env:REMOTE_USRP_DECODE_PYTHON = "/home/user/venv/bin/python"',
        '$env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON = "/home/user/venv/bin/python"',
        '$env:MLKEM_TRANSPORT_MODE = "usrp"',
        '$env:MLKEM_USRP_MODE = "ota"',
        '$env:OPENAMP_DEMO_INPUT_SOURCE_MODE = "usrp"',
        '$env:JSCC_LINK_MODE = "iq-direct"',
        '$env:OPENAMP_DEMO_LINK_MODE = "iq-direct"',
        '$env:MLKEM_CIPHER_SUITE = "SM4_GCM"',
        '$env:OPENAMP_IQ_STREAMING_TVM = "0"',
        '$env:OPENAMP_IQ_STREAMING_MIN_READY = "10"',
        '$env:OPENAMP_IQ_SEGMENT_SIZE = "30"',
        '$env:OPENAMP_IQ_SEGMENT_REPAIR_PASSES = "2"',
        '$env:BIG_LITTLE_INPUT_CHUNK_SIZE = "10"',
        '$env:ANALOG_REMOTE_DECODE_RESULT_MODE = "remote-dir"',
        '$env:ANALOG_REMOTE_DECODE_RESPONSE_MODE = "minimal"',
        '$env:ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY = "1"',
        '$env:ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC = "0.05"',
        '$env:ANALOG_REMOTE_DECODED_FORMAT = "npy"',
        '$env:ANALOG_SYNC_FFT_WARMUP = "0"',
        '$env:RX_ARM_WAIT_MS = "500"',
        '$env:RX_STOP_WAIT_MS = "8000"',
        '$env:ANALOG_PIPELINE_DEPTH = "1"',
        '$env:ANALOG_PIPELINE_RF_DECODE_OVERLAP = "0"',
        '$env:ANALOG_SPS = "2"',
        '$env:ANALOG_AMPLITUDE = "6000"',
        '$env:ANALOG_RX_POST_QUANTIZE = "0"',
        '$env:ANALOG_RX_TAIL_SEC = "0.040"',
        '$env:ANALOG_RX_SC16_MMAP = "1"',
        '$env:ANALOG_RX_CLIPPING_DECIMATION = "8"',
        '$env:ANALOG_RX_WAIT_TIMEOUT_SEC = "1.0"',
        '$env:ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC = "1.0"',
        '$env:ANALOG_RX_ARM_STATUS_TIMEOUT_SEC = "0.5"',
        '$env:ANALOG_RX_ARM_STATUS_POLL_SEC = "0.025"',
        '$env:ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC = "8.0"',
        '$env:ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC = "1.5"',
        '$env:PERSISTENT_RX_TX_DELAY = "0"',
        '$env:ANALOG_MIN_SYNC_METRIC = "0.05"',
        '$env:ANALOG_ROBUST_SYNC = "0"',
        '$env:ANALOG_REMOTE_CLEANUP_MODE = "skip"',
        '$env:ANALOG_PRECONNECT_CONTROL = "1"',
        '$env:ANALOG_PRECONNECT_RX_CAPTURE_CONTROL = "0"',
        '$env:ANALOG_RX_SESSION_CONTROL = "1"',
        '$env:ANALOG_RX_BATCH_SESSION_CONTROL = "1"',
        '$env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES = "16"',
        '$env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS = "1"',
        '$env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK = "80"',
        '$env:ANALOG_DECODE_PIPELINE_WARMUP = "1"',
        '$env:OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT = "0"',
        '$env:USRP_MAX_ARQ_ROUNDS = "12"',
        '$env:ANALOG_FALLBACK_SYNC_CANDIDATES = "4"',
        '$env:ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS = "1024"',
        '$env:ANALOG_IQ_QUALITY_GATE = "1"',
        '$env:ANALOG_IQ_QUALITY_MIN_SYNC_METRIC = "0.75"',
        '$env:ANALOG_IQ_MIN_PILOT_GAIN_RATIO = "0.85"',
        '$env:ANALOG_IQ_MAX_EVM_RMS = "0.75"',
        '$env:ANALOG_IQ_MIN_SNR_DB = "3.0"',
        '$env:OPENAMP_TVM_BATCH_RUNNER = "biglittle"',
        '$env:OPENAMP_DEMO_TVM_BATCH_RUNNER = "biglittle"',
        '$env:MLKEM_AUTH_ENABLED = "1"',
        '$env:MLKEM_AUTH_SIG_POLICY = "DUAL_REQUIRED"',
    )

    for expected in shell_defaults:
        assert expected in shell_script
    for expected in powershell_defaults:
        assert expected in powershell_script
    for rejected in (
        'ANALOG_REMOTE_DECODE_WORKER_PREFIX="${ANALOG_REMOTE_DECODE_WORKER_PREFIX:-taskset -c 0,1}"',
        'ANALOG_PIPELINE_DEPTH="${ANALOG_PIPELINE_DEPTH:-2}"',
        'ANALOG_PIPELINE_RF_DECODE_OVERLAP="${ANALOG_PIPELINE_RF_DECODE_OVERLAP:-1}"',
        'ANALOG_RX_BATCH_SESSION_MAX_IMAGES="${ANALOG_RX_BATCH_SESSION_MAX_IMAGES:-10}"',
    ):
        assert rejected not in shell_script
    for rejected in (
        '$env:ANALOG_REMOTE_DECODE_WORKER_PREFIX = "taskset -c 0,1"',
        '$env:ANALOG_PIPELINE_DEPTH = "2"',
        '$env:ANALOG_PIPELINE_RF_DECODE_OVERLAP = "1"',
        '$env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES = "10"',
    ):
        assert rejected not in powershell_script


def test_prepare_iq_board_sync_manifest_avoids_password_placeholder_and_lists_all_files() -> None:
    script = (PROJECT_ROOT / "scripts" / "prepare_iq_board_sync.sh").read_text(encoding="utf-8")
    extract_section = script.split("## 板端解压命令", 1)[1].split("## 同步后板端验证", 1)[0]

    assert "SSHPASS=user" not in script
    assert "SSHPASS=<board password>" not in script
    for rel_path in (
        "USRP292x/RunAnalogLatentBatch.py",
        "USRP292x/AnalogLatentLink.py",
        "USRP292x/test_analog_latent_link.py",
        "USRP292x/OtaRxPersistentServer.cpp",
        "USRP292x/OtaRxPersistentServer.sh",
        "USRP292x/OtaTxPersistentServer.cpp",
        "USRP292x/OtaTxPersistentServer.sh",
        "USRP292x/BuildOtaTools.sh",
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
    assert "python -m py_compile RunAnalogLatentBatch.py AnalogLatentLink.py" in validation_section
    assert "python /home/user/USRP292x/RunAnalogLatentBatch.py --help | head -3" in validation_section
    assert "OTA_TARGETS='OtaRxPersistentServer OtaTxPersistentServer' bash BuildOtaTools.sh" in validation_section
    assert "python -m pytest" not in validation_section


def test_prepare_iq_board_sync_powershell_wrapper_runs_docker_packager() -> None:
    script = read_script("prepare-iq-board-sync.ps1")

    assert "iccomp-ubuntu-minimal" in script
    assert '"/workspace"' in script
    assert "REPO_ROOT=/workspace" in script
    assert "OUT_TAR=/workspace/artifacts/iq_board_sync.tar.gz" in script
    assert "OUT_MANIFEST=/workspace/artifacts/iq_board_sync_manifest.txt" in script
    assert "scripts/prepare_iq_board_sync.sh" in script


def test_prepare_iq_board_sync_powershell_wrapper_can_deploy_with_docker() -> None:
    script = read_script("prepare-iq-board-sync.ps1")

    for expected in (
        "[switch]$Deploy",
        "[switch]$Verify",
        '[string]$BoardHost = "100.121.87.73"',
        '[string]$BoardUser = "user"',
        "[int]$BoardPort = 22",
        "sshpass -e scp",
        "REMOTE_HOST=$BoardHost",
        "REMOTE_USER=$BoardUser",
        "REMOTE_SSH_PORT=$BoardPort",
    ):
        assert expected in script

    assert "if (-not $Deploy)" in script
    assert "conda activate tvm310_safe" in script
    assert "python -m py_compile RunAnalogLatentBatch.py AnalogLatentLink.py" in script
    assert "python -m pytest" not in script
    assert "docker/start-tailscale.sh" not in script
    assert "--cap-add=NET_ADMIN" not in script
    assert "| cut -d ' ' -f1)" in script
    assert "awk '{print \\\\$1}'" not in script


def test_big_little_wrapper_intermediate_json_is_ascii_safe() -> None:
    script = (PROJECT_ROOT / "Semantic-Communication" / "session_bootstrap" / "scripts" / "run_big_little_pipeline.sh").read_text(
        encoding="utf-8"
    )

    assert "json.dumps(payload, ensure_ascii=True)" in script


def test_big_little_wrapper_passes_dynamic_input_wait_knobs() -> None:
    script = (PROJECT_ROOT / "Semantic-Communication" / "session_bootstrap" / "scripts" / "run_big_little_pipeline.sh").read_text(
        encoding="utf-8"
    )

    assert "INPUT_WAIT_TIMEOUT_SEC=\"${BIG_LITTLE_INPUT_WAIT_TIMEOUT_SEC:-0}\"" in script
    assert "INPUT_POLL_SEC=\"${BIG_LITTLE_INPUT_POLL_SEC:-0.05}\"" in script
    assert "--input-wait-timeout-sec" in script
    assert "--input-poll-sec" in script
