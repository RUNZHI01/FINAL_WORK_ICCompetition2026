#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

ONE_SHOT_SCRIPT="$SCRIPT_DIR/run_phytium_current_safe_one_shot.sh"
DEFAULT_REBUILD_ENV="$SESSION_DIR/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
DEFAULT_INFERENCE_ENV="$SESSION_DIR/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
STABLE_TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
EXPERIMENTAL_TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}'
DEFAULT_REPEAT=10
DEFAULT_WARMUP_RUNS=2
DEFAULT_ENTRY=main

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_phytium_current_safe_target_compare.sh [options]

Purpose:
  Run the two most important Phytium Pi baseline-seeded current-safe targets back-to-back:
    1) recommended stable target
    2) more aggressive experimental target

Targets:
  stable       : $STABLE_TARGET
  experimental : $EXPERIMENTAL_TARGET

Notes:
  - This wrapper is explicit about the baseline-seeded current + safe runtime path only.
  - It reuses run_phytium_current_safe_one_shot.sh for both runs.
  - It writes one concise compare report plus the two per-run one-shot summaries.
  - If the two targets produce the same optimized_model.so hash, the compare is marked invalid and exits nonzero.

Options:
  --rebuild-env <path>        Override rebuild env file.
  --inference-env <path>      Override safe-runtime inference env file.
  --output-root <path>        Override local root dir for both rebuilt artifacts.
  --remote-archive-dir <dir>  Override remote current archive dir.
  --report-id <id>            Override compare report/log prefix.
  --repeat <n>                Override inference repeat count for both runs.
  --warmup-runs <n>           Override inference warmup count for both runs.
  --entry <name>              Override Relax VM entry name (default: ${DEFAULT_ENTRY}).
  --help                      Show this message.
EOF
}

REBUILD_ENV="$DEFAULT_REBUILD_ENV"
INFERENCE_ENV="$DEFAULT_INFERENCE_ENV"
OUTPUT_ROOT_OVERRIDE=""
REMOTE_ARCHIVE_DIR_OVERRIDE=""
REPORT_ID_OVERRIDE=""
REPEAT_OVERRIDE=""
WARMUP_OVERRIDE=""
ENTRY_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild-env)
      REBUILD_ENV="${2:-}"
      shift 2
      ;;
    --inference-env)
      INFERENCE_ENV="${2:-}"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --remote-archive-dir)
      REMOTE_ARCHIVE_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --report-id)
      REPORT_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --repeat)
      REPEAT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --warmup-runs)
      WARMUP_OVERRIDE="${2:-}"
      shift 2
      ;;
    --entry)
      ENTRY_OVERRIDE="${2:-}"
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

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

resolve_path() {
  local maybe_relative="$1"
  if [[ -z "$maybe_relative" ]]; then
    printf '%s\n' ""
  elif [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

normalize_target_json() {
  python3 - "$1" <<'PY'
import json
import sys

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception as err:
    print(f"ERROR: invalid target JSON: {err}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(payload, dict):
    print("ERROR: target must be a JSON object.", file=sys.stderr)
    raise SystemExit(1)

print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
PY
}

append_optional_arg() {
  local option="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    RUN_CMD+=("$option" "$value")
  fi
}

require_command bash
require_command python3
require_file "$ONE_SHOT_SCRIPT" "current-safe one-shot script"
require_file "$REBUILD_ENV" "rebuild env"
require_file "$INFERENCE_ENV" "inference env"

STABLE_TARGET_NORMALIZED="$(normalize_target_json "$STABLE_TARGET")"
EXPERIMENTAL_TARGET_NORMALIZED="$(normalize_target_json "$EXPERIMENTAL_TARGET")"
if [[ "$STABLE_TARGET_NORMALIZED" == "$EXPERIMENTAL_TARGET_NORMALIZED" ]]; then
  echo "ERROR: compare targets are identical after normalization; refusing invalid compare." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$REBUILD_ENV"
COMPARE_LOG_DIR="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
COMPARE_REPORT_DIR="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

mkdir -p "$COMPARE_LOG_DIR" "$COMPARE_REPORT_DIR" "$SESSION_DIR/tmp"

STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_ID="${REPORT_ID_OVERRIDE:-phytium_current_safe_target_compare_${STAMP}}"
OUTPUT_ROOT="$(resolve_path "${OUTPUT_ROOT_OVERRIDE:-./session_bootstrap/tmp/${REPORT_ID}}")"
COMPARE_LOG="$COMPARE_LOG_DIR/${REPORT_ID}.log"
COMPARE_JSON="$COMPARE_REPORT_DIR/${REPORT_ID}.json"
COMPARE_MD="$COMPARE_REPORT_DIR/${REPORT_ID}.md"

STABLE_RUN_ID="${REPORT_ID}_stable"
EXPERIMENTAL_RUN_ID="${REPORT_ID}_experimental"
STABLE_OUTPUT_DIR="$OUTPUT_ROOT/stable"
EXPERIMENTAL_OUTPUT_DIR="$OUTPUT_ROOT/experimental"
STABLE_SUMMARY_JSON="$COMPARE_REPORT_DIR/${STABLE_RUN_ID}.json"
EXPERIMENTAL_SUMMARY_JSON="$COMPARE_REPORT_DIR/${EXPERIMENTAL_RUN_ID}.json"
STABLE_SUMMARY_MD="$COMPARE_REPORT_DIR/${STABLE_RUN_ID}.md"
EXPERIMENTAL_SUMMARY_MD="$COMPARE_REPORT_DIR/${EXPERIMENTAL_RUN_ID}.md"

mkdir -p "$OUTPUT_ROOT"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$1" | tee -a "$COMPARE_LOG"
}

run_one_shot() {
  local label="$1"
  local target="$2"
  local output_dir="$3"
  local run_id="$4"

  RUN_CMD=(
    bash "$ONE_SHOT_SCRIPT"
    --rebuild-env "$REBUILD_ENV"
    --inference-env "$INFERENCE_ENV"
    --target "$target"
    --output-dir "$output_dir"
    --report-id "$run_id"
  )
  append_optional_arg --remote-archive-dir "$REMOTE_ARCHIVE_DIR_OVERRIDE"
  append_optional_arg --repeat "$REPEAT_OVERRIDE"
  append_optional_arg --warmup-runs "$WARMUP_OVERRIDE"
  append_optional_arg --entry "$ENTRY_OVERRIDE"

  log "run=${label} start"
  if ! ("${RUN_CMD[@]}") 2>&1 | tee -a "$COMPARE_LOG"; then
    log "run=${label} failed"
    exit 1
  fi
  log "run=${label} success"
}

log "Phytium baseline-seeded current-safe target compare started"
log "mode=baseline-seeded warm-start current rebuild-only target compare + safe runtime"
log "rebuild_env=$REBUILD_ENV"
log "inference_env=$INFERENCE_ENV"
log "output_root=$OUTPUT_ROOT"
log "stable_target=$STABLE_TARGET_NORMALIZED"
log "experimental_target=$EXPERIMENTAL_TARGET_NORMALIZED"

run_one_shot stable "$STABLE_TARGET_NORMALIZED" "$STABLE_OUTPUT_DIR" "$STABLE_RUN_ID"
run_one_shot experimental "$EXPERIMENTAL_TARGET_NORMALIZED" "$EXPERIMENTAL_OUTPUT_DIR" "$EXPERIMENTAL_RUN_ID"

require_file "$STABLE_SUMMARY_JSON" "stable summary json"
require_file "$EXPERIMENTAL_SUMMARY_JSON" "experimental summary json"
require_file "$STABLE_SUMMARY_MD" "stable summary md"
require_file "$EXPERIMENTAL_SUMMARY_MD" "experimental summary md"

set +e
python3 - \
  "$STABLE_SUMMARY_JSON" \
  "$EXPERIMENTAL_SUMMARY_JSON" \
  "$COMPARE_JSON" \
  "$COMPARE_MD" \
  "$STABLE_SUMMARY_MD" \
  "$EXPERIMENTAL_SUMMARY_MD" \
  "$REPORT_ID" \
  "$REBUILD_ENV" \
  "$INFERENCE_ENV" \
  "$COMPARE_LOG" \
  "$OUTPUT_ROOT" <<'PY'
import json
import math
import sys
from datetime import datetime


def load_json(path):
    with open(path, "r", encoding="utf-8") as infile:
        return json.load(infile)


def as_float(value):
    if value in (None, "NA", ""):
        return None
    return float(value)


def metric_block(summary):
    payload = summary.get("safe_runtime_inference", {}).get("payload", {})
    return {
        "target": summary.get("target"),
        "rebuild_elapsed_sec": as_float(summary.get("local_build", {}).get("rebuild_elapsed_sec")),
        "runner": summary.get("local_build", {}).get("runner"),
        "total_trials": summary.get("local_build", {}).get("total_trials"),
        "search_mode": summary.get("local_build", {}).get("search_mode"),
        "load_ms": as_float(payload.get("load_ms")),
        "vm_init_ms": as_float(payload.get("vm_init_ms")),
        "run_median_ms": as_float(payload.get("run_median_ms")),
        "run_mean_ms": as_float(payload.get("run_mean_ms")),
        "run_min_ms": as_float(payload.get("run_min_ms")),
        "run_max_ms": as_float(payload.get("run_max_ms")),
        "run_variance_ms2": as_float(payload.get("run_variance_ms2")),
        "run_samples_ms": payload.get("run_samples_ms"),
        "optimized_model_so": summary.get("local_build", {}).get("optimized_model_so"),
        "optimized_model_sha256": summary.get("local_build", {}).get("optimized_model_sha256"),
        "optimized_model_size_bytes": summary.get("local_build", {}).get("optimized_model_size_bytes"),
        "summary_json": summary_path_map[id(summary)]["json"],
        "summary_md": summary_path_map[id(summary)]["md"],
    }


def delta(left, right):
    if left is None or right is None:
        return None
    return round(left - right, 3)


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:.3f}"


def delta_text(value, better_when_lower):
    if value is None:
        return "NA"
    if math.isclose(value, 0.0, abs_tol=1e-9):
        return "no change"
    direction = "lower" if value < 0 else "higher"
    magnitude = abs(value)
    if better_when_lower:
        speed = "faster" if value < 0 else "slower"
        return f"{magnitude:.3f} ms {speed}"
    return f"{magnitude:.3f} ms^2 {direction}"


(
    stable_json_path,
    experimental_json_path,
    compare_json_path,
    compare_md_path,
    stable_md_path,
    experimental_md_path,
    report_id,
    rebuild_env,
    inference_env,
    compare_log,
    output_root,
) = sys.argv[1:12]

stable = load_json(stable_json_path)
experimental = load_json(experimental_json_path)
summary_path_map = {
    id(stable): {"json": stable_json_path, "md": stable_md_path},
    id(experimental): {"json": experimental_json_path, "md": experimental_md_path},
}

stable_metrics = metric_block(stable)
experimental_metrics = metric_block(experimental)

stable_hash = stable_metrics.get("optimized_model_sha256")
experimental_hash = experimental_metrics.get("optimized_model_sha256")
targets_distinct = stable_metrics.get("target") != experimental_metrics.get("target")
identical_artifact = (
    targets_distinct
    and stable_hash not in (None, "", "NA")
    and stable_hash == experimental_hash
)

if targets_distinct and identical_artifact:
    validity = {
        "status": "invalid",
        "reason": "distinct_targets_same_optimized_model_sha256",
        "message": (
            "Stable and experimental targets differ, but the rebuilt optimized_model.so "
            "hash is identical. Treat this compare as invalid."
        ),
    }
else:
    validity = {
        "status": "valid",
        "reason": None,
        "message": "Distinct targets produced distinct optimized artifacts.",
    }

comparison = {
    "mode": "baseline-seeded warm-start current rebuild-only target compare + safe runtime",
    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "report_id": report_id,
    "rebuild_env": rebuild_env,
    "inference_env": inference_env,
    "validity": validity,
    "stable": stable_metrics,
    "experimental": experimental_metrics,
    "experimental_minus_stable": {
        "load_ms": delta(experimental_metrics["load_ms"], stable_metrics["load_ms"]),
        "vm_init_ms": delta(experimental_metrics["vm_init_ms"], stable_metrics["vm_init_ms"]),
        "run_median_ms": delta(experimental_metrics["run_median_ms"], stable_metrics["run_median_ms"]),
        "run_mean_ms": delta(experimental_metrics["run_mean_ms"], stable_metrics["run_mean_ms"]),
        "run_min_ms": delta(experimental_metrics["run_min_ms"], stable_metrics["run_min_ms"]),
        "run_max_ms": delta(experimental_metrics["run_max_ms"], stable_metrics["run_max_ms"]),
        "run_variance_ms2": delta(experimental_metrics["run_variance_ms2"], stable_metrics["run_variance_ms2"]),
        "rebuild_elapsed_sec": delta(experimental_metrics["rebuild_elapsed_sec"], stable_metrics["rebuild_elapsed_sec"]),
    },
    "artifacts": {
        "output_root": output_root,
        "compare_log": compare_log,
        "compare_md": compare_md_path,
        "compare_json": compare_json_path,
    },
}

with open(compare_json_path, "w", encoding="utf-8") as outfile:
    json.dump(comparison, outfile, indent=2, ensure_ascii=False)

median_delta = comparison["experimental_minus_stable"]["run_median_ms"]
variance_delta = comparison["experimental_minus_stable"]["run_variance_ms2"]
validity_line = comparison["validity"]["message"]
status_text = comparison["validity"]["status"].upper()
default_target_line = "Stable default remains the safer current-safe runtime target."
failure_note = ""
if comparison["validity"]["status"] == "invalid":
    default_target_line = "This compare is invalid; do not use it to rank stable vs experimental targets."
    failure_note = """
## Invalid Compare

- status: INVALID
- reason: distinct targets produced the same optimized_model.so sha256
- action: discard the timing delta and rerun only after a path that yields distinct artifacts
"""

md = f"""# Phytium Pi baseline-seeded current-safe target comparison

- mode: baseline-seeded warm-start current rebuild-only target compare + safe runtime
- generated_at: {comparison['generated_at']}
- report_id: {report_id}
- rebuild_env: {rebuild_env}
- inference_env: {inference_env}
- validity: {status_text}
- validity_note: {validity_line}

## Runs

| profile | target | build sec | load ms | vm init ms | median ms | mean ms | min ms | max ms | variance ms^2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| recommended stable | `{stable_metrics['target']}` | {fmt(stable_metrics['rebuild_elapsed_sec'])} | {fmt(stable_metrics['load_ms'])} | {fmt(stable_metrics['vm_init_ms'])} | {fmt(stable_metrics['run_median_ms'])} | {fmt(stable_metrics['run_mean_ms'])} | {fmt(stable_metrics['run_min_ms'])} | {fmt(stable_metrics['run_max_ms'])} | {fmt(stable_metrics['run_variance_ms2'])} |
| aggressive experimental | `{experimental_metrics['target']}` | {fmt(experimental_metrics['rebuild_elapsed_sec'])} | {fmt(experimental_metrics['load_ms'])} | {fmt(experimental_metrics['vm_init_ms'])} | {fmt(experimental_metrics['run_median_ms'])} | {fmt(experimental_metrics['run_mean_ms'])} | {fmt(experimental_metrics['run_min_ms'])} | {fmt(experimental_metrics['run_max_ms'])} | {fmt(experimental_metrics['run_variance_ms2'])} |

## Build Identity

| profile | runner | total_trials | search_mode | optimized_model_sha256 |
|---|---|---:|---|---|
| recommended stable | `{stable_metrics['runner']}` | {stable_metrics['total_trials']} | `{stable_metrics['search_mode']}` | `{stable_metrics['optimized_model_sha256']}` |
| aggressive experimental | `{experimental_metrics['runner']}` | {experimental_metrics['total_trials']} | `{experimental_metrics['search_mode']}` | `{experimental_metrics['optimized_model_sha256']}` |

{failure_note}

## Quick Readout

- {default_target_line}
- Experimental vs stable median: {delta_text(median_delta, better_when_lower=True)}.
- Experimental vs stable variance: {delta_text(variance_delta, better_when_lower=False)}.
- Compare validity: {status_text} ({validity_line})
- Stable per-run summary: `{stable_md_path}`
- Experimental per-run summary: `{experimental_md_path}`
- Compare log: `{compare_log}`
- Compare json: `{compare_json_path}`
"""

with open(compare_md_path, "w", encoding="utf-8") as outfile:
    outfile.write(md)

if comparison["validity"]["status"] == "invalid":
    raise SystemExit(2)
PY
COMPARE_RC=$?
set -e

if [[ "$COMPARE_RC" -eq 2 ]]; then
  log "compare_validity=invalid"
  log "reason=distinct_targets_same_optimized_model_sha256"
elif [[ "$COMPARE_RC" -ne 0 ]]; then
  exit "$COMPARE_RC"
else
  log "compare_validity=valid"
fi

cat <<EOF
Phytium baseline-seeded current-safe target compare complete.
  stable_summary:        $STABLE_SUMMARY_MD
  experimental_summary:  $EXPERIMENTAL_SUMMARY_MD
  compare_md:            $COMPARE_MD
  compare_json:          $COMPARE_JSON
EOF

if [[ "$COMPARE_RC" -eq 2 ]]; then
  echo "ERROR: compare invalid because distinct targets produced the same optimized_model.so hash." >&2
  exit "$COMPARE_RC"
fi
