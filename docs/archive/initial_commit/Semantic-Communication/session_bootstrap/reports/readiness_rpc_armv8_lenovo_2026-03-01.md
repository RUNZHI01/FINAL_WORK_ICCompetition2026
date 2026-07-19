# RPC Readiness Checklist

- generated_at: 2026-03-01T14:44:41+08:00
- env_file: session_bootstrap/config/rpc_armv8.lenovo.2026-03-01.env
- overall_status: PASS

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET=llvm -mtriple=aarch64-linux-gnu -mattr=+neon; DEVICE_KEY=replace_with_device_key; RPC_TRACKER_HOST=127.0.0.1; RPC_TRACKER_PORT=9190 |
| 执行策略：quick 可执行（20-40 分钟窗口） | 满足 | QUICK_REPEAT=2; QUICK_TIMEOUT_SEC=120; QUICK_BASELINE_CMD=mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8; QUICK_CURRENT_CMD=mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4 |
| 执行策略：full 可执行（夜间热点） | 满足 | FULL_TIMEOUT_SEC=180; FULL_BASELINE_CMD=bash "$FULL_RUNNER_SCRIPT" --label baseline --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_BASELINE_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"; FULL_CURRENT_CMD=bash "$FULL_RUNNER_SCRIPT" --label current --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_CURRENT_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs" |
| 执行策略：热点 Top3-8 已锁定 | 满足 | FULL_HOTSPOT_TASKS=conv2d_nchw_1,dense_1,layernorm_1; count=3 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_armv8_lenovo_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db |
| 执行策略：单变量实验字段已定义 | 满足 | DAILY_SINGLE_CHANGE=bootstrap machine-specific rpc env on lenovo orchestrator |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |

## 阻断项（最小修复）

- 无阻断项。
