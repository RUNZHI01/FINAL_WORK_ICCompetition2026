# 日报模板字段映射（RPC 闭环）

本表用于把 `templates/daily_report_template.md` 的字段直接映射到当前脚本产物，避免手工猜测。

| 日报字段 | 来源脚本/文件 | 取值说明 |
|---|---|---|
| 日期 | `scripts/summarize_to_daily.sh --date` | 默认当天，可显式传参。 |
| 执行人 | env: `DAILY_OWNER` | 未配置时回退当前用户。 |
| 今日唯一改动变量 | env: `DAILY_SINGLE_CHANGE` | 必须单变量。 |
| 实验模式 | `reports/*.md` 中 `mode` | 聚合为 `quick` / `full` / `quick + full`。 |
| 目标模型与shape桶 | `reports/*.md` 中 `model_name` + `shape_buckets` | 自动去重拼接。 |
| target与线程配置 | `reports/*.md` 中 `target` + `threads` | 自动去重拼接。 |
| 延迟对比（baseline -> current） | quick:`baseline_median_ms/current_median_ms`; full:`baseline_elapsed_ms/current_elapsed_ms` | `summarize_to_daily.sh` 自动计算并串联。 |
| 有效样本（baseline/current） | quick/full 报告中的 `baseline_count/current_count` | quick 来自复测成功样本数；full 成功为 1，失败为 0。 |
| 稳定性（复测中位数/方差） | quick 报告中的 `baseline_variance_ms2/current_variance_ms2` | full 默认不含方差，quick 为主。 |
| 产物路径（DB/日志/报告） | env: `TUNING_DB_DIR/LOG_DIR/REPORT_DIR` + 报告内 `log_file/raw_csv_file` | `summarize_to_daily.sh` 汇总样例路径。 |
| 异常与处理 | 报告状态 + 日志关键词扫描 | 统计 `failed` / `ERROR` 等关键词。 |
| 结论 | `summarize_to_daily.sh` 自动结论 | 按当日报告数量与失败数生成。 |
| 明日单一改动计划 | env: `DAILY_NEXT_CHANGE` | 与今日变量保持可归因。 |

## 快速检查命令

```bash
bash ./session_bootstrap/scripts/summarize_to_daily.sh --env ./session_bootstrap/config/rpc_armv8_smoke.env --date "$(date +%F)"
```
