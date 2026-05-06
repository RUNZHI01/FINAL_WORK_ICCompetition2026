#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:?usage: run-isolated-cli-smoke.sh REPO_ROOT RUN_ROOT}"
RUN_ROOT="${2:?usage: run-isolated-cli-smoke.sh REPO_ROOT RUN_ROOT}"

REPO_ROOT="$(cd "${REPO_ROOT}" && pwd)"
mkdir -p "${RUN_ROOT}/logs" "${RUN_ROOT}/work/places" "${RUN_ROOT}/work/mnn" \
    "${RUN_ROOT}/work/npz" "${RUN_ROOT}/work/outputs/tvm" \
    "${RUN_ROOT}/work/outputs/mnn" "${RUN_ROOT}/work/outputs/pytorch"

log() {
    printf '[cli-smoke] %s\n' "$*" | tee -a "${RUN_ROOT}/logs/setup.log"
}

runtime_dir_or_unpack() {
    local name="$1"
    local dir="${RUN_ROOT}/runtime/${name}"
    local archive="${REPO_ROOT}/board_deps/runtime/${name}.tar.gz"
    local part_prefix="${archive}.part-"
    if [ -d "${dir}" ]; then
        printf '%s\n' "${dir}"
        return
    fi
    if [ -f "${archive}" ]; then
        mkdir -p "${RUN_ROOT}/runtime"
        tar -xzf "${archive}" -C "${RUN_ROOT}/runtime"
        printf '%s\n' "${dir}"
        return
    fi
    if compgen -G "${part_prefix}*" >/dev/null; then
        mkdir -p "${RUN_ROOT}/runtime"
        cat "${part_prefix}"* | tar -xzf - -C "${RUN_ROOT}/runtime"
        printf '%s\n' "${dir}"
        return
    fi
    printf 'missing runtime: %s or %s\n' "${dir}" "${archive}" >&2
    return 1
}

TVM_PY_PREFIX="$(runtime_dir_or_unpack tvm_py310)"
MNN_PY_PREFIX="$(runtime_dir_or_unpack mnn_py312)"
MNN_PY="${MNN_PY_PREFIX}/bin/python"
MNN_SP="${MNN_PY_PREFIX}/lib/python3.12/site-packages"
MNN_LIB="${MNN_PY_PREFIX}/lib:${MNN_SP}/mnn.libs:${MNN_SP}/numpy.libs:${MNN_SP}/pillow.libs"

log "extracting input archives"
rm -rf "${RUN_ROOT}/work/places" "${RUN_ROOT}/work/mnn" "${RUN_ROOT}/work/npz"
mkdir -p "${RUN_ROOT}/work/places" "${RUN_ROOT}/work/mnn" "${RUN_ROOT}/work/npz"
tar -xzf "${REPO_ROOT}/board_deps/inputs/places365-latents.tar.gz" -C "${RUN_ROOT}/work/places"
tar -xzf "${REPO_ROOT}/board_deps/inputs/mnn-encoder-outputs.tar.gz" -C "${RUN_ROOT}/work/mnn"

log "checking MNN/PyTorch runtime imports"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" - <<'PY'
import torch
import numpy
import PIL
import MNN
print("MNN_PY_IMPORT_OK", torch.__version__, numpy.__version__)
PY

log "converting three PyTorch latent files to NPZ for TVM"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" - "${RUN_ROOT}/work/places" "${RUN_ROOT}/work/npz" <<'PY'
from pathlib import Path
import sys
import numpy as np
import torch

input_root = Path(sys.argv[1])
output_root = Path(sys.argv[2])
output_root.mkdir(parents=True, exist_ok=True)
files = sorted(input_root.rglob("*.pt"))[:3]
print("pt_inputs", [str(path) for path in files])
if len(files) < 3:
    raise SystemExit("need at least 3 pt inputs")

for path in files:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    data = {}
    if isinstance(payload, dict):
        for key in ("latent", "quant", "scale", "zero_point"):
            if key in payload:
                value = payload[key]
                if hasattr(value, "detach"):
                    value = value.detach().cpu().numpy()
                data[key] = np.asarray(value)
    else:
        if hasattr(payload, "detach"):
            payload = payload.detach().cpu().numpy()
        data["latent"] = np.asarray(payload)
    if not data:
        raise RuntimeError(f"no latent keys in {path}")
    np.savez(output_root / f"{path.stem}.npz", **data)

print("npz_outputs", [str(path) for path in sorted(output_root.glob("*.npz"))])
PY

TVM_RT="${REPO_ROOT}/board_deps/tvm/runtime"
TVM_EXTRACT_ROOT="${RUN_ROOT}/work/tvm_runtime"
TVM_BUILD="${TVM_EXTRACT_ROOT}/home/user/tvm_samegen_safe_20260309/build"
TVM_PY_SRC="${TVM_EXTRACT_ROOT}/home/user/tvm_samegen_20260307/python"
TVM_PY="${TVM_PY_PREFIX}/bin/python"
TVM_SP="${TVM_PY_PREFIX}/lib/python3.10/site-packages"

log "extracting TVM runtime"
rm -rf "${TVM_EXTRACT_ROOT}"
mkdir -p "${TVM_EXTRACT_ROOT}"
tar -xzf "${TVM_RT}/tvm310-safe-runtime-aarch64.tar.gz" -C "${TVM_EXTRACT_ROOT}"

export TVM_FFI_DISABLE_TORCH_C_DLPACK=1
export TVM_LIBRARY_PATH="${TVM_BUILD}"
export LD_LIBRARY_PATH="${TVM_PY_PREFIX}/lib:${TVM_SP}/tvm_ffi/lib:${TVM_BUILD}:${TVM_BUILD}/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${TVM_PY_SRC}:${TVM_SP}"

log "checking TVM runtime import"
"${TVM_PY}" - <<'PY'
import tvm
from tvm import relax
print("TVM_IMPORT_OK", tvm.__version__, relax.VirtualMachine)
PY

log "running TVM CLI inference"
TVM_INPUT_FILE="$(find "${RUN_ROOT}/work/npz" -type f -name '*.npz' -print -quit)"
if [ -z "${TVM_INPUT_FILE}" ]; then
    printf 'missing TVM NPZ input under %s\n' "${RUN_ROOT}/work/npz" >&2
    exit 1
fi
"${TVM_PY}" "${REPO_ROOT}/scripts/tvm_inference_helper.py" \
    --artifact-path "${REPO_ROOT}/board_deps/tvm/current/optimized_model.so" \
    --input "${TVM_INPUT_FILE}" \
    --output "${RUN_ROOT}/work/outputs/tvm/result.npy" \
    --snr 10 \
    --seed 1 | tee "${RUN_ROOT}/logs/tvm.json"

log "running MNN CLI inference"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" "${REPO_ROOT}/Semantic-Communication/session_bootstrap/scripts/mnn_real_reconstruction.py" \
    --model-path "${REPO_ROOT}/board_deps/mnn/origin/model1.mnn" \
    --input-dir "${RUN_ROOT}/work/mnn/encoder_outputs" \
    --output-dir "${RUN_ROOT}/work/outputs/mnn" \
    --snr 10 \
    --variant mnn-isolated \
    --max-inputs 3 \
    --interpreter-count 1 \
    --session-threads 1 \
    --seed 1 | tee "${RUN_ROOT}/logs/mnn.json"

PYTORCH_CKPT="${REPO_ROOT}/board_deps/pytorch/compressed_gan.pt"
if [ ! -f "${PYTORCH_CKPT}" ]; then
    printf 'missing PyTorch checkpoint: %s\n' "${PYTORCH_CKPT}" >&2
    exit 1
fi
PYTORCH_INPUT_FILE="$(find "${RUN_ROOT}/work/places" -type f -name '*.pt' -print -quit)"
PYTORCH_INPUT_DIR=""
if [ -n "${PYTORCH_INPUT_FILE}" ]; then
    PYTORCH_INPUT_DIR="$(dirname "${PYTORCH_INPUT_FILE}")"
fi
if [ -z "${PYTORCH_INPUT_DIR}" ]; then
    printf 'missing PyTorch latent inputs under %s\n' "${RUN_ROOT}/work/places" >&2
    exit 1
fi

log "running PyTorch CLI inference"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" "${REPO_ROOT}/Semantic-Communication/session_bootstrap/scripts/pytorch_reference_reconstruction.py" \
    --jscc-root "${REPO_ROOT}/host_pic_to_latent/jscc" \
    --generator-ckpt "${PYTORCH_CKPT}" \
    --input-dir "${PYTORCH_INPUT_DIR}" \
    --output-dir "${RUN_ROOT}/work/outputs/pytorch" \
    --snr 10 \
    --device cpu \
    --max-images 3 \
    --seed 1 | tee "${RUN_ROOT}/logs/pytorch.json"

log "writing output index"
find "${RUN_ROOT}/logs" "${RUN_ROOT}/work/outputs" -maxdepth 3 -type f \
    -printf '%p\t%s bytes\n' | sort | tee "${RUN_ROOT}/logs/files.txt"
printf '%s\n' "${RUN_ROOT}" > "${RUN_ROOT}/logs/run_root.txt"
echo "cli-smoke-ok"
