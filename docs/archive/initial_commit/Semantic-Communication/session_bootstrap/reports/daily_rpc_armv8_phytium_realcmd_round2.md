# Daily Report

- 日期：2026-03-01
- 执行人：tianxing
- 今日唯一改动变量：change only tvm_002.py snr: REMOTE_SNR_BASELINE=10 -> REMOTE_SNR_CURRENT=12 (batch fixed at 1)
- 实验模式：quick + full
- 目标模型与shape桶：example_model:64,128; smoke_demo:64; replace_with_model_name:1x3x224x224,1x3x256x256; jscc:1x3x224x224,1x3x256x256; smoke_rpc_model:1x3x224x224
- target与线程配置：llvm/threads=4; smoke_target/threads=1; llvm -mtriple=aarch64-linux-gnu -mattr=+neon/threads=4; llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc/threads=4
- 延迟对比（baseline -> current）：full_low_budget_hotspot_2026-03-01_01(full): 83.072ms -> 76.419ms (delta -6.653ms, 8.01%); full_low_budget_template(full): 48.240ms -> 38.317ms (delta -9.923ms, 20.57%); full_review_ok(full): 216.436ms -> 116.511ms (delta -99.925ms, 46.17%); full_rpc_armv8_lenovo_round1(full): 58.087ms -> 54.120ms (delta -3.967ms, 6.83%); full_rpc_armv8_phytium_realcmd_round1(full): status=failed_baseline, baseline=25.183, current=NA; full_rpc_armv8_phytium_round1(full): 801.478ms -> 1555.451ms (delta 753.973ms, -94.07%); full_rpc_armv8_phytium_realcmd_round1(full): 78160.686ms -> 77640.022ms (delta -520.664ms, 0.67%); full_rpc_armv8_phytium_realcmd_round1(full): 77247.983ms -> 111505.756ms (delta 34257.773ms, -44.35%); full_rpc_armv8_phytium_realcmd_round1(full): 82090.845ms -> 79369.808ms (delta -2721.037ms, 3.31%); full_rpc_armv8_phytium_realcmd_round1(full): 76949.930ms -> 75667.989ms (delta -1281.941ms, 1.67%); full_rpc_smoke_first_round(full): 57.051ms -> 58.082ms (delta 1.031ms, -1.81%); full_smoke(full): 1232.974ms -> 421.020ms (delta -811.954ms, 65.85%); quick_review_fail(quick): status=failed_current, baseline=14.825, current=NA; quick_review_ok(quick): 259.293ms -> 114.102ms (delta -145.191ms, 55.99%); quick_rpc_armv8_lenovo_round1(quick): 812.024ms -> 412.241ms (delta -399.783ms, 49.23%); quick_rpc_armv8_phytium_realcmd_round1(quick): 76457.014ms -> 78055.593ms (delta 1598.579ms, -2.09%); quick_rpc_armv8_phytium_round1(quick): 6494.468ms -> 1046.129ms (delta -5448.339ms, 83.89%); quick_rpc_smoke_first_round(quick): 813.226ms -> 413.209ms (delta -400.017ms, 49.19%); quick_smoke(quick): 4809.742ms -> 3610.203ms (delta -1199.539ms, 24.94%)
- 有效样本（baseline/current）：full_rpc_armv8_lenovo_round1(full): baseline=1, current=1; full_rpc_armv8_phytium_realcmd_round1(full): baseline=0, current=0; full_rpc_armv8_phytium_round1(full): baseline=1, current=1; full_rpc_armv8_phytium_realcmd_round1(full): baseline=1, current=1; full_rpc_smoke_first_round(full): baseline=1, current=1; quick_review_fail(quick): baseline=1, current=0; quick_review_ok(quick): baseline=1, current=1; quick_rpc_armv8_lenovo_round1(quick): baseline=2, current=2; quick_rpc_armv8_phytium_realcmd_round1(quick): baseline=1, current=1; quick_rpc_armv8_phytium_round1(quick): baseline=1, current=1; quick_rpc_smoke_first_round(quick): baseline=2, current=2; quick_smoke(quick): baseline=2, current=2
- 稳定性（复测中位数/方差）：quick_review_fail(quick): status=failed_current, var 0.000000 -> NA; quick_review_ok(quick): var 0.000000 -> 0.000000; quick_rpc_armv8_lenovo_round1(quick): var 0.091204 -> 0.152490; quick_rpc_armv8_phytium_realcmd_round1(quick): var 0.000000 -> 0.000000; quick_rpc_armv8_phytium_round1(quick): var 0.000000 -> 0.000000; quick_rpc_smoke_first_round(quick): var 0.251502 -> 0.289444; quick_smoke(quick): var 16937.981316 -> 16042.755600
- 产物路径（DB/日志/报告）：reports_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports; logs_dir=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs; artifacts=/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01_raw.csv; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log
- 异常与处理：failed_reports=2; logs_with_error_keywords=4
- 结论：已聚合 19 份报告（quick=7, full=12）。
- 明日单一改动计划：run SNR sweep with batch fixed at 1 (e.g., 8/10/12/14) and compare stability

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
| full_low_budget_hotspot_2026-03-01_01 | full | example_model | llvm | 64,128 | success | 8.01 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md |
| full_low_budget_template | full | example_model | llvm | 64,128 | success | 20.57 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md |
| full_review_ok | full | smoke_demo | smoke_target | 64 | success | 46.17 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md |
| full_rpc_armv8_lenovo_round1 | full | replace_with_model_name | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224,1x3x256x256 | success | 6.83 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_lenovo_round1.md |
| full_rpc_armv8_phytium_realcmd_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | failed_baseline | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_realcmd_round1.md |
| full_rpc_armv8_phytium_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224,1x3x256x256 | success | -94.07 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_round1.md |
| full_rpc_armv8_phytium_realcmd_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 0.67 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_snr10.md |
| full_rpc_armv8_phytium_realcmd_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | -44.35 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_snr12.md |
| full_rpc_armv8_phytium_realcmd_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 3.31 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_snr14.md |
| full_rpc_armv8_phytium_realcmd_round1 | full | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | 1.67 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_snr8.md |
| full_rpc_smoke_first_round | full | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | -1.81 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_smoke_first_round.md |
| full_smoke | full | smoke_demo | smoke_target | 64 | success | 65.85 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke.md |
| quick_review_fail | quick | smoke_demo | smoke_target | 64 | failed_current | NA | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_fail.md |
| quick_review_ok | quick | smoke_demo | smoke_target | 64 | success | 55.99 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_ok.md |
| quick_rpc_armv8_lenovo_round1 | quick | replace_with_model_name | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224,1x3x256x256 | success | 49.23 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_lenovo_round1.md |
| quick_rpc_armv8_phytium_realcmd_round1 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc | 1x3x224x224,1x3x256x256 | success | -2.09 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_phytium_realcmd_round1.md |
| quick_rpc_armv8_phytium_round1 | quick | jscc | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224,1x3x256x256 | success | 83.89 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_phytium_round1.md |
| quick_rpc_smoke_first_round | quick | smoke_rpc_model | llvm -mtriple=aarch64-linux-gnu -mattr=+neon | 1x3x224x224 | success | 49.19 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round.md |
| quick_smoke | quick | smoke_demo | smoke_target | 64 | success | 24.94 | /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_smoke.md |

## Log Snapshot

- 当日日志文件数：20
- 命中失败关键词日志数：4
- 日志路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_review_ok.log
- 报告路径样例：/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok.md

## Metadata

- generated_at: 2026-03-01T20:04:40+08:00
- generated_by: summarize_to_daily.sh
