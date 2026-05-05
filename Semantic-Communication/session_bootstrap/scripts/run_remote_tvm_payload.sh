#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_remote_tvm_payload.sh --profile <quick|full> --variant <baseline|current>

Notes:
  - Reads payload parameters from current env.
  - REMOTE_MODE=ssh (default): run on remote board via SSH.
  - REMOTE_MODE=local: run directly on local machine (no SSH).
  - Quick mode defaults to REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY=fresh-process
    to avoid same-process repeated load_module() instability on large Relax/VM artifacts.
EOF
}

PROFILE=""
VARIANT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --variant)
      VARIANT="${2:-}"
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

if [[ "$PROFILE" != "quick" && "$PROFILE" != "full" ]]; then
  echo "ERROR: --profile must be quick or full." >&2
  exit 1
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

for req in REMOTE_TVM_PYTHON REMOTE_TVM_PRIMARY_DIR; do
  require_var "$req"
done

if [[ "$REMOTE_MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

archives_csv=""
budget_sec=0
min_rounds=0

if [[ "$PROFILE" == "quick" ]]; then
  require_var REMOTE_TVM_JSCC_BASE_DIR
  budget_sec="${QUICK_BUDGET_SEC_PER_ARCHIVE:-900}"
  min_rounds="${QUICK_MIN_ROUNDS:-20}"
  if [[ "$VARIANT" == "baseline" ]]; then
    archives_csv="$REMOTE_TVM_PRIMARY_DIR"
  else
    archives_csv="$REMOTE_TVM_JSCC_BASE_DIR"
  fi
else
  require_var REMOTE_FULL_BASELINE_ARCHIVES
  require_var REMOTE_FULL_CURRENT_ARCHIVES
  budget_sec="${FULL_BUDGET_SEC_PER_ARCHIVE:-300}"
  min_rounds="${FULL_MIN_ROUNDS:-15}"
  if [[ "$VARIANT" == "baseline" ]]; then
    archives_csv="$REMOTE_FULL_BASELINE_ARCHIVES"
  else
    archives_csv="$REMOTE_FULL_CURRENT_ARCHIVES"
  fi
fi

if ! [[ "$budget_sec" =~ ^[0-9]+$ ]] || [[ "$budget_sec" -lt 1 ]]; then
  echo "ERROR: budget seconds must be a positive integer." >&2
  exit 1
fi

if ! [[ "$min_rounds" =~ ^[0-9]+$ ]] || [[ "$min_rounds" -lt 1 ]]; then
  echo "ERROR: min rounds must be a positive integer." >&2
  exit 1
fi

if [[ -z "$archives_csv" ]]; then
  echo "ERROR: archive set is empty for profile=$PROFILE variant=$VARIANT" >&2
  exit 1
fi

REMOTE_PAYLOAD_LOAD_DB_VALUE="${REMOTE_PAYLOAD_LOAD_DB:-1}"
REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY_VALUE="${REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY:-fresh-process}"
REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY_VALUE="${REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY:-same-process}"

run_probe_python() {
  local py_script
  local rc=0
  py_script="$(mktemp)"
  cat >"$py_script" <<'PY'
import json
import os
import statistics
import subprocess
import sys
import time

archives_csv, budget_sec_raw, min_rounds_raw, profile, variant = sys.argv[1:6]
budget_sec = int(budget_sec_raw)
min_rounds = int(min_rounds_raw)
archives = [x.strip() for x in archives_csv.split(",") if x.strip()]
if not archives:
    raise SystemExit("ERROR: no archives to probe")

import tvm  # pylint: disable=import-error
from tvm.runtime import load_module  # pylint: disable=import-error

load_db = os.environ.get("REMOTE_PAYLOAD_LOAD_DB", "1").lower() not in ("0", "false", "no")
quick_load_strategy = os.environ.get("REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY", "fresh-process")
non_quick_load_strategy = os.environ.get("REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY", "same-process")
load_strategy = quick_load_strategy if profile == "quick" else non_quick_load_strategy
load_strategy = load_strategy.strip().lower().replace("_", "-")
if load_strategy not in ("same-process", "fresh-process"):
    raise SystemExit(f"ERROR: unsupported load strategy: {load_strategy}")

json_db_cls = None
import_errors = []
if load_db:
    for mod_path in ("tvm.s_tir.meta_schedule.database", "tvm.meta_schedule.database"):
        try:
            module = __import__(mod_path, fromlist=["JSONDatabase"])
            json_db_cls = getattr(module, "JSONDatabase")
            break
        except Exception as err:  # pylint: disable=broad-except
            import_errors.append(f"{mod_path}: {err}")

    if json_db_cls is None:
        raise SystemExit("ERROR: JSONDatabase import failed: " + " | ".join(import_errors))

report = {
    "profile": profile,
    "variant": variant,
    "budget_sec_per_archive": budget_sec,
    "min_rounds_per_archive": min_rounds,
    "load_db": load_db,
    "load_strategy": load_strategy,
    "tvm_version": tvm.__version__,
    "archives": [],
}
all_elapsed_ms = []


def touch_module(mod):
    try:
        _ = str(mod.type_key)
    except Exception:  # pylint: disable=broad-except
        _ = str(mod)
    return _


SINGLE_LOAD_CHILD = r'''
import json
import os
import time
import tvm
from tvm.runtime import load_module

so_path = os.environ["TVM_SO_PATH"]
t0 = time.perf_counter()
mod = load_module(so_path)
try:
    _ = str(mod.type_key)
except Exception:
    _ = str(mod)
print(json.dumps({"elapsed_ms": (time.perf_counter() - t0) * 1000.0}, ensure_ascii=False))
'''


def parse_last_json_line(text):
    for line in reversed([x.strip() for x in text.splitlines() if x.strip()]):
        try:
            return json.loads(line)
        except Exception:  # pylint: disable=broad-except
            continue
    raise RuntimeError("no JSON payload found in child stdout")


def measure_single_load_same_process(so_path):
    t0 = time.perf_counter()
    mod = load_module(so_path)
    touch_module(mod)
    return (time.perf_counter() - t0) * 1000.0


def measure_single_load_fresh_process(so_path):
    proc = subprocess.run(
        [sys.executable, "-c", SINGLE_LOAD_CHILD],
        env={**os.environ, "TVM_SO_PATH": so_path},
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"fresh-process load probe failed rc={proc.returncode}: {details}"
        )
    payload = parse_last_json_line(proc.stdout)
    return float(payload["elapsed_ms"])


measure_single_load = (
    measure_single_load_fresh_process if load_strategy == "fresh-process" else measure_single_load_same_process
)

for archive in archives:
    so_path = os.path.join(archive, "tvm_tune_logs", "optimized_model.so")
    db_workload = os.path.join(archive, "tuning_logs", "database_workload.json")
    db_record = os.path.join(archive, "tuning_logs", "database_tuning_record.json")
    required = [so_path, db_workload, db_record]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        raise SystemExit("ERROR: missing artifacts: " + "; ".join(missing))

    per_archive_elapsed = []
    db_records = 0
    if load_db:
        db = json_db_cls(
            path_workload=db_workload,
            path_tuning_record=db_record,
            allow_missing=False,
        )
        db_records = len(db)

    start = time.perf_counter()
    rounds = 0
    while rounds < min_rounds or (time.perf_counter() - start) < budget_sec:
        elapsed_ms = measure_single_load(so_path)
        per_archive_elapsed.append(elapsed_ms)
        all_elapsed_ms.append(elapsed_ms)
        rounds += 1

    archive_report = {
        "archive": archive,
        "rounds": rounds,
        "db_records": db_records,
        "median_ms": round(statistics.median(per_archive_elapsed), 3),
        "mean_ms": round(sum(per_archive_elapsed) / len(per_archive_elapsed), 3),
        "variance_ms2": round(
            statistics.pvariance(per_archive_elapsed) if len(per_archive_elapsed) > 1 else 0.0,
            6,
        ),
    }
    report["archives"].append(archive_report)

summary = {
    "archives_count": len(report["archives"]),
    "samples": len(all_elapsed_ms),
    "median_ms": round(statistics.median(all_elapsed_ms), 3),
    "mean_ms": round(sum(all_elapsed_ms) / len(all_elapsed_ms), 3),
    "variance_ms2": round(
        statistics.pvariance(all_elapsed_ms) if len(all_elapsed_ms) > 1 else 0.0,
        6,
    ),
}
report["summary"] = summary

print(json.dumps(report, ensure_ascii=False))
PY

  if [[ "$REMOTE_MODE" == "ssh" ]]; then
    set +e
    bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$REMOTE_HOST" \
      --user "$REMOTE_USER" \
      --pass "$REMOTE_PASS" \
      --port "${REMOTE_SSH_PORT:-22}" \
      -- \
      env \
      "REMOTE_PAYLOAD_LOAD_DB=$REMOTE_PAYLOAD_LOAD_DB_VALUE" \
      "REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY=$REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY_VALUE" \
      "REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY=$REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY_VALUE" \
      "$REMOTE_TVM_PYTHON" - "$archives_csv" "$budget_sec" "$min_rounds" "$PROFILE" "$VARIANT" \
      <"$py_script"
    rc=$?
    set -e
    rm -f "$py_script"
    return "$rc"
  fi

  set +e
  env \
    "REMOTE_PAYLOAD_LOAD_DB=$REMOTE_PAYLOAD_LOAD_DB_VALUE" \
    "REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY=$REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY_VALUE" \
    "REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY=$REMOTE_PAYLOAD_NON_QUICK_LOAD_STRATEGY_VALUE" \
    "$REMOTE_TVM_PYTHON" - "$archives_csv" "$budget_sec" "$min_rounds" "$PROFILE" "$VARIANT" \
    <"$py_script"
  rc=$?
  set -e
  rm -f "$py_script"
  return "$rc"
}

run_probe_python
