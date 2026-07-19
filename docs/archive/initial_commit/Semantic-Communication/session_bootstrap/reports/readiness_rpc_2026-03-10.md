# RPC Readiness Checklist

- generated_at: 2026-03-10T23:15:50+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- overall_status: PASS

| 检查项 | 状态 | 证据 |
|---|---|---|
| 目标场景：ARMv8 runner + 开发机 builder/orchestrator | 满足 | TARGET={"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}; DEVICE_KEY=armv8; RPC_TRACKER_HOST=100.121.87.73; RPC_TRACKER_PORT=9190 |
| 模式：baseline-seeded warm-start current incremental 已识别 | 满足 | TUNE_MODE_LABEL=baseline_seeded_warm_start_current_safe_recommended_cortex_a72_neon; env_file=rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env; TUNE_REQUIRE_REAL=1; TUNE_RUNNER=rpc; TUNE_TOTAL_TRIALS=500 |
| 执行策略：远端 TVM prep payload 参数完整 | 满足 | uses_remote_payload=0 |
| 执行策略：tuning DB 复用路径可写 | 满足 | TUNING_DB_DIR=./session_bootstrap/tmp/rpc_tune_db; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db |
| 执行策略：safe runtime 下游 one-shot SSH 信息完整 | 满足 | REMOTE_MODE=ssh; REMOTE_HOST=100.121.87.73; REMOTE_USER=user; REMOTE_PASS=set; REMOTE_SSH_PORT=22; REMOTE_TVM_PYTHON=set; REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc |
| 验收要素：baseline/current + 有效样本 + 稳定性字段 | 满足 | checked_fields=baseline/current/count/variance in run_quick.sh |
| 验收要素：日报与实验记录模板存在 | 满足 | daily_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/daily_report_template.md; experiment_template=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/templates/experiment_record_template.md |
| 首轮闭环入口：RPC 命令模板与执行入口脚本 | 满足 | rpc_print_cmd_templates.sh + run_rpc_first_round.sh |
| RPC Tune：ONNX 模型文件存在 | 满足 | ONNX_MODEL_PATH=/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx; resolved=/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx |
| RPC Tune：LOCAL_TVM_PYTHON 可用（import tvm + from_onnx） | 满足 | LOCAL_TVM_PYTHON=/home/tianxing/.venvs/tvm-ms/bin/python; resolved=/home/tianxing/.venvs/tvm-ms/bin/python |
| RPC Tune：TUNE_INPUT_SHAPE 格式正确 | 满足 | TUNE_INPUT_SHAPE=1,32,32,32 |
| RPC Tune：TUNE_TOTAL_TRIALS 非零 | 满足 | TUNE_TOTAL_TRIALS=500 |
| RPC Tune：真调优护栏一致（require_real -> runner=rpc 且 trials>0） | 满足 | TUNE_REQUIRE_REAL=1; TUNE_RUNNER=rpc; TUNE_TOTAL_TRIALS=500 |
| RPC Tune：warm-start DB 路径有效（baseline-seeded 模式必需） | 满足 | TUNE_EXISTING_DB=./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs; files=ok |
| RPC Tune：TUNE_OUTPUT_DIR 可写 | 满足 | TUNE_OUTPUT_DIR=./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260310; resolved=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260310 |
| RPC Tune：Tracker 端口可达（100.121.87.73:9190） | 满足 | host=100.121.87.73; port=9190 |

## 阻断项（最小修复）

- 无阻断项。
