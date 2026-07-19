# 实验记录

- 实验ID：EXP-FULL-HOTSPOT-2026-03-01-01
- 日期时间：2026-03-01T12:19:05+08:00
- 负责人：tianxing
- 模式：full
- 目标task（热点编号）：conv2d_nchw_1, dense_1, layernorm_1
- 本轮唯一变量：full 输入任务集合改为锁定热点 Top3 列表
- 变量取值：FULL_HOTSPOT_TASKS=conv2d_nchw_1,dense_1,layernorm_1
- 固定条件（target/shape/线程/测量参数）：target=llvm; shape_buckets=64,128; threads=4; full_timeout_sec=120; trials_per_task=2; baseline_work_units=24; current_work_units=12
- 预期收益：在低预算下保持 current 小于 baseline，并完成热点限定链路验证
- 实际结果：full_low_budget_hotspot_2026-03-01_01 成功；baseline 83.072ms -> current 76.419ms，improvement 8.01%
- 是否复现：是（与前序热点模板 run 同方向，幅度较低）
- 失败样本信息（可选）：无
- 下一步：执行同热点列表二次 quick，验证 warm-start 命中率与时间变化

## 产物

- env：session_bootstrap/config/full_low_budget_hotspot_2026-03-01.env
- hotspot list：session_bootstrap/reports/hotspot_top_2026-03-01.md
- full report：session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01.md
- full log：session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log
