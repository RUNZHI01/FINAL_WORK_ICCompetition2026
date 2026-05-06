#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:?usage: run-isolated-cli-smoke.sh REPO_ROOT RUN_ROOT}"
RUN_ROOT="${2:?usage: run-isolated-cli-smoke.sh REPO_ROOT RUN_ROOT}"
MAX_INPUTS="${BOARD_CLI_MAX_INPUTS:-300}"

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

log "converting ${MAX_INPUTS} PyTorch latent files to NPZ for TVM"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" - "${RUN_ROOT}/work/places" "${RUN_ROOT}/work/npz" "${MAX_INPUTS}" <<'PY'
from pathlib import Path
import sys
import numpy as np
import torch

input_root = Path(sys.argv[1])
output_root = Path(sys.argv[2])
max_inputs = int(sys.argv[3])
output_root.mkdir(parents=True, exist_ok=True)
files = sorted(input_root.rglob("*.pt"))
if max_inputs > 0:
    files = files[:max_inputs]
print("pt_input_count", len(files))
print("pt_inputs_preview", [str(path) for path in files[:5]])
if not files:
    raise SystemExit("need at least one pt input")

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

print("npz_output_count", len(list(output_root.glob("*.npz"))))
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

log "running TVM CLI inference for ${MAX_INPUTS} inputs"
TVM_INPUT_COUNT="$(find "${RUN_ROOT}/work/npz" -type f -name '*.npz' | wc -l)"
if [ "${TVM_INPUT_COUNT}" -le 0 ]; then
    printf 'missing TVM NPZ input under %s\n' "${RUN_ROOT}/work/npz" >&2
    exit 1
fi
mkdir -p "${RUN_ROOT}/work/outputs/tvm/results"
: > "${RUN_ROOT}/logs/tvm.jsonl"
while IFS= read -r TVM_INPUT_FILE; do
    TVM_STEM="$(basename "${TVM_INPUT_FILE}" .npz)"
    "${TVM_PY}" "${REPO_ROOT}/scripts/tvm_inference_helper.py" \
        --artifact-path "${REPO_ROOT}/board_deps/tvm/current/optimized_model.so" \
        --input "${TVM_INPUT_FILE}" \
        --output "${RUN_ROOT}/work/outputs/tvm/results/${TVM_STEM}.npy" \
        --snr 10 \
        --seed 1 | tee -a "${RUN_ROOT}/logs/tvm.jsonl"
done < <(find "${RUN_ROOT}/work/npz" -type f -name '*.npz' | sort)
"${MNN_PY}" - "${RUN_ROOT}/logs/tvm.jsonl" "${RUN_ROOT}/work/outputs/tvm/summary.json" <<'PY'
import json
import statistics
import sys
from pathlib import Path

records = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
ok = [item for item in records if item.get("status") == "ok"]
run_ms = [float(item["inference_ms"]) for item in ok]
load_ms = [float(item["load_ms"]) for item in ok if "load_ms" in item]
summary = {
    "status": "ok" if len(ok) == len(records) and records else "error",
    "runtime": "tvm",
    "processed_count": len(ok),
    "record_count": len(records),
    "run_mean_ms": statistics.mean(run_ms) if run_ms else None,
    "run_median_ms": statistics.median(run_ms) if run_ms else None,
    "run_min_ms": min(run_ms) if run_ms else None,
    "run_max_ms": max(run_ms) if run_ms else None,
    "load_mean_ms": statistics.mean(load_ms) if load_ms else None,
    "output_dir": str(Path(sys.argv[2]).parent / "results"),
}
Path(sys.argv[2]).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
if summary["status"] != "ok":
    raise SystemExit("TVM batch did not finish cleanly")
PY

log "running MNN CLI inference for ${MAX_INPUTS} inputs"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" "${REPO_ROOT}/Semantic-Communication/session_bootstrap/scripts/mnn_real_reconstruction.py" \
    --model-path "${REPO_ROOT}/board_deps/mnn/origin/model1.mnn" \
    --input-dir "${RUN_ROOT}/work/mnn/encoder_outputs" \
    --output-dir "${RUN_ROOT}/work/outputs/mnn" \
    --snr 10 \
    --variant mnn-isolated \
    --max-inputs "${MAX_INPUTS}" \
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

log "running PyTorch CLI inference for ${MAX_INPUTS} inputs"
LD_LIBRARY_PATH="${MNN_LIB}:${LD_LIBRARY_PATH:-}" \
PYTHONPATH="${MNN_SP}" \
"${MNN_PY}" "${REPO_ROOT}/Semantic-Communication/session_bootstrap/scripts/pytorch_reference_reconstruction.py" \
    --jscc-root "${REPO_ROOT}/host_pic_to_latent/jscc" \
    --generator-ckpt "${PYTORCH_CKPT}" \
    --input-dir "${PYTORCH_INPUT_DIR}" \
    --output-dir "${RUN_ROOT}/work/outputs/pytorch" \
    --snr 10 \
    --device cpu \
    --max-images "${MAX_INPUTS}" \
    --seed 1 | tee "${RUN_ROOT}/logs/pytorch.json"

log "writing output index"
find "${RUN_ROOT}/logs" "${RUN_ROOT}/work/outputs" -maxdepth 3 -type f \
    -printf '%p\t%s bytes\n' | sort | tee "${RUN_ROOT}/logs/files.txt"
printf '%s\n' "${RUN_ROOT}" > "${RUN_ROOT}/logs/run_root.txt"
echo "cli-smoke-ok"
