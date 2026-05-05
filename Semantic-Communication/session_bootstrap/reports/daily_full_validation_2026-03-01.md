# Daily Report

- 日期：2026-03-01
- 执行人：tianxing
- 今日唯一改动变量：wire full to executable hotspot payload command
- 实验模式：quick + full
- 目标模型与shape桶：example_model:64,128; smoke_demo:64
- target与线程配置：llvm/threads=4; smoke_target/threads=1
- 延迟对比（baseline -> current）：full_low_budget_template(full): 48.240ms -> 38.317ms (delta -9.923ms, 20.57%); full_smoke(full): 1232.974ms -> 421.020ms (delta -811.954ms, 65.85%); quick_smoke(quick): 4809.742ms -> 3610.203ms (delta -1199.539ms, 24.94%)
- 稳定性（复测中位数/方差）：quick_smoke(quick): var 16937.981316 -> 16042.755600
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_smoke.log
- 异常与处理：未发现失败关键词。
- 结论：已聚合 3 份报告（quick=1, full=2）。
- 明日单一改动计划：replace dd payload with real TVM hotspot command

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| full_low_budget_template | full | example_model | llvm | 64,128 | success | 20.57 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md |
| full_smoke | full | smoke_demo | smoke_target | 64 | success | 65.85 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md |
| quick_smoke | quick | smoke_demo | smoke_target | 64 | success | 24.94 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_smoke.md |

## Log Snapshot

- 当日日志文件数：3
- 命中失败关键词日志数：0
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_smoke.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_smoke.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_smoke.md

## Metadata

- generated_at: 2026-03-01T11:36:20+08:00
- generated_by: summarize_to_daily.sh
