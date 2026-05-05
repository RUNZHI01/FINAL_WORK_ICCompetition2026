# Hotspot Top Tasks

- generated_at: 2026-03-01T12:16:52+08:00
- source_baseline_csv: session_bootstrap/tmp/local_db/full_hotspot_runs/full_payload_baseline_20260301_113609.csv
- source_current_csv: session_bootstrap/tmp/local_db/full_hotspot_runs/full_payload_current_20260301_113609.csv
- ranking_rule: 按 baseline_avg_ms 降序（同任务取均值）
- hotspot_task_count: 3
- hotspot_tasks_csv: session_bootstrap/reports/hotspot_top_2026-03-01.csv
- hotspot_tasks_for_full: conv2d_nchw_1,dense_1,layernorm_1

## Ranked Tasks

| rank | task | baseline_avg_ms | current_avg_ms | delta_ms_current_minus_baseline | improvement_pct |
|---|---|---|---|---|---|
| 1 | conv2d_nchw_1 | 4.257 | 3.053 | -1.204 | 28.28 |
| 2 | dense_1 | 3.518 | 2.859 | -0.659 | 18.73 |
| 3 | layernorm_1 | 3.419 | 2.930 | -0.489 | 14.30 |
