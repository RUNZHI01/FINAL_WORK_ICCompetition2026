#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/rpc_armv8.example.env"

usage() {
  cat <<'EOF'
Usage:
  check_rpc_readiness.sh [--env <path>] [--output <path>]

Notes:
  - 输出 readiness checklist（满足/不满足/证据）和阻断项。
  - 若存在阻断项，脚本返回非零状态码。
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env requires a file path." >&2
        exit 1
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    --output)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --output requires a file path." >&2
        exit 1
      fi
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a
source "$ENV_FILE"
set +a

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

trim_value() {
  printf '%s' "$1" | awk '{$1=$1;print}'
}

normalize_token() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_'
}

has_pattern() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -q "$pattern" "$file"
  else
    grep -q -- "$pattern" "$file"
  fi
}

is_placeholder_cmd() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    ""|*replace*|*todo*|*"run baseline"*|*"run current"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_placeholder_value() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    ""|*replace*|*todo*|*changeme*|*example*|*placeholder*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

check_rows=()
blockers=()
blocked=0

env_file_name="$(basename "$ENV_FILE")"
mode_label_token="$(normalize_token "${TUNE_MODE_LABEL:-}")"
env_file_token="$(normalize_token "$env_file_name")"
warm_start_mode_hint=0
warm_start_incremental_mode=0
if { [[ "$mode_label_token" == *baseline_seeded_warm_start* ]] && [[ "$mode_label_token" == *current* ]]; } \
  || { [[ "$env_file_token" == *baseline_seeded_warm_start* ]] && [[ "$env_file_token" == *current* ]]; }; then
  warm_start_mode_hint=1
fi
if [[ "$warm_start_mode_hint" -eq 1 ]] \
  && [[ "${TUNE_REQUIRE_REAL:-0}" == "1" ]] \
  && [[ "${TUNE_RUNNER:-}" == "rpc" ]] \
  && [[ "${TUNE_TOTAL_TRIALS:-}" =~ ^[1-9][0-9]*$ ]]; then
  warm_start_incremental_mode=1
fi

add_check() {
  local item="$1"
  local ok="$2"
  local evidence="$3"
  local blocker_reason="${4:-}"
  local status="满足"
  if [[ "$ok" != "1" ]]; then
    status="不满足"
    blocked=1
    if [[ -n "$blocker_reason" ]]; then
      blockers+=("$blocker_reason")
    fi
  fi
  check_rows+=("| $item | $status | $evidence |")
}

target_lower="$(printf '%s' "${TARGET:-}" | tr '[:upper:]' '[:lower:]')"
arm_target_ok=0
if [[ "$target_lower" == *"aarch64"* || "$target_lower" == *"arm64"* || "$target_lower" == *"armv8"* ]]; then
  arm_target_ok=1
fi

rpc_role_ok=0
rpc_role_evidence="TARGET=${TARGET:-N/A}; DEVICE_KEY=${DEVICE_KEY:-N/A}; RPC_TRACKER_HOST=${RPC_TRACKER_HOST:-N/A}; RPC_TRACKER_PORT=${RPC_TRACKER_PORT:-N/A}"
if [[ "$arm_target_ok" -eq 1 && -n "${DEVICE_KEY:-}" && -n "${RPC_TRACKER_HOST:-}" && "${RPC_TRACKER_PORT:-}" =~ ^[0-9]+$ ]]; then
  rpc_role_ok=1
  if [[ "$warm_start_incremental_mode" -eq 1 ]] && { is_placeholder_value "${DEVICE_KEY:-}" || is_placeholder_value "${RPC_TRACKER_HOST:-}"; }; then
    rpc_role_ok=0
  fi
fi
add_check \
  "目标场景：ARMv8 runner + 开发机 builder/orchestrator" \
  "$rpc_role_ok" \
  "$rpc_role_evidence" \
  "补齐 ARMv8 TARGET / DEVICE_KEY / RPC_TRACKER_HOST / RPC_TRACKER_PORT。"

if [[ "$warm_start_incremental_mode" -eq 1 ]]; then
  add_check \
    "模式：baseline-seeded warm-start current incremental 已识别" \
    "1" \
    "TUNE_MODE_LABEL=${TUNE_MODE_LABEL:-N/A}; env_file=${env_file_name}; TUNE_REQUIRE_REAL=${TUNE_REQUIRE_REAL:-0}; TUNE_RUNNER=${TUNE_RUNNER:-N/A}; TUNE_TOTAL_TRIALS=${TUNE_TOTAL_TRIALS:-N/A}"
else
  quick_strategy_ok=0
  quick_strategy_evidence="QUICK_REPEAT=${QUICK_REPEAT:-N/A}; QUICK_TIMEOUT_SEC=${QUICK_TIMEOUT_SEC:-N/A}; QUICK_BASELINE_CMD=${QUICK_BASELINE_CMD:-N/A}; QUICK_CURRENT_CMD=${QUICK_CURRENT_CMD:-N/A}"
  if [[ "${QUICK_REPEAT:-}" =~ ^[0-9]+$ && "${QUICK_REPEAT:-0}" -ge 1 ]] \
    && [[ "${QUICK_TIMEOUT_SEC:-}" =~ ^[0-9]+$ ]] \
    && ! is_placeholder_cmd "${QUICK_BASELINE_CMD:-}" \
    && ! is_placeholder_cmd "${QUICK_CURRENT_CMD:-}"; then
    quick_strategy_ok=1
  fi
  add_check \
    "执行策略：quick 可执行（20-40 分钟窗口）" \
    "$quick_strategy_ok" \
    "$quick_strategy_evidence" \
    "补齐 QUICK_* 命令与预算参数（避免占位符命令）。"

  full_strategy_ok=0
  full_strategy_evidence="FULL_TIMEOUT_SEC=${FULL_TIMEOUT_SEC:-N/A}; FULL_BASELINE_CMD=${FULL_BASELINE_CMD:-N/A}; FULL_CURRENT_CMD=${FULL_CURRENT_CMD:-N/A}"
  if [[ "${FULL_TIMEOUT_SEC:-}" =~ ^[0-9]+$ ]] \
    && ! is_placeholder_cmd "${FULL_BASELINE_CMD:-}" \
    && ! is_placeholder_cmd "${FULL_CURRENT_CMD:-}"; then
    full_strategy_ok=1
  fi
  add_check \
    "执行策略：full 可执行（夜间热点）" \
    "$full_strategy_ok" \
    "$full_strategy_evidence" \
    "补齐 FULL_* 命令与超时预算。"
fi

uses_remote_payload=0
for cmd in "${QUICK_BASELINE_CMD:-}" "${QUICK_CURRENT_CMD:-}" "${FULL_BASELINE_CMD:-}" "${FULL_CURRENT_CMD:-}"; do
  if [[ "$cmd" == *"run_remote_tvm_payload.sh"* ]]; then
    uses_remote_payload=1
    break
  fi
done

remote_payload_ok=1
remote_payload_evidence="uses_remote_payload=${uses_remote_payload}"
if [[ "$uses_remote_payload" -eq 1 ]]; then
  remote_mode_raw="${REMOTE_MODE:-ssh}"
  remote_mode="$(printf '%s' "$remote_mode_raw" | tr '[:upper:]' '[:lower:]')"
  missing_remote_fields=()
  remote_required_vars=(
    REMOTE_TVM_PYTHON
    REMOTE_TVM_PRIMARY_DIR
    REMOTE_TVM_JSCC_BASE_DIR
    REMOTE_FULL_BASELINE_ARCHIVES
    REMOTE_FULL_CURRENT_ARCHIVES
  )
  if [[ "$remote_mode" == "ssh" ]]; then
    remote_required_vars=(
      REMOTE_HOST
      REMOTE_USER
      REMOTE_PASS
      "${remote_required_vars[@]}"
    )
  elif [[ "$remote_mode" != "local" ]]; then
    remote_payload_ok=0
    missing_remote_fields+=("REMOTE_MODE")
  fi

  for var_name in "${remote_required_vars[@]}"; do
    var_value="${!var_name:-}"
    if is_placeholder_value "$var_value"; then
      remote_payload_ok=0
      missing_remote_fields+=("$var_name")
    fi
  done

  missing_fields_text="none"
  if [[ "${#missing_remote_fields[@]}" -gt 0 ]]; then
    missing_fields_text="$(printf '%s,' "${missing_remote_fields[@]}")"
    missing_fields_text="${missing_fields_text%,}"
  fi

  # When using local mode, make sure local archives already contain probe artifacts.
  if [[ "$remote_payload_ok" -eq 1 && "$remote_mode" == "local" ]]; then
    declare -A seen_archives=()
    archive_candidates=(
      "${REMOTE_TVM_PRIMARY_DIR:-}"
      "${REMOTE_TVM_JSCC_BASE_DIR:-}"
    )

    IFS=',' read -r -a baseline_archives <<< "${REMOTE_FULL_BASELINE_ARCHIVES:-}"
    IFS=',' read -r -a current_archives <<< "${REMOTE_FULL_CURRENT_ARCHIVES:-}"
    archive_candidates+=("${baseline_archives[@]}" "${current_archives[@]}")

    local_missing_artifacts=()
    for archive in "${archive_candidates[@]}"; do
      archive_trimmed="$(trim_value "$archive")"
      if [[ -z "$archive_trimmed" ]]; then
        continue
      fi
      if [[ -n "${seen_archives[$archive_trimmed]:-}" ]]; then
        continue
      fi
      seen_archives["$archive_trimmed"]=1

      for rel in "tvm_tune_logs/optimized_model.so" "tuning_logs/database_workload.json" "tuning_logs/database_tuning_record.json"; do
        if [[ ! -f "$archive_trimmed/$rel" ]]; then
          local_missing_artifacts+=("$archive_trimmed/$rel")
        fi
      done
    done

    local_python_ok=1
    if ! "${REMOTE_TVM_PYTHON}" -c "import tvm" >/dev/null 2>&1; then
      local_python_ok=0
    fi

    if [[ "${#local_missing_artifacts[@]}" -gt 0 ]]; then
      remote_payload_ok=0
      first_missing="${local_missing_artifacts[0]}"
      remote_payload_evidence="uses_remote_payload=1; remote_mode=local; missing_or_placeholder=${missing_fields_text}; missing_artifacts=${#local_missing_artifacts[@]}; first_missing=${first_missing}; python_import_tvm=${local_python_ok}; REMOTE_TVM_PYTHON=${REMOTE_TVM_PYTHON:-N/A}"
    else
      if [[ "$local_python_ok" -eq 0 ]]; then
        remote_payload_ok=0
        remote_payload_evidence="uses_remote_payload=1; remote_mode=local; missing_or_placeholder=${missing_fields_text}; local_artifacts_ok=1; python_import_tvm=0; REMOTE_TVM_PYTHON=${REMOTE_TVM_PYTHON:-N/A}; REMOTE_TVM_PRIMARY_DIR=${REMOTE_TVM_PRIMARY_DIR:-N/A}"
      else
        remote_payload_evidence="uses_remote_payload=1; remote_mode=local; missing_or_placeholder=${missing_fields_text}; local_artifacts_ok=1; python_import_tvm=1; REMOTE_TVM_PYTHON=${REMOTE_TVM_PYTHON:-N/A}; REMOTE_TVM_PRIMARY_DIR=${REMOTE_TVM_PRIMARY_DIR:-N/A}"
      fi
    fi
  else
    remote_payload_evidence="uses_remote_payload=1; remote_mode=${remote_mode:-N/A}; missing_or_placeholder=${missing_fields_text}; REMOTE_HOST=${REMOTE_HOST:-N/A}; REMOTE_TVM_PRIMARY_DIR=${REMOTE_TVM_PRIMARY_DIR:-N/A}"
  fi
fi
add_check \
  "执行策略：远端 TVM prep payload 参数完整" \
  "$remote_payload_ok" \
  "$remote_payload_evidence" \
  "补齐 REMOTE_* 参数；若 REMOTE_MODE=local，确保 archive 下已有 tvm_tune_logs/optimized_model.so 与 tuning_logs/database_*.json。"

if [[ "$warm_start_incremental_mode" -eq 0 ]]; then
  hotspot_count=0
  if [[ -n "${FULL_HOTSPOT_TASKS:-}" ]]; then
    IFS=',' read -r -a hotspot_arr <<< "${FULL_HOTSPOT_TASKS}"
    for item in "${hotspot_arr[@]}"; do
      if [[ -n "$(trim_value "$item")" ]]; then
        hotspot_count="$((hotspot_count + 1))"
      fi
    done
  fi
  hotspot_ok=0
  if [[ "$hotspot_count" -ge 3 && "$hotspot_count" -le 8 ]]; then
    hotspot_ok=1
  fi
  add_check \
    "执行策略：热点 Top3-8 已锁定" \
    "$hotspot_ok" \
    "FULL_HOTSPOT_TASKS=${FULL_HOTSPOT_TASKS:-N/A}; count=${hotspot_count}" \
    "将 FULL_HOTSPOT_TASKS 约束在 3-8 个任务。"
fi

db_dir_resolved="$(resolve_path "${TUNING_DB_DIR:-}")"
db_ok=0
if [[ -n "${TUNING_DB_DIR:-}" ]]; then
  mkdir -p "$db_dir_resolved"
  db_ok=1
fi
add_check \
  "执行策略：tuning DB 复用路径可写" \
  "$db_ok" \
  "TUNING_DB_DIR=${TUNING_DB_DIR:-N/A}; resolved=${db_dir_resolved}" \
  "配置 TUNING_DB_DIR 并确保可写。"

if [[ "$warm_start_incremental_mode" -eq 1 ]]; then
  safe_runtime_remote_ok=0
  remote_pass_state="missing"
  remote_python_state="missing"
  if [[ -n "${REMOTE_PASS:-}" ]]; then
    remote_pass_state="set"
  fi
  if [[ -n "${REMOTE_TVM_PYTHON:-}" ]]; then
    remote_python_state="set"
  fi
  if [[ "${REMOTE_MODE:-ssh}" == "ssh" ]] \
    && ! is_placeholder_value "${REMOTE_HOST:-}" \
    && ! is_placeholder_value "${REMOTE_USER:-}" \
    && ! is_placeholder_value "${REMOTE_PASS:-}" \
    && [[ "${REMOTE_SSH_PORT:-}" =~ ^[0-9]+$ ]] \
    && ! is_placeholder_value "${REMOTE_TVM_PYTHON:-}" \
    && ! is_placeholder_value "${REMOTE_TVM_JSCC_BASE_DIR:-}"; then
    safe_runtime_remote_ok=1
  fi
  add_check \
    "执行策略：safe runtime 下游 one-shot SSH 信息完整" \
    "$safe_runtime_remote_ok" \
    "REMOTE_MODE=${REMOTE_MODE:-N/A}; REMOTE_HOST=${REMOTE_HOST:-N/A}; REMOTE_USER=${REMOTE_USER:-N/A}; REMOTE_PASS=${remote_pass_state}; REMOTE_SSH_PORT=${REMOTE_SSH_PORT:-N/A}; REMOTE_TVM_PYTHON=${remote_python_state}; REMOTE_TVM_JSCC_BASE_DIR=${REMOTE_TVM_JSCC_BASE_DIR:-N/A}" \
    "补齐 safe runtime 下游 one-shot 所需的 REMOTE_MODE=ssh / REMOTE_HOST / REMOTE_USER / REMOTE_PASS / REMOTE_SSH_PORT / REMOTE_TVM_PYTHON / REMOTE_TVM_JSCC_BASE_DIR。"
else
  single_var_ok=0
  if [[ -n "${DAILY_SINGLE_CHANGE:-}" && "${DAILY_SINGLE_CHANGE}" != "TODO" ]]; then
    single_var_ok=1
  fi
  add_check \
    "执行策略：单变量实验字段已定义" \
    "$single_var_ok" \
    "DAILY_SINGLE_CHANGE=${DAILY_SINGLE_CHANGE:-N/A}" \
    "在 env 中填写 DAILY_SINGLE_CHANGE（仅一个变量）。"
fi

quick_script="$SESSION_DIR/scripts/run_quick.sh"
acceptance_ok=0
if has_pattern "baseline_median_ms" "$quick_script" \
  && has_pattern "current_median_ms" "$quick_script" \
  && has_pattern "baseline_count" "$quick_script" \
  && has_pattern "current_count" "$quick_script" \
  && has_pattern "baseline_variance_ms2" "$quick_script" \
  && has_pattern "current_variance_ms2" "$quick_script"; then
  acceptance_ok=1
fi
add_check \
  "验收要素：baseline/current + 有效样本 + 稳定性字段" \
  "$acceptance_ok" \
  "checked_fields=baseline/current/count/variance in run_quick.sh" \
  "在 quick 报告中补齐 baseline/current/count/variance 字段。"

daily_tpl="$SESSION_DIR/templates/daily_report_template.md"
exp_tpl="$SESSION_DIR/templates/experiment_record_template.md"
daily_ok=0
if [[ -f "$daily_tpl" && -f "$exp_tpl" ]]; then
  daily_ok=1
fi
add_check \
  "验收要素：日报与实验记录模板存在" \
  "$daily_ok" \
  "daily_template=${daily_tpl}; experiment_template=${exp_tpl}" \
  "补齐 daily_report_template.md 与 experiment_record_template.md。"

rpc_entry_ok=0
if [[ -x "$SESSION_DIR/scripts/rpc_print_cmd_templates.sh" && -x "$SESSION_DIR/scripts/run_rpc_first_round.sh" ]]; then
  rpc_entry_ok=1
fi
add_check \
  "首轮闭环入口：RPC 命令模板与执行入口脚本" \
  "$rpc_entry_ok" \
  "rpc_print_cmd_templates.sh + run_rpc_first_round.sh" \
  "补齐 RPC 命令模板脚本与首轮执行入口。"

# === RPC Tune mode checks (only when ONNX_MODEL_PATH is set) ===
if [[ -n "${ONNX_MODEL_PATH:-}" ]]; then

  onnx_resolved="$(resolve_path "$ONNX_MODEL_PATH")"
  onnx_ok=0
  if [[ -f "$onnx_resolved" ]]; then
    onnx_ok=1
  fi
  add_check \
    "RPC Tune：ONNX 模型文件存在" \
    "$onnx_ok" \
    "ONNX_MODEL_PATH=${ONNX_MODEL_PATH}; resolved=${onnx_resolved}" \
    "ONNX 文件不存在，运行 manage_rpc_services.sh prepare 从飞腾派拉取。"

  local_tvm_python="${LOCAL_TVM_PYTHON:-${TVM_PYTHON:-python3}}"
  tvm_import_ok=0
  if "$local_tvm_python" -c "import tvm; from tvm.relax.frontend.onnx import from_onnx" >/dev/null 2>&1; then
    tvm_import_ok=1
  fi
  local_tvm_item="RPC Tune：本机 TVM 可用（import tvm + from_onnx）"
  local_tvm_evidence="LOCAL_TVM_PYTHON=${LOCAL_TVM_PYTHON:-N/A}; resolved=${local_tvm_python}"
  local_tvm_ok="$tvm_import_ok"
  if [[ "$warm_start_incremental_mode" -eq 1 ]]; then
    local_tvm_item="RPC Tune：LOCAL_TVM_PYTHON 可用（import tvm + from_onnx）"
    if [[ -z "${LOCAL_TVM_PYTHON:-}" ]]; then
      local_tvm_ok=0
    fi
  fi
  add_check \
    "$local_tvm_item" \
    "$local_tvm_ok" \
    "$local_tvm_evidence" \
    "本机 TVM 环境异常，检查 LOCAL_TVM_PYTHON 路径和 tvm 安装。"

  tune_shape_ok=0
  if [[ -n "${TUNE_INPUT_SHAPE:-}" && "${TUNE_INPUT_SHAPE}" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
    tune_shape_ok=1
  fi
  add_check \
    "RPC Tune：TUNE_INPUT_SHAPE 格式正确" \
    "$tune_shape_ok" \
    "TUNE_INPUT_SHAPE=${TUNE_INPUT_SHAPE:-N/A}" \
    "TUNE_INPUT_SHAPE 必须为逗号分隔的整数（如 1,32,32,32）。"

  tune_trials_ok=0
  if [[ "${TUNE_TOTAL_TRIALS:-}" =~ ^[0-9]+$ && "${TUNE_TOTAL_TRIALS:-0}" -ge 1 ]]; then
    tune_trials_ok=1
  fi
  tune_trials_item="RPC Tune：TUNE_TOTAL_TRIALS 已配置"
  if [[ "$warm_start_incremental_mode" -eq 1 ]]; then
    tune_trials_item="RPC Tune：TUNE_TOTAL_TRIALS 非零"
  fi
  add_check \
    "$tune_trials_item" \
    "$tune_trials_ok" \
    "TUNE_TOTAL_TRIALS=${TUNE_TOTAL_TRIALS:-N/A}" \
    "TUNE_TOTAL_TRIALS 必须为正整数。"

  real_tune_guard_ok=1
  real_tune_guard_evidence="TUNE_REQUIRE_REAL=${TUNE_REQUIRE_REAL:-0}; TUNE_RUNNER=${TUNE_RUNNER:-rpc}; TUNE_TOTAL_TRIALS=${TUNE_TOTAL_TRIALS:-N/A}"
  if [[ "${TUNE_REQUIRE_REAL:-0}" == "1" ]]; then
    if [[ "${TUNE_RUNNER:-rpc}" != "rpc" ]] || [[ "$tune_trials_ok" -ne 1 ]]; then
      real_tune_guard_ok=0
    fi
  fi
  add_check \
    "RPC Tune：真调优护栏一致（require_real -> runner=rpc 且 trials>0）" \
    "$real_tune_guard_ok" \
    "$real_tune_guard_evidence" \
    "若要执行真机调优，设置 TUNE_REQUIRE_REAL=1、TUNE_RUNNER=rpc、TUNE_TOTAL_TRIALS>=1。"

  warm_start_ok=1
  warm_start_item="RPC Tune：warm-start DB 路径有效（若配置）"
  warm_start_blocker="若配置 TUNE_EXISTING_DB，确保目录下存在 database_workload.json 与 database_tuning_record.json。"
  warm_start_evidence="TUNE_EXISTING_DB=${TUNE_EXISTING_DB:-N/A}"
  if [[ "$warm_start_incremental_mode" -eq 1 ]]; then
    warm_start_item="RPC Tune：warm-start DB 路径有效（baseline-seeded 模式必需）"
    warm_start_blocker="baseline-seeded warm-start incremental 模式必须提供有效 TUNE_EXISTING_DB，且目录下存在 database_workload.json 与 database_tuning_record.json。"
  fi
  if [[ -n "${TUNE_EXISTING_DB:-}" ]] && ! is_placeholder_value "${TUNE_EXISTING_DB:-}"; then
    warm_start_resolved="$(resolve_path "$TUNE_EXISTING_DB")"
    if [[ -f "$warm_start_resolved/database_workload.json" && -f "$warm_start_resolved/database_tuning_record.json" ]]; then
      warm_start_evidence="TUNE_EXISTING_DB=${TUNE_EXISTING_DB}; resolved=${warm_start_resolved}; files=ok"
    else
      warm_start_ok=0
      warm_start_evidence="TUNE_EXISTING_DB=${TUNE_EXISTING_DB}; resolved=${warm_start_resolved}; files=missing"
    fi
  elif [[ "$warm_start_incremental_mode" -eq 1 ]]; then
    warm_start_ok=0
    warm_start_evidence="TUNE_EXISTING_DB=${TUNE_EXISTING_DB:-N/A}; required=1; files=missing"
  fi
  add_check \
    "$warm_start_item" \
    "$warm_start_ok" \
    "$warm_start_evidence" \
    "$warm_start_blocker"

  tune_output_ok=0
  tune_output_resolved="$(resolve_path "${TUNE_OUTPUT_DIR:-}")"
  if [[ -n "${TUNE_OUTPUT_DIR:-}" ]]; then
    mkdir -p "$tune_output_resolved" 2>/dev/null && tune_output_ok=1
  fi
  add_check \
    "RPC Tune：TUNE_OUTPUT_DIR 可写" \
    "$tune_output_ok" \
    "TUNE_OUTPUT_DIR=${TUNE_OUTPUT_DIR:-N/A}; resolved=${tune_output_resolved}" \
    "配置 TUNE_OUTPUT_DIR 并确保可写。"

  tracker_reachable_ok=0
  tracker_check_host="${RPC_TRACKER_HOST:-127.0.0.1}"
  tracker_check_port="${RPC_TRACKER_PORT:-9190}"
  if command -v timeout >/dev/null 2>&1; then
    if timeout 3 bash -lc "cat < /dev/null > /dev/tcp/${tracker_check_host}/${tracker_check_port}" 2>/dev/null; then
      tracker_reachable_ok=1
    fi
  fi
  add_check \
    "RPC Tune：Tracker 端口可达（${tracker_check_host}:${tracker_check_port}）" \
    "$tracker_reachable_ok" \
    "host=${tracker_check_host}; port=${tracker_check_port}" \
    "Tracker 未运行或不可达，先运行 manage_rpc_services.sh start-tracker。"

fi

generated_at="$(date -Iseconds)"
output_resolved=""
if [[ -n "$OUTPUT_FILE" ]]; then
  output_resolved="$(resolve_path "$OUTPUT_FILE")"
else
  report_dir_resolved="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
  mkdir -p "$report_dir_resolved"
  output_resolved="$report_dir_resolved/readiness_rpc_$(date +%F).md"
fi

mkdir -p "$(dirname "$output_resolved")"

{
  cat <<EOF
# RPC Readiness Checklist

- generated_at: $generated_at
- env_file: $ENV_FILE
- overall_status: $(if [[ "$blocked" -eq 0 ]]; then echo "PASS"; else echo "BLOCKED"; fi)

| 检查项 | 状态 | 证据 |
|---|---|---|
EOF
  printf '%s\n' "${check_rows[@]}"
  echo
  echo "## 阻断项（最小修复）"
  if [[ "${#blockers[@]}" -eq 0 ]]; then
    echo
    echo "- 无阻断项。"
  else
    echo
    for blocker in "${blockers[@]}"; do
      echo "- $blocker"
    done
  fi
} >"$output_resolved"

echo "Readiness report generated: $output_resolved"

if [[ "$blocked" -ne 0 ]]; then
  exit 2
fi
