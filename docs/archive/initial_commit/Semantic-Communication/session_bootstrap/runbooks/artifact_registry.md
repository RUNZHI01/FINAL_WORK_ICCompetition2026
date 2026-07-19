# 产物 / 脚本 / 路径索引（当前可信工程入口）

更新时间：`2026-03-18`
适用范围：飞腾派 current-safe / baseline 对比、增量调优、真实重建复现，以及 OpenAMP 控制面答辩收证

这份文档的目的很直接：把**当前最重要的产物、脚本、报告和路径**固定下来，后续要复现、汇报、继续优化时，不用再翻聊天记录。

---

## Judge Evidence Pack（2026-03-30）

核心入口：

- `session_bootstrap/runbooks/judge_evidence_workflow_2026-03-30.md`
- `session_bootstrap/scripts/build_quality_matrix_report.py`
- `session_bootstrap/scripts/build_snr_robustness_report.py`
- `session_bootstrap/scripts/build_judge_evidence_pack.py`
- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_latency.svg`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_quality.svg`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`
- `session_bootstrap/reports/defense_quick_reference_card_20260330_current_chunk4.md`
- `session_bootstrap/reports/judge_evidence_legacy_index_20260330.md`

补充说明：

- 这条线只服务于 judge-facing evidence / complementary materials，不处理 demo / admission 交付；
- 本地已经把 `quality / hotspot / resource / SNR` 结果统一整理成正式材料；
- 目前最新质量入口已升级到 `lpips_full`：`PyTorch vs TVM baseline/current` 与 `TVM baseline vs current` 三组都已有 SNR10 的远端 LPIPS 实测；
- 当前 judge-evidence 主线已基本闭环；若继续往下做，主要是把 profiling 从 `1 sample` 扩成多 sample 稳定性结论，而不是再补核心缺口。

---

## 0. big.LITTLE 异构大小核真机入口（2026-03-18）

核心入口：
- `session_bootstrap/scripts/run_big_little_first_real_attempt.sh`
- `session_bootstrap/reports/big_little_real_run_summary_20260318.md`
- `session_bootstrap/reports/big_little_compare_20260318_123300.md`
- `session_bootstrap/reports/big_little_compare_20260318_123300.json`
- `session_bootstrap/reports/big_little_compare_20260318_123300.serial.raw.log`
- `session_bootstrap/reports/big_little_compare_20260318_123300.pipeline.raw.log`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.json`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.raw.log`
- `session_bootstrap/reports/big_little_board_state_drift_20260318.md`
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/resource_profile_big_little_current_20260318_052922.md`
- `session_bootstrap/config/big_little_pipeline.current.bestcurrent_snr10.2026-03-18.phytium_pi.env`
- `session_bootstrap/reports/big_little_compare_20260318_095615.md`
- `session_bootstrap/reports/big_little_compare_20260318_095615.json`
- `session_bootstrap/reports/big_little_compare_20260318_095615.serial.raw.log`
- `session_bootstrap/reports/big_little_compare_20260318_095615.pipeline.raw.log`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_095811.md`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_095811.json`
- `session_bootstrap/reports/big_little_compare_20260318_051326.md`
- `session_bootstrap/reports/big_little_compare_20260318_053619.md`
- `session_bootstrap/reports/big_little_overnight_handoff_20260318.md`
- `session_bootstrap/runbooks/big_little_pipeline_runbook_2026-03-18.md`
- `session_bootstrap/scripts/big_little_topology_probe.py`
- `session_bootstrap/scripts/apply_big_little_topology_suggestion.py`
- `session_bootstrap/scripts/run_big_little_pipeline.sh`
- `session_bootstrap/scripts/run_big_little_compare.sh`
- `session_bootstrap/reports/big_little_topology_capture_20260318_0136.txt`
- `session_bootstrap/reports/big_little_topology_suggestion_20260318_0136.json`

补充说明：
- 这条线已经从“明早可执行”推进到“健康板态默认 apples-to-apples 真机 compare 已落盘”；
- `big_little_real_run_summary_20260318.md` 是当前最适合直接引用的一页摘要：它已经把“relative-vs-serial improvement”和“absolute-vs-historical-best status”拆开说清楚；
- `big_little_compare_20260318_123300.md` 是当前默认引用的健康板态 apples-to-apples compare：serial current median `231.522 ms/image`，pipeline current median `134.617 ms/image`，相对同轮 serial current 吞吐提升 `56.077%`；
- `big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md` 是与这次默认 compare 配套的 pipeline wrapper 报告：`processed_count=300`、`artifact_sha256_match=true`、`big_cores=[2]`、`little_cores=[0,1]`；
- 历史最佳 direct current e2e 参考仍然是 `inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`：current median `230.339 ms/image`、SHA `6f236b07...6dc1`、`SNR=10`；
- `big_little_board_state_drift_20260318.md` 现在是必须连带引用的复盘页：它把 same-day direct rerun 的 `347.375 -> 295.255 -> 239.233 ms/image` 恢复序列，以及 CPU online `0-2 -> 0-3` 的板态变化固定下来；
- 这意味着当前最重要的新结论是：**板态 / CPU online set 是 primary factor，不只是 artifact lineage**；
- `big_little_compare_20260318_095615.md` 与 `big_little_pipeline_bestcurrent_snr10_current_20260318_095811.md` 现保留为 degraded-board 时代的 apples-to-apples 证据：serial `344.721 ms/image`、pipeline `254.791 ms/image`、throughput uplift `35.298%`，但不再是默认 headline；
- `big_little_compare_20260318_051326.md` 和 `big_little_compare_20260318_053619.md` 现保留为更早两轮同日复现证据：`36.937%` / `36.54%` uplift，可作为稳定性佐证，但不再是默认 headline；
- `resource_profile_big_little_current_20260318_052922.md` 继续保留为同日 current pipeline 路径的板级资源证据：wall time `84s`、vmstat 平均 CPU `user/system/idle/wait = 53.812 / 2.706 / 43.435 / 0.129 %`、平均 runnable `2.165`、最小 free memory `217480 KB`；
- `big_little_overnight_handoff_20260318.md` 现保留为这次首跑前的短交接，同时在顶部补了真机结果回链；
- `run_big_little_first_real_attempt.sh` 现在会自动复制 runtime env、只读探测 topology、自动回填 BIG/LITTLE core 建议、再顺序跑 pipeline 与 compare；
- `big_little_pipeline.current.bestcurrent_snr10.2026-03-18.phytium_pi.env` 明确固定了这次 apples-to-apples compare 的 best-current artifact lineage、`SNR=10` 和 `big=[2] / little=[0,1]` 绑定；
- `big_little_topology_capture_20260318_0136.txt` / `big_little_topology_suggestion_20260318_0136.json` 现在主要用于保留 degraded-board 当时 `On-line CPU(s) list = 0-2` 的证据，而不是继续当默认板态假设。

## 1. OpenAMP 控制面答辩证据包（2026-03-15）

核心入口：
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_materials_index.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_four_act_runbook.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/defense_talk_outline.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/degraded_demo_plan.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md`
- `session_bootstrap/reports/openamp_demo_live_delivery_snapshot_20260317.md`
- `session_bootstrap/scripts/run_openamp_demo.sh`
- `session_bootstrap/demo/openamp_control_plane_demo/README.md`

补充说明：
- `openamp_demo_live_dualpath_status_20260317.md` 是 2026-03-17 这轮最近聊天上下文对应的正式留档，专门回答“8115 当前 live demo 到底是什么状态”：
  - current 已在 8115 上成功跑通；
  - baseline 也已通过 signed sideband 进入真机执行；
  - 两侧最近 live reconstruction 均完成 `300/300`；
  - `cool-har` 只是一次本地 probe 会话被外部 `SIGTERM`，不构成新的板端失败。
- `openamp_demo_dashboard_local_acceptance_20260317.md` 则补上了“这套最新状态已经被 dashboard 实际跑起来并通过本地 API 验收”的证据：`run_openamp_demo.sh --port 8092` 可正常启动，`/api/snapshot` 已正确暴露 `latest_live_status`（`8115`、current `300/300`、baseline `300/300`）。
- `openamp_demo_live_delivery_snapshot_20260317.md` 用一页把本轮两份核心报告、已接入入口、相关代码文件与提交链集中列出，适合作为后续直接 handoff / 接手入口。

关键结论：
- P0 最小板级控制闭环已落证：`STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT/HEARTBEAT_ACK`、wrapper-backed board smoke、`SAFE_STOP`、`JOB_DONE`
- P1 正式 FIT 最终状态：`FIT-01 PASS / FIT-02 PASS / FIT-03 PASS`
- `FIT-03` 历史明确保留了 pre-fix FAIL -> post-fix PASS：
  - pre-fix: `session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md`
  - post-fix: `session_bootstrap/reports/openamp_phase5_fit03_watchdog_success_2026-03-15.md`

---

## 1. 当前可信结论（先看这个）

### 1.1 payload 级推理：current 已显著优于 baseline

核心报告：
- `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/trusted_current_speedup_causal_chain_20260313.md`

关键结果：
- baseline median in the fresh formal validation: `1846.9 ms`
- current median in the fresh formal validation: `130.219 ms`
- improvement vs baseline in the fresh formal validation: `92.95%`
- delta vs previous trusted current payload median `131.343 ms`: `-1.124 ms`（约 `0.86%` 更快）
- current artifact SHA256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

### 1.2 真实端到端重建：current 已显著优于 baseline

核心报告：
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`

关键结果：
- baseline median: `1850.0 ms/image`
- current median: `230.339 ms/image`
- improvement: `87.55%`
- baseline/current count: `300`
- current artifact SHA256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- delta vs previous trusted current end-to-end median `234.219 ms/image`: `-3.880 ms/image`（约 `1.66%` 更快）
- 说明：
  - 这是当前仓库内最新、且已正式对齐当前 trusted current SHA 的真实端到端重建报告；
  - `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140.md` 现保留为上一代 trusted current SHA `65747fb3...b6377` 的历史参照；
  - `session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301.md` 现保留为更早上一代 trusted current SHA `1946...c644` 的历史参照。

### 1.3 hotspot -> topup -> chunk4 fresh current 的工程链路已经被验证

核心报告：
- `session_bootstrap/reports/trusted_current_speedup_causal_chain_20260313.md`
- `session_bootstrap/reports/phytium_speed_test_summary_20260313_162731.md`
- `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`

关键结果：
- trusted current 热点前 8 个 task 覆盖 tuned-stage weight 的 `80.247%`
- `split_topup15` 先把 trusted current 推到 SHA `65747fb3...b6377`，payload / e2e 分别推进到 `131.343 ms` / `234.219 ms/image`
- 随后的 fresh `chunk4` 继续把默认 trusted current 推到 SHA `6f236b07...6dc1`
- 这代 fresh current 的正式结论现在是：payload `130.219 ms`、真实端到端 `230.339 ms/image`

---

## 2. 当前可信 current 产物

### 2.1 本地产物（推荐基准 artifact）

- local optimized model:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- SHA256:
  - `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 产物说明：
  - 当前默认 trusted current 的规范入口使用 `chunk4` fresh 目录；
  - `chunk3` / `chunk4` 对应报告都落到了同一个 SHA `6f236b07...6dc1`，当前默认对外口径以 `chunk4` 正式验证报告为准；
  - 已完成：hotspot 提取 → warm-start continuation / topup → fresh current 继续推进 → 本地编译 → 远端上传 → payload / e2e 正式验证。

### 2.2 远端部署产物（飞腾派）

- remote archive root:
  - `/home/user/Downloads/jscc-test/jscc`
- remote current `.so`:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- remote tuning logs:
  - `/home/user/Downloads/jscc-test/jscc/tuning_logs`
- remote workload db:
  - `/home/user/Downloads/jscc-test/jscc/tuning_logs/database_workload.json`
- remote tuning record db:
  - `/home/user/Downloads/jscc-test/jscc/tuning_logs/database_tuning_record.json`

### 2.3 current 产物身份保护

用于 current-safe 复现时，优先使用：
- `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env`

其中应维护：
- `INFERENCE_CURRENT_EXPECTED_SHA256=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

原则：
- 只要远端 `.so` 有更新，就必须同步更新 expected SHA；
- 没有 SHA guard 的 current-safe benchmark，不应当视为最终可信结论。

---

## 3. 关键脚本：按用途找入口

### 3.1 登录 / 基础连接

- 登录飞腾派：
  - `session_bootstrap/scripts/connect_phytium_pi.sh`
- SSH 包装：
  - `session_bootstrap/scripts/ssh_with_password.sh`

### 3.2 current-safe 复现与调优

- baseline-seeded rebuild-only current：
  - `session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh`
- baseline-seeded warm-start current 增量调优：
  - `session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh`
- baseline-style payload-symmetric rebuild-only current：
  - `session_bootstrap/scripts/run_phytium_baseline_style_current_rebuild.sh`
- current-safe 双 target 对比：
  - `session_bootstrap/scripts/run_phytium_current_safe_target_compare.sh`

### 3.3 benchmark / 推理验证

- payload 级对比：
  - `session_bootstrap/scripts/run_inference_benchmark.sh`
- current-safe payload runner：
  - `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`
- legacy baseline runner：
  - `session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh`
- 真实端到端 current runner：
  - `session_bootstrap/scripts/run_remote_current_real_reconstruction.sh`
- 真实端到端 Python 入口：
  - `session_bootstrap/scripts/current_real_reconstruction.py`

### 3.4 MetaSchedule / RPC 基础设施

- RPC tune 主入口：
  - `session_bootstrap/scripts/rpc_tune.py`
- 一键编排 tune + deploy + validate：
  - `session_bootstrap/scripts/run_rpc_tune.sh`
- RPC 服务管理：
  - `session_bootstrap/scripts/manage_rpc_services.sh`
- readiness 检查：
  - `session_bootstrap/scripts/check_rpc_readiness.sh`
- 热点 task 提取：
  - `session_bootstrap/scripts/extract_hotspot_tasks.py`
- hotspot 微基准：
  - `session_bootstrap/scripts/run_hotspot_micro_benchmark.sh`

---

## 4. 关键 env / 配置文件

### 4.1 当前推荐 current-safe 推理 env

- `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env`

用途：
- safe runtime current 推理
- current SHA guard
- one-shot / incremental 产物验证

### 4.2 当前推荐 rebuild-only env

- `session_bootstrap/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`

用途：
- baseline-seeded rebuild-only current 基线
- 推荐 target：`cortex-a72 + neon`

### 4.3 当前推荐 incremental env

- `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`

用途：
- 非零预算 current 增量调优
- warm-start 复用已有 tuning DB

### 4.4 payload-symmetric fair compare env

- `session_bootstrap/config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env`

用途：
- 避免 legacy/current mixed 路径
- 用更公平的 payload runner 比较 current rebuild-only / incremental

### 4.5 第一轮真实 RPC tune 拓扑参考 env

- `session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env`

用途：
- 远端 tracker + 远端 runner + 本地 builder/orchestrator

---

## 5. 关键报告：按问题找证据

| 你想回答的问题 | 看哪个报告 |
|---|---|
| 新 trusted current 是否真的快过 baseline？ | `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| 为什么 2026-03-13 的 trusted current 比上一版更快？ | `session_bootstrap/reports/trusted_current_speedup_causal_chain_20260313.md` |
| current 的真实端到端重建是否也更快？ | `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| big.LITTLE 在健康板态、best-current / `SNR=10` 真机设置下，是否比同轮 serial current 更好？ | `session_bootstrap/reports/big_little_compare_20260318_123300.md` |
| big.LITTLE 现在是否已经超过 current 历史最佳绝对 e2e？ | `session_bootstrap/reports/big_little_real_run_summary_20260318.md` / `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| 为什么同 artifact lineage / 同 `SNR=10` 的真机结果会从 `347.375` 恢复到 `239.233 ms/image`？ | `session_bootstrap/reports/big_little_board_state_drift_20260318.md` |
| 早先 incremental 是否已经优于 rebuild-only？ | `session_bootstrap/reports/current_scheme_b_compare_20260311_195303.md` |
| 2026-03-11 的第一轮 current incremental 突破总结是什么？ | `session_bootstrap/reports/phytium_current_incremental_breakthrough_20260311.md` |
| 当前 target 选择为什么倾向 cortex-a72 + neon？ | `session_bootstrap/reports/phytium_current_target_comparison_safe_runtime_20260310.md` |
| Python 入口为什么切到 tvm310_safe / Python 3.10？ | `session_bootstrap/reports/phytium_tvm24_python310_migration_2026-03-08.md` |
| baseline/current artifact 路径和 guard 语义怎么演化的？ | `session_bootstrap/reports/inference_currentsafe_artifact_guard_handoff_20260311.md` |

---

## 6. 典型复现路径（最常用）

### 6.1 只验证当前 trusted current artifact 是否还稳定

```bash
bash session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
```

你应该重点检查：
- `current_artifact_sha256_match`
- `current_run_median_ms`
- `current_run_variance_ms2`
- 当前 trusted SHA 参考值：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 当前 payload 中位时间参考带：`~130 ms`

### 6.2 从 rebuild-only 重新建立 current 基线

```bash
bash session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh
```

### 6.3 继续做 current 增量调优

```bash
bash session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh
```

### 6.4 跑真实端到端重建对比

```bash
bash session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
```

---

## 7. 路径管理约定

### 7.1 本地

- 脚本：`session_bootstrap/scripts/`
- 配置：`session_bootstrap/config/`
- 报告：`session_bootstrap/reports/`
- 日志：`session_bootstrap/logs/`
- 临时编译产物：`session_bootstrap/tmp/<report_id>/`

### 7.2 远端飞腾派

- 项目根：`/home/user/Downloads/jscc-test/jscc`
- current archive：`/home/user/Downloads/jscc-test/jscc/tvm_tune_logs`
- baseline/legacy 路径：沿 `tvm_002.py` / compat runner 既有目录约定，不与 current-safe archive 混写

### 7.3 命名规则建议

- 新报告：`<主题>_<YYYYMMDD_HHMMSS>.md`
- 新 env 快照：`session_bootstrap/tmp/<run_id>.env`
- 新 current 产物目录：`session_bootstrap/tmp/<report_id>/`
- 新 trusted artifact：必须同步记录 `.so path + SHA256 + 对应报告`

---

## 8. 下一步优化该从哪里继续

最值得继续投入的顺序：

1. **先稳住当前 trusted SHA**
   - 对 `6f236...6dc1` 再做 2–3 次 payload benchmark 复跑
   - 确认 `~130 ms` 延迟带稳定，不是偶然波动
2. **把新的真实端到端正式结论同步到对外材料**
   - 当前 latest real reconstruction 正式报告已更新为 `1850.0 -> 230.339 ms/image`
   - 后续若再复跑，应视为稳定性验证，而不是“补齐缺失 end-to-end 证据”
3. **继续做 warm-start incremental**
   - 在同一条 DB 链上把预算从 `500 -> 1000 -> 2000`
   - 观察边际收益是否还显著
4. **做热点 task 定位和定向预算投放**
   - 用 `extract_hotspot_tasks.py` 导出 task 权重
   - 如果总提升趋缓，就把预算从“全局均摊”转向“热点集中”
5. **分离 payload 优化与端到端优化**
   - payload 已经到 `130 ms` 量级
   - 端到端最新正式结论已更新到 `230 ms/image` 量级，中间仍有前后处理、I/O、图片读写和 pipeline 开销可挖
6. **若 MetaSchedule 边际收益变平，再转 INT8 / 模型级优化**
   - 量化、算子融合、结构裁剪会比继续硬堆搜索预算更划算

更详细的优化计划见：
- `session_bootstrap/runbooks/optimization_roadmap.md`

---

## 9. 维护规则

每当出现以下任一情况，必须同步更新这份索引：
- trusted current artifact SHA 变了；
- 推荐 env 变了；
- 复现主入口脚本变了；
- 新结论取代了旧 benchmark；
- 远端 archive 路径变了。
