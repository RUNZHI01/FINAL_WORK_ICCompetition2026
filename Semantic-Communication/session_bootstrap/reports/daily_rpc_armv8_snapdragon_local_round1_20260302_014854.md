# Daily Report

- 日期：2026-03-02
- 执行人：tianxing
- 今日唯一改动变量：switch prep execution host to local snapdragon while keeping phytium target fixed
- 实验模式：quick
- 目标模型与shape桶：smoke_rpc_model:1x3x224x224
- target与线程配置：llvm -mtriple=aarch64-linux-gnu -mattr=+neon/threads=4
- 延迟对比（baseline -> current）：quick_rpc_smoke_first_round_20260302_001226(quick): 819.013ms -> 420.856ms (delta -398.157ms, 48.61%); quick_rpc_smoke_first_round_20260302_001523(quick): 818.968ms -> 416.589ms (delta -402.379ms, 49.13%); quick_rpc_smoke_first_round_20260302_001644(quick): 816.228ms -> 417.288ms (delta -398.940ms, 48.88%)
- 有效样本（baseline/current）：quick_rpc_smoke_first_round_20260302_001226(quick): baseline=2, current=2; quick_rpc_smoke_first_round_20260302_001523(quick): baseline=2, current=2; quick_rpc_smoke_first_round_20260302_001644(quick): baseline=3, current=3
- 稳定性（复测中位数/方差）：quick_rpc_smoke_first_round_20260302_001226(quick): var 0.680625 -> 4.445772; quick_rpc_smoke_first_round_20260302_001523(quick): var 2.678132 -> 0.023409; quick_rpc_smoke_first_round_20260302_001644(quick): var 0.557102 -> 0.865664
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001226.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round_20260302_001226.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001226_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001523.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round_20260302_001523.log
- 异常与处理：未发现失败关键词。
- 结论：已聚合 3 份报告（quick=3, full=0）。
- 明日单一改动计划：ensure local archives contain tvm_tune_logs + tuning_logs artifacts, then run closed-loop prep

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| quick_rpc_smoke_first_round_20260302_001226 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 48.61 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001226.md |
| quick_rpc_smoke_first_round_20260302_001523 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 49.13 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001523.md |
| quick_rpc_smoke_first_round_20260302_001644 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 48.88 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001644.md |

## Log Snapshot

- 当日日志文件数：8
- 命中失败关键词日志数：0
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001226.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001523.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001644.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001226.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001523.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001644.md

## Metadata

- generated_at: 2026-03-02T01:48:55+08:00
- generated_by: summarize_to_daily.sh
