# 实验记录

- 实验ID：EXP-RPC-FIRST-ROUND-20260301_131806
- 日期时间：2026-03-01T13:18:09+08:00
- 负责人：tianxing
- 模式：quick + full
- 目标task（热点编号）：conv2d_nchw_1,dense_1,layernorm_1
- 本轮唯一变量：switch execution entry to rpc first-round pipeline
- 变量取值：DEVICE_KEY=armv8_smoke; RPC_TRACKER_HOST=127.0.0.1; RPC_TRACKER_PORT=9190
- 固定条件（target/shape/线程/测量参数）：target=llvm -mtriple=aarch64-linux-gnu -mattr=+neon; shape_buckets=1x3x224x224; threads=4; quick_repeat=2; full_timeout_sec=120
- 预期收益：在 ARMv8 RPC runner 条件下维持 baseline -> current 的可解释变化
- 实际结果：quick(success) 813.226ms -> 413.209ms; baseline=2, current=2; full(success) 57.051ms -> 58.082ms
- 是否复现：离线模拟（非真机）
- 失败样本信息（可选）：若失败，见 readiness/daily/log 报告
- 下一步：替换为真机 tracker/server 与真实 TVM 命令后重跑

## 产物

- readiness：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/readiness_rpc_2026-03-01.md
- run env snapshot：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_131806.env
- rpc command templates：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_commands_20260301_131806.md
- quick report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round.md
- full report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_smoke_first_round.md
- daily report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/daily_rpc_smoke_first_round.md
