# RPC Readiness Checklist

- generated_at: 2026-03-01T16:09:05+08:00
- env_file: session_bootstrap/config/rpc_armv8.phytium_pi.2026-03-01.env
- overall_status: PASS

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET=llvm -mtriple=aarch64-linux-gnu -mattr=+neon; DEVICE_KEY=armv8; RPC_TRACKER_HOST=10.194.7.123; RPC_TRACKER_PORT=9190 |
| 执行策略：quick 可执行（20-40 分钟窗口） | 满足 | QUICK_REPEAT=1; QUICK_TIMEOUT_SEC=180; QUICK_BASELINE_CMD=bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "test -f \"$REMOTE_TVM_PRIMARY_SO\" && test -f \"$REMOTE_TVM_PRIMARY_DB_RECORD\" && test -f \"$REMOTE_TVM_PRIMARY_DB_WORKLOAD\" && \"$REMOTE_TVM_PYTHON\" -c \"import tvm; print(tvm.__version__)\""; QUICK_CURRENT_CMD=bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "test -d \"$REMOTE_TVM_ALT_DIR\" && test -f \"$REMOTE_TVM_ALT_SO\" && ls -lh \"$REMOTE_TVM_ALT_SO\"" |
| 执行策略：full 可执行（夜间热点） | 满足 | FULL_TIMEOUT_SEC=600; FULL_BASELINE_CMD=bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "sha256sum \"$REMOTE_TVM_PRIMARY_SO\" \"$REMOTE_TVM_PRIMARY_DB_RECORD\" \"$REMOTE_TVM_PRIMARY_DB_WORKLOAD\""; FULL_CURRENT_CMD=bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"optimized_model.so\" | sort && echo \"---\" && find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"database_tuning_record.json\" | sort && find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"database_workload.json\" | sort" |
| 执行策略：热点 Top3-8 已锁定 | 满足 | FULL_HOTSPOT_TASKS=tvm_main_archive,jscc_experiment_archive,db_integrity; count=3 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_armv8_phytium_pi_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_phytium_pi_db |
| 执行策略：单变量实验字段已定义 | 满足 | DAILY_SINGLE_CHANGE=wire rpc first-round env to phytium board ip/key/python/path variables |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |

## 阻断项（最小修复）

- 无阻断项。
