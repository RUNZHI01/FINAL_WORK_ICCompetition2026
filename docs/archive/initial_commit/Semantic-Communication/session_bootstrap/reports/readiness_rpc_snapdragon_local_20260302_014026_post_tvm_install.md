# RPC Readiness Checklist

- generated_at: 2026-03-02T01:40:27+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.snapdragon_local.2026-03-01.env
- overall_status: BLOCKED

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET=llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc; DEVICE_KEY=armv8; RPC_TRACKER_HOST=127.0.0.1; RPC_TRACKER_PORT=9190 |
| 执行策略：quick 可执行（20-40 分钟窗口） | 满足 | QUICK_REPEAT=1; QUICK_TIMEOUT_SEC=2700; QUICK_BASELINE_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline; QUICK_CURRENT_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current |
| 执行策略：full 可执行（夜间热点） | 满足 | FULL_TIMEOUT_SEC=5400; FULL_BASELINE_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile full --variant baseline; FULL_CURRENT_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile full --variant current |
| 执行策略：远端 TVM prep payload 参数完整 | 不满足 | uses_remote_payload=1; remote_mode=local; missing_or_placeholder=none; missing_artifacts=3; first_missing=/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_tune_logs/optimized_model.so; python_import_tvm=1; REMOTE_TVM_PYTHON=/home/tianxing/.venvs/tvm-ms/bin/python |
| 执行策略：热点 Top3-8 已锁定 | 满足 | FULL_HOTSPOT_TASKS=tvm_primary_archive,jscc_base_archive,jscc_3000_archive,jscc_dynamic20_archive; count=4 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_armv8_snapdragon_local_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_snapdragon_local_db |
| 执行策略：单变量实验字段已定义 | 满足 | DAILY_SINGLE_CHANGE=switch prep execution host to local snapdragon while keeping phytium target fixed |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |

## 阻断项（最小修复）

- 补齐 REMOTE_* 参数；若 REMOTE_MODE=local，确保 archive 下已有 tvm_tune_logs/optimized_model.so 与 tuning_logs/database_*.json。
