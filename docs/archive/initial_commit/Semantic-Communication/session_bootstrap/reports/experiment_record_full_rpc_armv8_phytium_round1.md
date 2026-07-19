# 实验记录

- 实验ID：EXP-RPC-FIRST-ROUND-20260301_165035
- 日期时间：2026-03-01T16:50:46+08:00
- 负责人：tianxing
- 模式：quick + full
- 目标task（热点编号）：tvm_main_archive,jscc_experiment_archive,db_integrity
- 本轮唯一变量：wire rpc first-round env to phytium board ip/key/python/path variables
- 变量取值：DEVICE_KEY=armv8; RPC_TRACKER_HOST=10.194.7.123; RPC_TRACKER_PORT=9190
- 固定条件（target/shape/线程/测量参数）：target=llvm -mtriple=aarch64-linux-gnu -mattr=+neon; shape_buckets=1x3x224x224,1x3x256x256; threads=4; quick_repeat=1; full_timeout_sec=600
- 预期收益：在 ARMv8 RPC runner 条件下维持 baseline -> current 的可解释变化
- 实际结果：quick(success) 6494.468ms -> 1046.129ms; baseline=1, current=1; full(success) 801.478ms -> 1555.451ms
- 是否复现：待真机确认
- 失败样本信息（可选）：若失败，见 readiness/daily/log 报告
- 下一步：执行夜间 full 热点并复查稳定性

## 产物

- readiness：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/readiness_rpc_2026-03-01.md
- run env snapshot：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_165035.env
- rpc command templates：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_commands_20260301_165035.md
- quick report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_phytium_round1.md
- full report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_round1.md
- daily report：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/daily_rpc_armv8_phytium_round1.md
