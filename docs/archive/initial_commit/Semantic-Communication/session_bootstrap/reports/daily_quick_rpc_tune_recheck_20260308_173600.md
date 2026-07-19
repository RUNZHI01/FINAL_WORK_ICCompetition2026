# Daily Report

- 日期：2026-03-08
- 执行人：tianxing
- 今日唯一改动变量：refresh Phytium-Pi target to generic+aarch64+neon+num-cores=4 and rebuild from existing DB
- 实验模式：quick
- 目标模型与shape桶：jscc:1x3x224x224,1x3x256x256
- target与线程配置：{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon","+crypto","+crc"],"num-cores":4}/threads=4; {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}/threads=4
- 延迟对比（baseline -> current）：quick_rpc_tune_20260306_190304(quick): status=failed_baseline, baseline=NA, current=NA; quick_rpc_tune_20260308_024940(quick): status=failed_baseline, baseline=NA, current=NA; quick_rpc_tune_20260308_031126(quick): status=failed_current, baseline=322134.557, current=483713.501; quick_rpc_tune_recheck_20260308_151301(quick): status=failed_current, baseline=322805.871, current=NA; quick_rpc_tune_recheck_20260308_162420(quick): status=failed_current, baseline=329030.068, current=NA; quick_rpc_tune_recheck_20260308_173600(quick): 304061.589ms -> 303992.103ms (delta -69.486ms, 0.02%); quick_rpc_tune_safe_recheck_20260308_165534(quick): 305742.841ms -> 304745.971ms (delta -996.870ms, 0.33%); quick_safe_smoke_20260308_1654(quick): 10387.873ms -> 10550.650ms (delta 162.777ms, -1.57%)
- 有效样本（baseline/current）：quick_rpc_tune_20260306_190304(quick): baseline=0, current=0; quick_rpc_tune_20260308_024940(quick): baseline=0, current=0; quick_rpc_tune_20260308_031126(quick): baseline=3, current=1; quick_rpc_tune_recheck_20260308_151301(quick): baseline=3, current=0; quick_rpc_tune_recheck_20260308_162420(quick): baseline=3, current=0; quick_rpc_tune_recheck_20260308_173600(quick): baseline=3, current=3; quick_rpc_tune_safe_recheck_20260308_165534(quick): baseline=3, current=3; quick_safe_smoke_20260308_1654(quick): baseline=1, current=1
- 稳定性（复测中位数/方差）：quick_rpc_tune_20260306_190304(quick): status=failed_baseline, var NA -> NA; quick_rpc_tune_20260308_024940(quick): status=failed_baseline, var NA -> NA; quick_rpc_tune_20260308_031126(quick): var 131625.339066 -> 0.000000; quick_rpc_tune_recheck_20260308_151301(quick): status=failed_current, var 25071209.353897 -> NA; quick_rpc_tune_recheck_20260308_162420(quick): status=failed_current, var 1480987.563965 -> NA; quick_rpc_tune_recheck_20260308_173600(quick): var 13850.115250 -> 688455.117310; quick_rpc_tune_safe_recheck_20260308_165534(quick): var 451651.830460 -> 28748.029144; quick_safe_smoke_20260308_1654(quick): var 0.000000 -> 0.000000
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260306_190304.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_tune_20260306_190304.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260306_190304_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260308_024940.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_tune_20260308_024940.log
- 异常与处理：failed_reports=5; logs_with_error_keywords=7; deduped_reports=0
- 结论：已聚合 8 份去重后报告（候选=8; quick=8, full=0）。
- 明日单一改动计划：rerun readiness/quick on live Phytium-Pi once SSH/network is available

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| quick_rpc_tune_20260306_190304 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon","+crypto","+crc"],"num-cores":4} | 1x3x224x224,1x3x256x256 | failed_baseline | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260306_190304.md |
| quick_rpc_tune_20260308_024940 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | failed_baseline | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260308_024940.md |
| quick_rpc_tune_20260308_031126 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | failed_current | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260308_031126.md |
| quick_rpc_tune_recheck_20260308_151301 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | failed_current | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_recheck_20260308_151301.md |
| quick_rpc_tune_recheck_20260308_162420 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | failed_current | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_recheck_20260308_162420.md |
| quick_rpc_tune_recheck_20260308_173600 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | success | 0.02 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_recheck_20260308_173600.md |
| quick_rpc_tune_safe_recheck_20260308_165534 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | success | 0.33 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_safe_recheck_20260308_165534.md |
| quick_safe_smoke_20260308_1654 | quick | jscc | {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4} | 1x3x224x224,1x3x256x256 | success | -1.57 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_safe_smoke_20260308_1654.md |

## Log Snapshot

- 当日日志文件数：17
- 命中失败关键词日志数：7
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/continue_hourly_main.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_legacy_parse_ok_20260308_1805.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_legacy_parse_ok_20260308_1807.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260306_190304.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260308_024940.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_20260308_031126.md

## Metadata

- generated_at: 2026-03-08T18:06:28+08:00
- generated_by: summarize_to_daily.sh
