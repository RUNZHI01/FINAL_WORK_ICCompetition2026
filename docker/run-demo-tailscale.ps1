$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$env:ENABLE_TAILSCALE = "1"
if (-not $env:ICCOMP_COCKPIT_PROFILE) {
    $env:ICCOMP_COCKPIT_PROFILE = "tvm250-prerecorded"
}
if (-not $env:CONTAINER_NAME) {
    $env:CONTAINER_NAME = "iccomp-electron-demo-tailscale"
}
if (-not $env:TAILSCALE_HOSTNAME) {
    $env:TAILSCALE_HOSTNAME = "iccomp-demo"
}
if (-not $env:TAILSCALE_PING_TARGET) {
    $env:TAILSCALE_PING_TARGET = "100.121.87.73"
}
if (-not $env:REMOTE_HOST) {
    $env:REMOTE_HOST = "100.121.87.73"
}
if (-not $env:REMOTE_USER) {
    $env:REMOTE_USER = "user"
}
if (-not $env:REMOTE_SSH_PORT) {
    $env:REMOTE_SSH_PORT = "22"
}
if (-not $env:OPENAMP_SSH_RUNNER) {
    $env:OPENAMP_SSH_RUNNER = "docker"
}
if (-not $env:OPENAMP_SSH_DOCKER_IMAGE) {
    $env:OPENAMP_SSH_DOCKER_IMAGE = "iccomp-usrp-tx:latest"
}
if (-not $env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER) {
    $env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER = "1"
}
if (-not $env:OPENAMP_USRP_TX_RUNNER) {
    $env:OPENAMP_USRP_TX_RUNNER = "docker"
}
if (-not $env:OPENAMP_USRP_TX_DOCKER_IMAGE) {
    $env:OPENAMP_USRP_TX_DOCKER_IMAGE = "iccomp-usrp-tx:latest"
}
if (-not $env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET) {
    $env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET = "/host_workspace"
}
if (-not $env:REMOTE_USRP_RX_DIR) {
    $env:REMOTE_USRP_RX_DIR = "/home/user/cockpit_usrp_rx"
}
if (-not $env:REMOTE_RX_RUN_ROOT) {
    $env:REMOTE_RX_RUN_ROOT = "/dev/shm/usrp292x_remote_runs"
}
if (-not $env:REMOTE_USRP_PROJECT_ROOT) {
    $env:REMOTE_USRP_PROJECT_ROOT = "/home/user"
}
if (-not $env:REMOTE_USRP_DECODE_PYTHON) {
    $env:REMOTE_USRP_DECODE_PYTHON = "/home/user/venv/bin/python"
}
if (-not $env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON) {
    $env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON = "/home/user/venv/bin/python"
}
if (-not $env:JSCC_LINK_MODE) {
    $env:JSCC_LINK_MODE = "iq-direct"
}
if ($env:JSCC_LINK_MODE -eq "iq-direct") {
    if (-not $env:OPENAMP_IQ_STREAMING_TVM) {
        $env:OPENAMP_IQ_STREAMING_TVM = "0"
    }
    if (-not $env:OPENAMP_IQ_STREAMING_MIN_READY) {
        $env:OPENAMP_IQ_STREAMING_MIN_READY = "10"
    }
    if (-not $env:BIG_LITTLE_INPUT_CHUNK_SIZE) {
        $env:BIG_LITTLE_INPUT_CHUNK_SIZE = "10"
    }
}
if (-not $env:ANALOG_REMOTE_DECODE_RESULT_MODE) {
    $env:ANALOG_REMOTE_DECODE_RESULT_MODE = "remote-dir"
}
if (-not $env:ANALOG_REMOTE_DECODE_RESPONSE_MODE) {
    $env:ANALOG_REMOTE_DECODE_RESPONSE_MODE = "minimal"
}
if (-not $env:ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY) {
    $env:ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY = "1"
}
if (-not $env:ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC) {
    $env:ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC = "0.05"
}
if (-not $env:ANALOG_REMOTE_DECODED_FORMAT) {
    $env:ANALOG_REMOTE_DECODED_FORMAT = "npy"
}
if ($env:JSCC_LINK_MODE -eq "iq-direct") {
    if (-not $env:ANALOG_REMOTE_DECODE_WORKER_PREFIX) {
        $env:ANALOG_REMOTE_DECODE_WORKER_PREFIX = "taskset -c 0,1"
    }
}
if (-not $env:RX_ARM_WAIT_MS) {
    $env:RX_ARM_WAIT_MS = "500"
}
if (-not $env:RX_STOP_WAIT_MS) {
    $env:RX_STOP_WAIT_MS = "8000"
}
if ($env:JSCC_LINK_MODE -eq "iq-direct") {
    if (-not $env:ANALOG_PIPELINE_DEPTH) {
        $env:ANALOG_PIPELINE_DEPTH = "2"
    }
    if (-not $env:ANALOG_PIPELINE_RF_DECODE_OVERLAP) {
        $env:ANALOG_PIPELINE_RF_DECODE_OVERLAP = "1"
    }
} elseif (-not $env:ANALOG_PIPELINE_DEPTH) {
    $env:ANALOG_PIPELINE_DEPTH = "1"
}
if (-not $env:ANALOG_SPS) {
    $env:ANALOG_SPS = "2"
}
if (-not $env:ANALOG_AMPLITUDE) {
    $env:ANALOG_AMPLITUDE = "6000"
}
if (-not $env:ANALOG_RX_POST_QUANTIZE) {
    $env:ANALOG_RX_POST_QUANTIZE = "0"
}
if (-not $env:ANALOG_RX_TAIL_SEC) {
    $env:ANALOG_RX_TAIL_SEC = "0.040"
}
if (-not $env:ANALOG_RX_SC16_MMAP) {
    $env:ANALOG_RX_SC16_MMAP = "1"
}
if (-not $env:ANALOG_RX_CLIPPING_DECIMATION) {
    $env:ANALOG_RX_CLIPPING_DECIMATION = "8"
}
if (-not $env:ANALOG_RX_WAIT_TIMEOUT_SEC) {
    $env:ANALOG_RX_WAIT_TIMEOUT_SEC = "1.0"
}
if (-not $env:ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC) {
    $env:ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC = "1.0"
}
if (-not $env:ANALOG_RX_ARM_STATUS_TIMEOUT_SEC) {
    $env:ANALOG_RX_ARM_STATUS_TIMEOUT_SEC = "0.5"
}
if (-not $env:ANALOG_RX_ARM_STATUS_POLL_SEC) {
    $env:ANALOG_RX_ARM_STATUS_POLL_SEC = "0.025"
}
if (-not $env:ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC) {
    $env:ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC = "8.0"
}
if (-not $env:ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC) {
    $env:ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC = "1.5"
}
if (-not $env:PERSISTENT_RX_TX_DELAY) {
    $env:PERSISTENT_RX_TX_DELAY = "0"
}
if (-not $env:ANALOG_MIN_SYNC_METRIC) {
    $env:ANALOG_MIN_SYNC_METRIC = "0.05"
}
if (-not $env:ANALOG_ROBUST_SYNC) {
    $env:ANALOG_ROBUST_SYNC = "0"
}
if (-not $env:ANALOG_REMOTE_CLEANUP_MODE) {
    $env:ANALOG_REMOTE_CLEANUP_MODE = "async"
}
if (-not $env:ANALOG_PRECONNECT_CONTROL) {
    $env:ANALOG_PRECONNECT_CONTROL = "1"
}
if (-not $env:ANALOG_PRECONNECT_RX_CAPTURE_CONTROL) {
    $env:ANALOG_PRECONNECT_RX_CAPTURE_CONTROL = "0"
}
if (-not $env:ANALOG_RX_SESSION_CONTROL) {
    $env:ANALOG_RX_SESSION_CONTROL = "1"
}
if (-not $env:ANALOG_RX_BATCH_SESSION_CONTROL) {
    $env:ANALOG_RX_BATCH_SESSION_CONTROL = "1"
}
if ($env:JSCC_LINK_MODE -eq "iq-direct") {
    if (-not $env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES) {
        $env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES = "10"
    }
} elseif (-not $env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES) {
    $env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES = "16"
}
if (-not $env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS) {
    $env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS = "1"
}
if (-not $env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK) {
    $env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK = "80"
}
if (-not $env:ANALOG_DECODE_PIPELINE_WARMUP) {
    $env:ANALOG_DECODE_PIPELINE_WARMUP = "1"
}
if (-not $env:OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT) {
    $env:OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT = "0"
}
if (-not $env:MLKEM_USRP_MAX_ARQ_ROUNDS) {
    $env:MLKEM_USRP_MAX_ARQ_ROUNDS = "5"
}
if (-not $env:USRP_MAX_ARQ_ROUNDS) {
    $env:USRP_MAX_ARQ_ROUNDS = "5"
}
if (-not $env:ANALOG_RETRY_ON_BURST_MISS) {
    $env:ANALOG_RETRY_ON_BURST_MISS = "1"
}
if (-not $env:ANALOG_RETRY_ON_LOW_SYNC) {
    $env:ANALOG_RETRY_ON_LOW_SYNC = "1"
}
if (-not $env:ANALOG_LOW_SYNC_RETRY_THRESHOLD) {
    $env:ANALOG_LOW_SYNC_RETRY_THRESHOLD = "0.08"
}
if (-not $env:ANALOG_FALLBACK_SYNC_CANDIDATES) {
    $env:ANALOG_FALLBACK_SYNC_CANDIDATES = "4"
}
if (-not $env:ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS) {
    $env:ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS = "1024"
}
if (-not $env:OPENAMP_TVM_BATCH_RUNNER) {
    $env:OPENAMP_TVM_BATCH_RUNNER = "biglittle"
}
if (-not $env:OPENAMP_DEMO_TVM_BATCH_RUNNER) {
    $env:OPENAMP_DEMO_TVM_BATCH_RUNNER = "biglittle"
}
if (-not $env:MLKEM_AUTH_ENABLED) {
    $env:MLKEM_AUTH_ENABLED = "1"
}
if (-not $env:MLKEM_AUTH_SIG_POLICY) {
    $env:MLKEM_AUTH_SIG_POLICY = "DUAL_REQUIRED"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "run-demo.ps1")
