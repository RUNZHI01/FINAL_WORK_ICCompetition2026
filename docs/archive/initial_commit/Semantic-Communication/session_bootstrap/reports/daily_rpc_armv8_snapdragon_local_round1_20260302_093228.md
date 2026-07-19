# Daily Report

- 日期：2026-03-02
- 执行人：tianxing
- 今日唯一改动变量：switch prep execution host to local snapdragon while keeping phytium target fixed
- 实验模式：quick
- 目标模型与shape桶：jscc:1x3x224x224,1x3x256x256; smoke_rpc_model:1x3x224x224
- target与线程配置：llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc/threads=4; llvm -mtriple=aarch64-linux-gnu -mattr=+neon/threads=4
- 延迟对比（baseline -> current）：quick_rpc_armv8_snapdragon_local_round1_20260302_015535(quick): status=failed_baseline, baseline=NA, current=NA; quick_rpc_armv8_snapdragon_local_round1_20260302_015641(quick): 8686.534ms -> 8667.809ms (delta -18.725ms, 0.22%); quick_rpc_armv8_snapdragon_local_round1_20260302_091050(quick): 309491.284ms -> 309433.617ms (delta -57.667ms, 0.02%); quick_rpc_armv8_snapdragon_local_round1_20260302_092125(quick): 310572.949ms -> 309695.503ms (delta -877.446ms, 0.28%); quick_rpc_armv8_snapdragon_local_round1_20260302_093228(quick): 310195.769ms -> 309945.425ms (delta -250.344ms, 0.08%); quick_rpc_smoke_first_round_20260302_001226(quick): 819.013ms -> 420.856ms (delta -398.157ms, 48.61%); quick_rpc_smoke_first_round_20260302_001523(quick): 818.968ms -> 416.589ms (delta -402.379ms, 49.13%); quick_rpc_smoke_first_round_20260302_001644(quick): 816.228ms -> 417.288ms (delta -398.940ms, 48.88%)
- 有效样本（baseline/current）：quick_rpc_armv8_snapdragon_local_round1_20260302_015535(quick): baseline=0, current=0; quick_rpc_armv8_snapdragon_local_round1_20260302_015641(quick): baseline=1, current=1; quick_rpc_armv8_snapdragon_local_round1_20260302_091050(quick): baseline=1, current=1; quick_rpc_armv8_snapdragon_local_round1_20260302_092125(quick): baseline=1, current=1; quick_rpc_armv8_snapdragon_local_round1_20260302_093228(quick): baseline=1, current=1; quick_rpc_smoke_first_round_20260302_001226(quick): baseline=2, current=2; quick_rpc_smoke_first_round_20260302_001523(quick): baseline=2, current=2; quick_rpc_smoke_first_round_20260302_001644(quick): baseline=3, current=3
- 稳定性（复测中位数/方差）：quick_rpc_armv8_snapdragon_local_round1_20260302_015535(quick): status=failed_baseline, var NA -> NA; quick_rpc_armv8_snapdragon_local_round1_20260302_015641(quick): var 0.000000 -> 0.000000; quick_rpc_armv8_snapdragon_local_round1_20260302_091050(quick): var 0.000000 -> 0.000000; quick_rpc_armv8_snapdragon_local_round1_20260302_092125(quick): var 0.000000 -> 0.000000; quick_rpc_armv8_snapdragon_local_round1_20260302_093228(quick): var 0.000000 -> 0.000000; quick_rpc_smoke_first_round_20260302_001226(quick): var 0.680625 -> 4.445772; quick_rpc_smoke_first_round_20260302_001523(quick): var 2.678132 -> 0.023409; quick_rpc_smoke_first_round_20260302_001644(quick): var 0.557102 -> 0.865664
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015535.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_snapdragon_local_round1_20260302_015535.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015535_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015641.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_snapdragon_local_round1_20260302_015641.log
- 异常与处理：failed_reports=1; logs_with_error_keywords=1
- 结论：已聚合 8 份报告（quick=8, full=0）。
- 明日单一改动计划：ensure local archives contain tvm_tune_logs + tuning_logs artifacts, then run closed-loop prep

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| quick_rpc_armv8_snapdragon_local_round1_20260302_015535 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | failed_baseline | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015535.md |
| quick_rpc_armv8_snapdragon_local_round1_20260302_015641 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 0.22 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015641.md |
| quick_rpc_armv8_snapdragon_local_round1_20260302_091050 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 0.02 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_091050.md |
| quick_rpc_armv8_snapdragon_local_round1_20260302_092125 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 0.28 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_092125.md |
| quick_rpc_armv8_snapdragon_local_round1_20260302_093228 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 0.08 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_093228.md |
| quick_rpc_smoke_first_round_20260302_001226 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 48.61 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001226.md |
| quick_rpc_smoke_first_round_20260302_001523 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 49.13 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001523.md |
| quick_rpc_smoke_first_round_20260302_001644 | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 48.88 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001644.md |

## Log Snapshot

- 当日日志文件数：21
- 命中失败关键词日志数：1
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001226.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001523.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/auto_round_20260302_001644.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015535.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015641.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_091050.md

## Metadata

- generated_at: 2026-03-02T09:42:53+08:00
- generated_by: summarize_to_daily.sh
