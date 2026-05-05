# RPC Readiness Checklist

- generated_at: 2026-03-01T13:17:12+08:00
- env_file: session_bootstrap/config/rpc_armv8.example.env
- overall_status: BLOCKED

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET=llvm -mtriple=aarch64-linux-gnu -mattr=+neon; DEVICE_KEY=replace_with_device_key; RPC_TRACKER_HOST=replace_with_tracker_ip; RPC_TRACKER_PORT=9190 |
| 执行策略：quick 可执行（20-40 分钟窗口） | 不满足 | QUICK_REPEAT=5; QUICK_TIMEOUT_SEC=2400; QUICK_BASELINE_CMD=echo "replace QUICK_BASELINE_CMD with real TVM RPC tuning/eval command" && exit 1; QUICK_CURRENT_CMD=echo "replace QUICK_CURRENT_CMD with real TVM RPC tuning/eval command" && exit 1 |
| 执行策略：full 可执行（夜间热点） | 不满足 | FULL_TIMEOUT_SEC=28800; FULL_BASELINE_CMD=echo "replace FULL_BASELINE_CMD with real TVM RPC hotspot command" && exit 1; FULL_CURRENT_CMD=echo "replace FULL_CURRENT_CMD with real TVM RPC hotspot command" && exit 1 |
| 执行策略：热点 Top3-8 已锁定 | 满足 | FULL_HOTSPOT_TASKS=task_1,task_2,task_3; count=3 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_db |
| 执行策略：单变量实验字段已定义 | 满足 | DAILY_SINGLE_CHANGE=replace_with_single_variable |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |

## 阻断项（最小修复）

- 补齐 QUICK_* 命令与预算参数（避免占位符命令）。
- 补齐 FULL_* 命令与超时预算。
