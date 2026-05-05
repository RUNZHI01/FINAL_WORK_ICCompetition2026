#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_HELPER_SOURCE="$SCRIPT_DIR/pytorch_reference_reconstruction.py"
SSH_HELPER_SOURCE="$SCRIPT_DIR/ssh_with_password.sh"
if [[ ! -f "$SSH_HELPER_SOURCE" ]]; then
  SSH_HELPER_SOURCE="$REPO_ROOT/session_bootstrap/scripts/ssh_with_password.sh"
fi
DEFAULT_ENV_FILE="$REPO_ROOT/session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env"
DEFAULT_LOCAL_JSCC_ROOT="/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc"

usage() {
  cat <<EOF
Usage:
  run_remote_pytorch_reference_reconstruction.sh [options]

Purpose:
  Generate task-4.1 PyTorch reference reconstructions from the same latent inputs
  used by the trusted Phytium Pi real reconstruction run.

Options:
  --env-file <path>        Optional env snapshot to source before resolving
                           remaining values. Defaults to the validated snapshot
                           only when the current shell has not already provided
                           the remote execution variables.
  --mode <ssh|local>       Override REMOTE_MODE from the env file.
  --python <path>          Python interpreter to use.
  --jscc-root <path>       Upstream jscc repo root.
  --generator-ckpt <path>  Generator state dict, usually export/compressed_gan.pt.
  --origin-ckpt <path>     Full origin checkpoint for manifest provenance.
  --input-dir <path>       Latent input directory.
  --output-dir <path>      Exact run output root.
  --output-prefix <name>   Output root name under REMOTE_OUTPUT_BASE or session_bootstrap/tmp.
  --snr <float>            SNR in dB. Default resolves from trusted env, else 10.
  --noise-mode <awgn|none> Noise mode. Default: awgn
  --seed <int>             Base seed for deterministic per-file AWGN. Default: 20260312
  --max-images <int>       Maximum latent files to process. Default: 300
  --device <device>        Torch device. Default: cpu
  --torch-num-threads <n>  If >0, call torch.set_num_threads(n) in the helper.
  --torch-num-interop-threads <n>
                           If >0, call torch.set_num_interop_threads(n) in the helper.
  --local-disable-mkldnn   Isolated local-workspace experimental switch: disable
                           oneDNN/MKLDNN before model load for this run.
  --local-experimental-subprocess-per-image
                           Local-only experimental mode. Each image reconstruction
                           runs in its own Python subprocess, and the parent
                           helper only schedules work and aggregates results.
  --manifest-name <name>   Manifest filename. Default: pytorch_reference_manifest.json
  --expected-sha256 <sha>  Optional trusted generator checkpoint SHA-256.
  -h, --help               Show this help.

Examples:
  bash ./session_bootstrap/scripts/run_remote_pytorch_reference_reconstruction.sh \\
    --env-file ./session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env \\
    --output-prefix pytorch_reference_reconstruction_20260312 \\
    --seed 20260312

  bash ./session_bootstrap/scripts/run_remote_pytorch_reference_reconstruction.sh \\
    --env-file ./session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env \\
    --output-prefix pytorch_reference_smoke_20260312 \\
    --max-images 1
EOF
}

ENV_FILE=""
MODE_OVERRIDE=""
PYTHON_BIN_OVERRIDE=""
JSCC_ROOT_OVERRIDE=""
GENERATOR_CKPT_OVERRIDE=""
ORIGIN_CKPT_OVERRIDE=""
INPUT_DIR_OVERRIDE=""
OUTPUT_DIR_OVERRIDE=""
OUTPUT_PREFIX_OVERRIDE=""
SNR_OVERRIDE=""
NOISE_MODE="awgn"
SEED="20260312"
MAX_IMAGES="300"
DEVICE="cpu"
TORCH_NUM_THREADS="0"
TORCH_NUM_INTEROP_THREADS="0"
LOCAL_DISABLE_MKLDNN="0"
LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE="0"
MANIFEST_NAME="pytorch_reference_manifest.json"
EXPECTED_SHA256=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --mode)
      MODE_OVERRIDE="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_BIN_OVERRIDE="${2:-}"
      shift 2
      ;;
    --jscc-root)
      JSCC_ROOT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --generator-ckpt)
      GENERATOR_CKPT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --origin-ckpt)
      ORIGIN_CKPT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --input-dir)
      INPUT_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --output-prefix)
      OUTPUT_PREFIX_OVERRIDE="${2:-}"
      shift 2
      ;;
    --snr)
      SNR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --noise-mode)
      NOISE_MODE="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --max-images)
      MAX_IMAGES="${2:-}"
      shift 2
      ;;
    --device)
      DEVICE="${2:-}"
      shift 2
      ;;
    --torch-num-threads)
      TORCH_NUM_THREADS="${2:-}"
      shift 2
      ;;
    --torch-num-interop-threads)
      TORCH_NUM_INTEROP_THREADS="${2:-}"
      shift 2
      ;;
    --local-disable-mkldnn)
      LOCAL_DISABLE_MKLDNN="1"
      shift
      ;;
    --local-experimental-subprocess-per-image)
      LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE="1"
      shift
      ;;
    --manifest-name)
      MANIFEST_NAME="${2:-}"
      shift 2
      ;;
    --expected-sha256)
      EXPECTED_SHA256="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$PYTHON_HELPER_SOURCE" ]]; then
  echo "ERROR: helper source not found: $PYTHON_HELPER_SOURCE" >&2
  exit 1
fi
if [[ ! -f "$SSH_HELPER_SOURCE" ]]; then
  echo "ERROR: ssh helper source not found: $SSH_HELPER_SOURCE" >&2
  exit 1
fi

if [[ -z "$ENV_FILE" ]]; then
  have_runtime_env=0
  for key in REMOTE_MODE REMOTE_HOST REMOTE_USER REMOTE_PASS REMOTE_JSCC_DIR REMOTE_INPUT_DIR REMOTE_OUTPUT_BASE; do
    if [[ -n "${!key:-}" ]]; then
      have_runtime_env=1
      break
    fi
  done
  if [[ "$have_runtime_env" -eq 0 && -f "$DEFAULT_ENV_FILE" ]]; then
    ENV_FILE="$DEFAULT_ENV_FILE"
  fi
fi

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: env file not found: $ENV_FILE" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
}

MODE_RAW="${MODE_OVERRIDE:-${REMOTE_MODE:-ssh}}"
MODE="$(printf '%s' "$MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$MODE" != "ssh" && "$MODE" != "local" ]]; then
  echo "ERROR: mode must be ssh or local (got: $MODE_RAW)" >&2
  exit 1
fi

if [[ ! "$SEED" =~ ^-?[0-9]+$ ]]; then
  echo "ERROR: --seed must be an integer (got: $SEED)" >&2
  exit 1
fi

if ! [[ "$TORCH_NUM_THREADS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --torch-num-threads must be a non-negative integer (got: $TORCH_NUM_THREADS)" >&2
  exit 1
fi

if ! [[ "$TORCH_NUM_INTEROP_THREADS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --torch-num-interop-threads must be a non-negative integer (got: $TORCH_NUM_INTEROP_THREADS)" >&2
  exit 1
fi

if ! [[ "$MAX_IMAGES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-images must be a non-negative integer (got: $MAX_IMAGES)" >&2
  exit 1
fi

if [[ "$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE" != "0" && "$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE" != "1" ]]; then
  echo "ERROR: internal flag LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE must be 0 or 1." >&2
  exit 1
fi

if [[ "$LOCAL_DISABLE_MKLDNN" != "0" && "$LOCAL_DISABLE_MKLDNN" != "1" ]]; then
  echo "ERROR: internal flag LOCAL_DISABLE_MKLDNN must be 0 or 1." >&2
  exit 1
fi

if [[ "$NOISE_MODE" != "awgn" && "$NOISE_MODE" != "none" ]]; then
  echo "ERROR: --noise-mode must be awgn or none (got: $NOISE_MODE)" >&2
  exit 1
fi

if [[ -z "$MAX_IMAGES" && "${OPENAMP_DEMO_MODE:-}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
  MAX_IMAGES="${OPENAMP_DEMO_MAX_INPUTS:-300}"
fi

if [[ "$MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

VARIANT="baseline"
DEFAULT_OUTPUT_PREFIX_STEM="pytorch_reference_reconstruction"
if [[ "$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE" == "1" ]]; then
  VARIANT="local_experimental_subprocess_per_image"
  DEFAULT_OUTPUT_PREFIX_STEM="$VARIANT"
fi
if [[ "$LOCAL_DISABLE_MKLDNN" == "1" ]]; then
  if [[ "$VARIANT" == "baseline" ]]; then
    VARIANT="baseline_mkldnn_disabled"
  else
    VARIANT="${VARIANT}_mkldnn_disabled"
  fi
  DEFAULT_OUTPUT_PREFIX_STEM="${DEFAULT_OUTPUT_PREFIX_STEM}_mkldnn_disabled"
fi

if [[ "$MODE" == "ssh" ]]; then
  JSCC_ROOT="${JSCC_ROOT_OVERRIDE:-${REMOTE_JSCC_DIR:-/home/user/Downloads/jscc-test/jscc}}"
  INPUT_DIR="${INPUT_DIR_OVERRIDE:-${REMOTE_INPUT_DIR:-/home/user/Downloads/jscc-test/简化版latent}}"
  PYTHON_BIN="${PYTHON_BIN_OVERRIDE:-${PYTORCH_REF_REMOTE_PYTHON:-/home/user/anaconda3/envs/myenv/bin/python}}"
  OUTPUT_PREFIX="${OUTPUT_PREFIX_OVERRIDE:-${DEFAULT_OUTPUT_PREFIX_STEM}_$(date +%Y%m%d_%H%M%S)}"
  OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-${REMOTE_OUTPUT_BASE:-/home/user/Downloads/jscc-test/jscc/infer_outputs}/$OUTPUT_PREFIX}"
else
  JSCC_ROOT="${JSCC_ROOT_OVERRIDE:-$DEFAULT_LOCAL_JSCC_ROOT}"
  INPUT_DIR="${INPUT_DIR_OVERRIDE:-$(dirname "$DEFAULT_LOCAL_JSCC_ROOT")/encoder_outputs}"
  PYTHON_BIN="${PYTHON_BIN_OVERRIDE:-python3}"
  OUTPUT_PREFIX="${OUTPUT_PREFIX_OVERRIDE:-${DEFAULT_OUTPUT_PREFIX_STEM}_$(date +%Y%m%d_%H%M%S)}"
  OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$REPO_ROOT/session_bootstrap/tmp/$OUTPUT_PREFIX}"
fi

JSCC_PARENT_DIR="$(dirname "$JSCC_ROOT")"
GENERATOR_CKPT="${GENERATOR_CKPT_OVERRIDE:-$JSCC_PARENT_DIR/export/compressed_gan.pt}"
ORIGIN_CKPT="${ORIGIN_CKPT_OVERRIDE:-$JSCC_PARENT_DIR/origin/1snr_lpips_6_6_6_6_6_6_6_openimages_gan.pt}"
SNR="${SNR_OVERRIDE:-${REMOTE_SNR_CURRENT:-${REMOTE_SNR_BASELINE:-10}}}"

run_helper_args=(
  --jscc-root "$JSCC_ROOT"
  --generator-ckpt "$GENERATOR_CKPT"
  --origin-ckpt "$ORIGIN_CKPT"
  --input-dir "$INPUT_DIR"
  --output-dir "$OUTPUT_DIR"
  --snr "$SNR"
  --noise-mode "$NOISE_MODE"
  --seed "$SEED"
  --max-images "$MAX_IMAGES"
  --device "$DEVICE"
  --torch-num-threads "$TORCH_NUM_THREADS"
  --torch-num-interop-threads "$TORCH_NUM_INTEROP_THREADS"
  --manifest-name "$MANIFEST_NAME"
  --variant "$VARIANT"
)
if [[ -n "$EXPECTED_SHA256" ]]; then
  run_helper_args+=(--expected-sha256 "$EXPECTED_SHA256")
fi
if [[ "$LOCAL_DISABLE_MKLDNN" == "1" ]]; then
  run_helper_args+=(--local-disable-mkldnn)
fi
if [[ "$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE" == "1" ]]; then
  run_helper_args+=(--local-experimental-subprocess-per-image)
fi

echo "[pytorch-ref] mode=$MODE python=$PYTHON_BIN jscc_root=$JSCC_ROOT"
echo "[pytorch-ref] input_dir=$INPUT_DIR output_dir=$OUTPUT_DIR snr=$SNR seed=$SEED max_images=$MAX_IMAGES"
echo "[pytorch-ref] torch_num_threads=$TORCH_NUM_THREADS torch_num_interop_threads=$TORCH_NUM_INTEROP_THREADS"
echo "[pytorch-ref] variant=$VARIANT local_disable_mkldnn=$LOCAL_DISABLE_MKLDNN local_experimental_subprocess_per_image=$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE"
echo "[pytorch-ref] generator_ckpt=$GENERATOR_CKPT origin_ckpt=$ORIGIN_CKPT"
if [[ -n "$ENV_FILE" ]]; then
  echo "[pytorch-ref] env_file=$ENV_FILE"
fi
if [[ -n "$EXPECTED_SHA256" ]]; then
  echo "[pytorch-ref] expected_sha256=${EXPECTED_SHA256:0:12}..."
fi

if [[ "$MODE" == "local" ]]; then
  mkdir -p "$OUTPUT_DIR"
  "$PYTHON_BIN" "$PYTHON_HELPER_SOURCE" "${run_helper_args[@]}"
  exit $?
fi

remote_runner="$(mktemp)"
cleanup() {
  rm -f "$remote_runner"
}
trap cleanup EXIT

{
  cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
  declare -p PYTHON_BIN JSCC_ROOT GENERATOR_CKPT ORIGIN_CKPT INPUT_DIR OUTPUT_DIR SNR NOISE_MODE SEED MAX_IMAGES DEVICE TORCH_NUM_THREADS TORCH_NUM_INTEROP_THREADS LOCAL_DISABLE_MKLDNN MANIFEST_NAME EXPECTED_SHA256 LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE VARIANT
  cat <<'SH'
HELPER_PATH="$(mktemp "${TMPDIR:-/tmp}/pytorch_reference_local_XXXXXX.py")"
cleanup_remote() {
  rm -f "$HELPER_PATH"
}
trap cleanup_remote EXIT
cat >"$HELPER_PATH" <<'PY'
SH
  cat "$PYTHON_HELPER_SOURCE"
  cat <<'SH'
PY
mkdir -p "$OUTPUT_DIR"
cmd=("$PYTHON_BIN" "$HELPER_PATH")
cmd+=(
  --jscc-root "$JSCC_ROOT"
  --generator-ckpt "$GENERATOR_CKPT"
  --origin-ckpt "$ORIGIN_CKPT"
  --input-dir "$INPUT_DIR"
  --output-dir "$OUTPUT_DIR"
  --snr "$SNR"
  --noise-mode "$NOISE_MODE"
  --seed "$SEED"
  --max-images "$MAX_IMAGES"
  --device "$DEVICE"
  --torch-num-threads "$TORCH_NUM_THREADS"
  --torch-num-interop-threads "$TORCH_NUM_INTEROP_THREADS"
  --manifest-name "$MANIFEST_NAME"
  --variant "$VARIANT"
)
if [[ -n "$EXPECTED_SHA256" ]]; then
  cmd+=(--expected-sha256 "$EXPECTED_SHA256")
fi
if [[ "$LOCAL_DISABLE_MKLDNN" == "1" ]]; then
  cmd+=(--local-disable-mkldnn)
fi
if [[ "$LOCAL_EXPERIMENTAL_SUBPROCESS_PER_IMAGE" == "1" ]]; then
  cmd+=(--local-experimental-subprocess-per-image)
fi
printf '[pytorch-ref-remote] running: %q' "${cmd[@]}"
printf '\n'
"${cmd[@]}"
SH
} >"$remote_runner"
chmod 700 "$remote_runner"

bash "$SSH_HELPER_SOURCE" \
  --host "$REMOTE_HOST" \
  --user "$REMOTE_USER" \
  --pass "$REMOTE_PASS" \
  --port "${REMOTE_SSH_PORT:-22}" \
  -- \
  bash -s \
  <"$remote_runner"
