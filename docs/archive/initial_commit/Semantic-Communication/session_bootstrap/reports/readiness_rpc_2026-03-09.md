# RPC Readiness Checklist

- generated_at: 2026-03-09T14:25:30+08:00
- env_file: ./session_bootstrap/config/rpc_tune_target_cortex_a72.2026-03-09.phytium_pi.env
- overall_status: BLOCKED

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET={"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+aes","+pmull","+sha1","+sha2","+crc","+sha3","+sha512"],"num-cores":4}; DEVICE_KEY=armv8; RPC_TRACKER_HOST=100.121.87.73; RPC_TRACKER_PORT=9190 |
| 执行策略：quick 可执行（20-40 分钟窗口） | 满足 | QUICK_REPEAT=1; QUICK_TIMEOUT_SEC=1800; QUICK_BASELINE_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline; QUICK_CURRENT_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current |
| 执行策略：full 可执行（夜间热点） | 满足 | FULL_TIMEOUT_SEC=3600; FULL_BASELINE_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile full --variant baseline; FULL_CURRENT_CMD=bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile full --variant current |
| 执行策略：远端 TVM prep payload 参数完整 | 满足 | uses_remote_payload=1; remote_mode=ssh; missing_or_placeholder=none; REMOTE_HOST=100.121.87.73; REMOTE_TVM_PRIMARY_DIR=/home/user/Downloads/5.1TVM优化结果 |
| 执行策略：热点 Top3-8 已锁定 | 满足 | FULL_HOTSPOT_TASKS=mirror_pad1,mirror_pad2,mirror_pad; count=3 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_tune_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db |
| 执行策略：单变量实验字段已定义 | 不满足 | DAILY_SINGLE_CHANGE=N/A |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |
| RPC Tune：ONNX 模型文件存在 | 满足 | ONNX_MODEL_PATH=/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx; resolved=/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx |
| RPC Tune：本机 TVM 可用（import tvm + from_onnx） | 满足 | LOCAL_TVM_PYTHON=/home/tianxing/.venvs/tvm-ms/bin/python |
| RPC Tune：TUNE_INPUT_SHAPE 格式正确 | 满足 | TUNE_INPUT_SHAPE=1,32,32,32 |
| RPC Tune：TUNE_TOTAL_TRIALS 已配置 | 满足 | TUNE_TOTAL_TRIALS=64 |
| RPC Tune：真调优护栏一致（require_real -> runner=rpc 且 trials>0） | 满足 | TUNE_REQUIRE_REAL=1; TUNE_RUNNER=rpc; TUNE_TOTAL_TRIALS=64 |
| RPC Tune：warm-start DB 路径有效（若配置） | 满足 | TUNE_EXISTING_DB=./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs; files=ok |
| RPC Tune：TUNE_OUTPUT_DIR 可写 | 满足 | TUNE_OUTPUT_DIR=./session_bootstrap/tmp/rpc_tune_target_cortex_a72_20260309; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_target_cortex_a72_20260309 |
| RPC Tune：Tracker 端口可达（100.121.87.73:9190） | 满足 | host=100.121.87.73; port=9190 |

## 阻断项（最小修复）

- 在 env 中填写 DAILY_SINGLE_CHANGE（仅一个变量）。
