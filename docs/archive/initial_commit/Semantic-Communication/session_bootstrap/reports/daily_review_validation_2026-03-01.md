# Daily Report

- 日期：2026-03-01
- 执行人：reviewer
- 今日唯一改动变量：validation
- 实验模式：quick + full
- 目标模型与shape桶：example_model:64,128; smoke_demo:64
- target与线程配置：llvm/threads=4; smoke_target/threads=1
- 延迟对比（baseline -> current）：full_low_budget_template(full): 48.240ms -> 38.317ms (delta -9.923ms, 20.57%); full_review_ok(full): 216.436ms -> 116.511ms (delta -99.925ms, 46.17%); full_smoke(full): 1232.974ms -> 421.020ms (delta -811.954ms, 65.85%); quick_review_ok(quick): 259.293ms -> 114.102ms (delta -145.191ms, 55.99%); quick_smoke(quick): 4809.742ms -> 3610.203ms (delta -1199.539ms, 24.94%)
- 稳定性（复测中位数/方差）：quick_review_ok(quick): var 0.000000 -> 0.000000; quick_smoke(quick): var 16937.981316 -> 16042.755600
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_review_ok.log
- 异常与处理：failed_reports=0; logs_with_error_keywords=1
- 结论：已聚合 5 份报告（quick=2, full=3）。
- 明日单一改动计划：none

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| full_low_budget_template | full | example_model | llvm | 64,128 | success | 20.57 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md |
| full_review_ok | full | smoke_demo | smoke_target | 64 | success | 46.17 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md |
| full_smoke | full | smoke_demo | smoke_target | 64 | success | 65.85 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md |
| quick_review_ok | quick | smoke_demo | smoke_target | 64 | success | 55.99 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_ok.md |
| quick_smoke | quick | smoke_demo | smoke_target | 64 | success | 24.94 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_smoke.md |

## Log Snapshot

- 当日日志文件数：6
- 命中失败关键词日志数：1
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_review_ok.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_smoke.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md

## Metadata

- generated_at: 2026-03-01T12:00:58+08:00
- generated_by: summarize_to_daily.sh
