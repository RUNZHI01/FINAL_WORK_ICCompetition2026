#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_remote_legacy_tvm_compat.sh --variant <baseline|current> [--script <path>] [--max-inputs <n>]

Notes:
  - Runs the legacy remote JSCC realcmd entry (default: tvm_002.py)
    with a small TVM API compatibility shim for TVM 0.24dev-style runtimes.
  - The main interpreter must be the remote tvm310-style TVM Python.
  - Optional torch dependencies can still be injected through
    REMOTE_TORCH_PYTHONPATH without switching the main interpreter.
  - Emits the original legacy log lines so run_inference_benchmark.sh can
    parse `批量推理时间（1 个样本）: ... 秒` output directly.

Required env:
  REMOTE_MODE=ssh|local
  REMOTE_TVM_PYTHON (or REMOTE_TVM310_PYTHON)
  REMOTE_JSCC_DIR
  REMOTE_INPUT_DIR
  REMOTE_OUTPUT_BASE
  REMOTE_SNR_BASELINE / REMOTE_SNR_CURRENT
  REMOTE_BATCH_BASELINE / REMOTE_BATCH_CURRENT

Optional env:
  REMOTE_TORCH_PYTHONPATH
  REMOTE_LEGACY_EXTRA_PYTHONPATH
  REMOTE_LEGACY_TVM_SCRIPT=tvm_002.py
  REMOTE_BASELINE_ARTIFACT
  REMOTE_CURRENT_ARTIFACT
  INFERENCE_LEGACY_OUTPUT_PREFIX=inference_benchmark
EOF
}

VARIANT=""
LEGACY_SCRIPT=""
MAX_INPUTS="0"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    --script)
      LEGACY_SCRIPT="${2:-}"
      shift 2
      ;;
    --max-inputs)
      MAX_INPUTS="${2:-}"
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

demo_mode_flag="$(printf '%s' "${OPENAMP_DEMO_MODE:-}" | tr '[:upper:]' '[:lower:]')"
if [[ "$MAX_INPUTS" == "0" && ( "$demo_mode_flag" == "1" || "$demo_mode_flag" == "true" || "$demo_mode_flag" == "yes" || "$demo_mode_flag" == "on" ) ]]; then
  MAX_INPUTS="${OPENAMP_DEMO_MAX_INPUTS:-300}"
fi

if [[ "$VARIANT" != "baseline" && "$VARIANT" != "current" ]]; then
  echo "ERROR: --variant must be baseline or current." >&2
  exit 1
fi

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
}

REMOTE_MODE_RAW="${REMOTE_MODE:-ssh}"
REMOTE_MODE="$(printf '%s' "$REMOTE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$REMOTE_MODE" != "ssh" && "$REMOTE_MODE" != "local" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh or local (got: $REMOTE_MODE_RAW)" >&2
  exit 1
fi

LEGACY_TVM_PYTHON="${REMOTE_TVM310_PYTHON:-${REMOTE_TVM_PYTHON:-}}"
if [[ -z "$LEGACY_TVM_PYTHON" ]]; then
  echo "ERROR: Missing REMOTE_TVM_PYTHON (or REMOTE_TVM310_PYTHON)." >&2
  exit 1
fi
if [[ "$LEGACY_TVM_PYTHON" == *"/myenv/"* ]]; then
  echo "ERROR: Legacy compat path must use the tvm310-style interpreter as main python, not myenv: $LEGACY_TVM_PYTHON" >&2
  exit 1
fi

for req in REMOTE_JSCC_DIR REMOTE_INPUT_DIR REMOTE_OUTPUT_BASE; do
  require_var "$req"
done

if [[ "$REMOTE_MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

if [[ "$VARIANT" == "baseline" ]]; then
  require_var REMOTE_SNR_BASELINE
  require_var REMOTE_BATCH_BASELINE
  LEGACY_SNR="$REMOTE_SNR_BASELINE"
  LEGACY_BATCH="$REMOTE_BATCH_BASELINE"
  LEGACY_ARTIFACT="${REMOTE_BASELINE_ARTIFACT:-}"
else
  require_var REMOTE_SNR_CURRENT
  require_var REMOTE_BATCH_CURRENT
  LEGACY_SNR="$REMOTE_SNR_CURRENT"
  LEGACY_BATCH="$REMOTE_BATCH_CURRENT"
  LEGACY_ARTIFACT="${REMOTE_CURRENT_ARTIFACT:-}"
fi

if ! [[ "$LEGACY_BATCH" =~ ^[0-9]+$ ]]; then
  echo "ERROR: batch_size must be a non-negative integer (got: $LEGACY_BATCH)." >&2
  exit 1
fi
if ! [[ "$MAX_INPUTS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-inputs must be a non-negative integer (got: $MAX_INPUTS)." >&2
  exit 1
fi

LEGACY_SCRIPT="${LEGACY_SCRIPT:-${REMOTE_LEGACY_TVM_SCRIPT:-tvm_002.py}}"
OUTPUT_PREFIX="${INFERENCE_LEGACY_OUTPUT_PREFIX:-inference_benchmark}"
LEGACY_OUTPUT_DIR="$REMOTE_OUTPUT_BASE/${OUTPUT_PREFIX}_${VARIANT}"
LEGACY_EXTRA_PYTHONPATH="${REMOTE_LEGACY_EXTRA_PYTHONPATH:-${REMOTE_TORCH_PYTHONPATH:-}}"

run_legacy_compat() {
  local runner_script
  local rc=0
  runner_script="$(mktemp)"
  {
    cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
    declare -p REMOTE_JSCC_DIR LEGACY_TVM_PYTHON LEGACY_SCRIPT REMOTE_INPUT_DIR LEGACY_OUTPUT_DIR LEGACY_SNR LEGACY_BATCH LEGACY_EXTRA_PYTHONPATH VARIANT LEGACY_ARTIFACT MAX_INPUTS
    cat <<'SH'

remote_jscc_dir="$REMOTE_JSCC_DIR"
remote_python="$LEGACY_TVM_PYTHON"
legacy_script="$LEGACY_SCRIPT"
input_dir="$REMOTE_INPUT_DIR"
output_dir="$LEGACY_OUTPUT_DIR"
snr="$LEGACY_SNR"
batch_size="$LEGACY_BATCH"
extra_pythonpath="$LEGACY_EXTRA_PYTHONPATH"
variant="$VARIANT"
legacy_artifact="$LEGACY_ARTIFACT"
max_inputs="$MAX_INPUTS"

cd "$remote_jscc_dir"
mkdir -p "$output_dir"

if [[ -n "$extra_pythonpath" ]]; then
  export PYTHONPATH="$extra_pythonpath"
fi
export PYTHONNOUSERSITE=1

run_remote_python() {
  local stdin_payload cmd arg rc=0
  stdin_payload="$(mktemp)"
  cat >"$stdin_payload"
  cmd="$remote_python"
  for arg in "$@"; do
    cmd+=" $(printf '%q' "$arg")"
  done
  set +e
  bash -c "$cmd" <"$stdin_payload"
  rc=$?
  set -e
  rm -f "$stdin_payload"
  return "$rc"
}

artifact_dir="$remote_jscc_dir/tvm_tune_logs"
artifact_target="$artifact_dir/optimized_model.so"
artifact_backup="$artifact_dir/optimized_model.so.__legacy_compat_backup__"
restore_original=0
selected_input_dir="$input_dir"
staged_input_dir=""

if [[ "$max_inputs" -gt 0 && -d "$input_dir" ]]; then
  mapfile -t supported_inputs < <(find "$input_dir" -maxdepth 1 -type f \( -name '*.pt' -o -name '*.npz' -o -name '*.npy' \) | LC_ALL=C sort)
  if [[ "${#supported_inputs[@]}" -gt "$max_inputs" ]]; then
    staged_input_dir="$(mktemp -d)"
    for source_path in "${supported_inputs[@]:0:max_inputs}"; do
      ln -sf "$source_path" "$staged_input_dir/$(basename "$source_path")"
    done
    selected_input_dir="$staged_input_dir"
  fi
fi

if [[ -n "$legacy_artifact" ]]; then
  if [[ ! -f "$legacy_artifact" ]]; then
    echo "ERROR: requested artifact for variant=$variant does not exist: $legacy_artifact" >&2
    exit 1
  fi
  mkdir -p "$artifact_dir"
  if [[ "$legacy_artifact" != "$artifact_target" ]]; then
    if [[ -f "$artifact_target" ]]; then
      cp -f "$artifact_target" "$artifact_backup"
      restore_original=1
    fi
    cp -f "$legacy_artifact" "$artifact_target"
  fi
fi

cleanup() {
  if [[ "$restore_original" == "1" && -f "$artifact_backup" ]]; then
    cp -f "$artifact_backup" "$artifact_target"
    rm -f "$artifact_backup"
  fi
  if [[ -n "$staged_input_dir" && -d "$staged_input_dir" ]]; then
    rm -rf "$staged_input_dir"
  fi
}
trap cleanup EXIT

echo "[legacy-compat] variant=$variant script=$legacy_script output_dir=$output_dir snr=$snr batch_size=$batch_size max_inputs=$max_inputs python=$remote_python artifact=${legacy_artifact:-$artifact_target}"

run_remote_python - "$legacy_artifact" <<'PY'
import sys
import traceback

artifact_path = sys.argv[1] if len(sys.argv) > 1 else ""

try:
    import tvm
    from tvm import relax
    runtime = getattr(tvm, "runtime", None)
    runtime_ndarray = getattr(runtime, "ndarray", None)
    if runtime_ndarray is not None and not hasattr(tvm, "nd"):
        tvm.nd = runtime_ndarray
    if runtime is not None and not hasattr(runtime, "tensor") and runtime_ndarray is not None:
        runtime.tensor = lambda arr, dev: runtime_ndarray.array(arr, dev)
    if artifact_path:
        lib = tvm.runtime.load_module(artifact_path)
        type_key = getattr(lib, "type_key", "NA")
        dev = tvm.cpu(0)
        try:
            relax.VirtualMachine(lib, dev)
        except AttributeError as err:
            if "vm_load_executable" not in str(err):
                raise
            print(
                f"[legacy-compat] probe_non_vm_executable artifact={artifact_path} "
                f"type_key={type_key} reason=missing_vm_load_executable"
            )
        else:
            print(f"[legacy-compat] probe_ok artifact={artifact_path} type_key={type_key}")
except Exception:
    print(f"[legacy-compat] probe_failed artifact={artifact_path}", file=sys.stderr)
    traceback.print_exc()
    raise
PY

legacy_log="$(mktemp)"
run_started_at="$(date +%s)"
set +e
run_remote_python - "$legacy_script" --input_dir "$selected_input_dir" --output_dir "$output_dir" --snr "$snr" --batch_size "$batch_size" <<'PY' 2>&1 | tee "$legacy_log"
import runpy
import sys

script_name = sys.argv[1]
script_args = sys.argv[2:]

try:
    import tvm
    runtime = getattr(tvm, "runtime", None)
    runtime_ndarray = getattr(runtime, "ndarray", None)
    if runtime_ndarray is not None and not hasattr(tvm, "nd"):
        tvm.nd = runtime_ndarray
    if runtime is not None and not hasattr(runtime, "tensor") and runtime_ndarray is not None:
        runtime.tensor = lambda arr, dev: runtime_ndarray.array(arr, dev)
except Exception as exc:
    print(f"[compat] warning: failed to expose tvm.nd: {exc}", file=sys.stderr)

sys.argv = [script_name] + script_args
runpy.run_path(script_name, run_name="__main__")
PY
legacy_rc=${PIPESTATUS[0]}
set -e
if [[ "$legacy_rc" -ne 0 ]]; then
  rm -f "$legacy_log"
  exit "$legacy_rc"
fi

summary_expected_sha=""
if [[ "$variant" == "baseline" ]]; then
  summary_expected_sha="${INFERENCE_BASELINE_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
else
  summary_expected_sha="${INFERENCE_CURRENT_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
fi

summary_artifact_path="${legacy_artifact:-$artifact_target}"
run_remote_python - "$legacy_log" "$summary_artifact_path" "$input_dir" "$selected_input_dir" "$output_dir" "$variant" "$snr" "$batch_size" "$summary_expected_sha" "$max_inputs" "$run_started_at" <<'PY'
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def argv_or(index: int, default: str = "") -> str:
    if len(sys.argv) > index:
        return sys.argv[index]
    return default


if len(sys.argv) < 9:
    raise SystemExit(f"ERROR: legacy summary expected at least 8 args, got {len(sys.argv) - 1}")

summary_warnings = []
if len(sys.argv) <= 10:
    summary_warnings.append("max_inputs_missing")
if len(sys.argv) <= 11:
    summary_warnings.append("run_started_at_missing")

log_path = Path(argv_or(1))
artifact_path = Path(argv_or(2))
original_input_dir = Path(argv_or(3))
selected_input_dir = Path(argv_or(4))
output_dir = Path(argv_or(5))
variant = argv_or(6)
snr = float(argv_or(7, "0") or 0.0)
batch_size = int(argv_or(8, "0") or 0)
expected_sha256 = argv_or(9).strip().lower()
max_inputs = int(argv_or(10, "0") or 0)
run_started_at = int(argv_or(11, "0") or 0)

patterns = (
    re.compile(r"批量推理时间.*?:\s*([0-9]+(?:\.[0-9]+)?)\s*秒"),
    re.compile(r"batch\s+infer(?:ence)?\s+time.*?:\s*([0-9]+(?:\.[0-9]+)?)\s*s(?:ec(?:onds?)?)?", re.I),
)

run_samples_ms = []
for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
    line = raw_line.strip()
    for pattern in patterns:
        match = pattern.search(line)
        if match:
            run_samples_ms.append(float(match.group(1)) * 1000.0)
            break

artifact_sha256 = file_sha256(artifact_path) if artifact_path.is_file() else ""
supported_suffixes = {".pt", ".npz", ".npy"}


def list_supported_inputs(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return [
        candidate
        for candidate in sorted(path.iterdir())
        if candidate.is_file() and candidate.suffix.lower() in supported_suffixes
    ]


def list_output_files(path: Path, *, run_started_at: int, selected_inputs: list[Path]) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    selected_stems = {candidate.stem for candidate in selected_inputs}
    files: list[Path] = []
    for candidate in sorted(path.iterdir()):
        if not candidate.is_file():
            continue
        stem = candidate.stem
        stem_matches_selected = stem in selected_stems or any(
            stem.startswith(f"{selected_stem}_") for selected_stem in selected_stems
        )
        try:
            modified_during_run = int(candidate.stat().st_mtime) >= run_started_at
        except OSError:
            modified_during_run = False
        if stem_matches_selected or modified_during_run:
            files.append(candidate)
    return files


available_inputs = list_supported_inputs(original_input_dir)
selected_inputs = list_supported_inputs(selected_input_dir)
available_input_count = len(available_inputs)
selected_input_count = len(selected_inputs)
reconstructions_dir = output_dir / "reconstructions"
effective_output_dir = reconstructions_dir if reconstructions_dir.is_dir() else output_dir
output_files = list_output_files(
    effective_output_dir,
    run_started_at=run_started_at,
    selected_inputs=selected_inputs,
)

summary = {
    "variant": variant,
    "artifact_path": str(artifact_path),
    "artifact_sha256": artifact_sha256,
    "artifact_sha256_expected": expected_sha256 or None,
    "artifact_sha256_match": None
    if not expected_sha256 or not artifact_sha256
    else artifact_sha256 == expected_sha256,
    "input_dir": str(original_input_dir),
    "output_dir": str(effective_output_dir),
    "output_count": len(output_files),
    "processed_count": len(run_samples_ms),
    "input_count": selected_input_count,
    "available_input_count": available_input_count,
    "load_ms": 0.0,
    "vm_init_ms": 0.0,
    "run_count": len(run_samples_ms),
    "run_samples_ms": [round(value, 3) for value in run_samples_ms],
    "run_median_ms": round(statistics.median(run_samples_ms), 3) if run_samples_ms else None,
    "run_mean_ms": round(sum(run_samples_ms) / len(run_samples_ms), 3) if run_samples_ms else None,
    "run_min_ms": round(min(run_samples_ms), 3) if run_samples_ms else None,
    "run_max_ms": round(max(run_samples_ms), 3) if run_samples_ms else None,
    "run_variance_ms2": round(statistics.pvariance(run_samples_ms), 6) if len(run_samples_ms) > 1 else 0.0,
    "output_shape": None,
    "output_dtype": None,
    "snr": snr,
    "batch_size": batch_size,
    "save_format": output_files[0].suffix.lstrip(".") if output_files else "unknown",
    "seed": None,
    "max_inputs": max_inputs,
    "parser": "legacy_latency_lines",
}
if summary_warnings:
    summary["warnings"] = summary_warnings
print(json.dumps(summary, ensure_ascii=False))
PY
rm -f "$legacy_log"
SH
  } >"$runner_script"
  chmod 700 "$runner_script"

  if [[ "$REMOTE_MODE" == "ssh" ]]; then
    set +e
    bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$REMOTE_HOST" \
      --user "$REMOTE_USER" \
      --pass "$REMOTE_PASS" \
      --port "${REMOTE_SSH_PORT:-22}" \
      -- \
      bash -s \
      <"$runner_script"
    rc=$?
    set -e
    rm -f "$runner_script"
    return "$rc"
  fi

  set +e
  bash "$runner_script"
  rc=$?
  set -e
  rm -f "$runner_script"
  return "$rc"
}

run_legacy_compat
