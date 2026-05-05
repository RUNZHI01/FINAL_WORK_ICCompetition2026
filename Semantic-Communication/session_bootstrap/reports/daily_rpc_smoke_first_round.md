# Daily Report

- 日期：2026-03-01
- 执行人：tianxing
- 今日唯一改动变量：switch execution entry to rpc first-round pipeline
- 实验模式：quick + full
- 目标模型与shape桶：example_model:64,128; smoke_demo:64; smoke_rpc_model:1x3x224x224
- target与线程配置：llvm/threads=4; smoke_target/threads=1; llvm -mtriple=aarch64-linux-gnu -mattr=+neon/threads=4
- 延迟对比（baseline -> current）：full_low_budget_hotspot_2026-03-01_01(full): 83.072ms -> 76.419ms (delta -6.653ms, 8.01%); full_low_budget_template(full): 48.240ms -> 38.317ms (delta -9.923ms, 20.57%); full_review_ok(full): 216.436ms -> 116.511ms (delta -99.925ms, 46.17%); full_rpc_smoke_first_round(full): 57.051ms -> 58.082ms (delta 1.031ms, -1.81%); full_smoke(full): 1232.974ms -> 421.020ms (delta -811.954ms, 65.85%); quick_review_fail(quick): status=failed_current, baseline=14.825, current=NA; quick_review_ok(quick): 259.293ms -> 114.102ms (delta -145.191ms, 55.99%); quick_rpc_smoke_first_round(quick): 813.226ms -> 413.209ms (delta -400.017ms, 49.19%); quick_smoke(quick): 4809.742ms -> 3610.203ms (delta -1199.539ms, 24.94%)
- 有效样本（baseline/current）：full_rpc_smoke_first_round(full): baseline=1, current=1; quick_review_fail(quick): baseline=1, current=0; quick_review_ok(quick): baseline=1, current=1; quick_rpc_smoke_first_round(quick): baseline=2, current=2; quick_smoke(quick): baseline=2, current=2
- 稳定性（复测中位数/方差）：quick_review_fail(quick): status=failed_current, var 0.000000 -> NA; quick_review_ok(quick): var 0.000000 -> 0.000000; quick_rpc_smoke_first_round(quick): var 0.251502 -> 0.289444; quick_smoke(quick): var 16937.981316 -> 16042.755600
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log
- 异常与处理：failed_reports=1; logs_with_error_keywords=2
- 结论：已聚合 9 份报告（quick=4, full=5）。
- 明日单一改动计划：replace smoke payload with real TVM RPC tune/eval command

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| full_low_budget_hotspot_2026-03-01_01 | full | example_model | llvm | 64,128 | success | 8.01 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md |
| full_low_budget_template | full | example_model | llvm | 64,128 | success | 20.57 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md |
| full_review_ok | full | smoke_demo | smoke_target | 64 | success | 46.17 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md |
| full_rpc_smoke_first_round | full | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | -1.81 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_smoke_first_round.md |
| full_smoke | full | smoke_demo | smoke_target | 64 | success | 65.85 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md |
| quick_review_fail | quick | smoke_demo | smoke_target | 64 | failed_current | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_fail.md |
| quick_review_ok | quick | smoke_demo | smoke_target | 64 | success | 55.99 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_ok.md |
| quick_rpc_smoke_first_round | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 49.19 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round.md |
| quick_smoke | quick | smoke_demo | smoke_target | 64 | success | 24.94 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_smoke.md |

## Log Snapshot

- 当日日志文件数：10
- 命中失败关键词日志数：2
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_review_ok.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md

## Metadata

- generated_at: 2026-03-01T13:18:09+08:00
- generated_by: summarize_to_daily.sh
