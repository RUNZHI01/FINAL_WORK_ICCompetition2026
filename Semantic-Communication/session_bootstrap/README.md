# Session Bootstrap（会话执行脚手架）

## 目的
为 TVM MetaSchedule 每日推进提供最小但完整的基础设施：任务管理、日志落盘、实验记录、日报输出。

## 目录约定

- `scripts/`：执行脚本（`run_quick.sh`、`run_full_placeholder.sh`、`run_hotspot_micro_benchmark.sh`、`summarize_to_daily.sh`、`check_rpc_readiness.sh`、`rpc_print_cmd_templates.sh`、`run_rpc_first_round.sh`、`rpc_tune.py`、`manage_rpc_services.sh`、`run_rpc_tune.sh`、`connect_phytium_pi.sh`、`run_phytium_baseline_style_current_rebuild.sh`）。
- `docs/`：持续维护的设计文档（协议、架构、长期方案）。
- `templates/`：统一模板（日报、实验记录）。  
- `logs/`：运行日志（按日期或执行ID分文件）。  
- `reports/`：结构化结果输出（对比表、结论）。  
- `config/local.example`：本机配置模板（推荐复制为 `config/local.env`）。  
- `config/rpc_armv8.example.env`：真机 RPC 配置模板。  
- `config/rpc_armv8_smoke.env`：RPC 闭环离线模拟配置。  
- `config/rpc_armv8.phytium_rpc_tune.env`：RPC Tune 配置模板（笔记本 builder + 飞腾派 runner）。  
- `config/phytium_pi_login.example.env`：飞腾派登录模板（默认 `user@100.121.87.73:22`，密码字段可留空）。  
- `runbooks/rpc_first_round_runbook.md`：首轮真机 RPC 闭环步骤手册。  
- `runbooks/artifact_registry.md`：当前可信产物 / 脚本 / 路径索引。  
- `runbooks/optimization_roadmap.md`：优化路线图（当前状态、下一轮重点、止损与转向）。  
- `tasks/backlog.md`：待办池与优先级列表。

## 当前可信成果入口（2026-03-18）

优先看下面这些：

| 目的 | 路径 |
|---|---|
| 当前成果 / 脚本 / 路径总索引 | `runbooks/artifact_registry.md` |
| 评委补证工作流 | `runbooks/judge_evidence_workflow_2026-03-30.md` |
| 评委技术证据总包（latest） | `reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md` |
| 正式质量报告（PSNR / SSIM / LPIPS，latest） | `reports/judge_quality_formal_report_20260330_lpips_full.md` |
| 多 SNR 鲁棒性摘要（latest） | `reports/judge_snr_robustness_20260330_current_chunk4.md` |
| trusted current payload 正式结论 | `reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| trusted current 真实端到端重建正式结论 | `reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| USRP latent 数据面方案（审查版） | `docs/design_usrp_latent_transport.md` |
| 下一轮性能优化执行清单 | `runbooks/next_round_optimization_checklist.md` |
| big.LITTLE 首次真机一键入口 | `scripts/run_big_little_first_real_attempt.sh` |
| big.LITTLE 真机结论摘要（推荐入口） | `reports/big_little_real_run_summary_20260318.md` |
| big.LITTLE 首选 apples-to-apples compare | `reports/big_little_compare_20260318_123300.md` |
| big.LITTLE 配套 pipeline wrapper 报告 | `reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md` |
| big.LITTLE 板态漂移复盘 | `reports/big_little_board_state_drift_20260318.md` |
| big.LITTLE 历史最佳 current e2e 参考 | `reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| big.LITTLE 首轮资源 profiling（支持性证据） | `reports/resource_profile_big_little_current_20260318_052922.md` |
| big.LITTLE 首跑前交接（历史） | `reports/big_little_overnight_handoff_20260318.md` |
| big.LITTLE 异构流水线 runbook | `runbooks/big_little_pipeline_runbook_2026-03-18.md` |
| 后续性能优化路线 | `runbooks/optimization_roadmap.md` |

### 3/31–4/2 TVM 算子优化结果

3/31已围绕runtime hotspot建成多算子post-db scheduled-form线并闭环；仅留transpose1 v7(-1.97%)、variance4 v18(-0.99%)。近6次尝试连退，项目已暂停手写优化，转向Demo/OpenAMP/judge-facing。

- `session_bootstrap/reports/handwritten_operator_materials_archive_20260331.md`
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- `session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- `session_bootstrap/reports/variance4_v18_remote_benchmark_20260403_0239.md`
- `session_bootstrap/reports/handwritten_optimization_status_summary_20260403.md`
- `session_bootstrap/reports/project_speedup_rerank_after_mean4_v2_regression_20260403.md`
- `session_bootstrap/reports/handwritten_optimization_success_pattern_analysis_20260403.md`

## Judge Evidence Workflow（2026-03-30）

如果当前目标是补评委追问证据，而不是继续做 demo / admission 交付，默认走下面这条线：

1. `python3 ./scripts/build_quality_matrix_report.py`
2. `python3 ./scripts/build_snr_robustness_report.py`
3. `python3 ./scripts/build_judge_evidence_pack.py`

推荐直接先看：

- `runbooks/judge_evidence_workflow_2026-03-30.md`
- `reports/judge_quality_formal_report_20260330_lpips_full.md`
- `reports/judge_snr_robustness_20260330_current_chunk4.md`
- `reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`
- `reports/defense_quick_reference_card_20260330_current_chunk4.md`

说明：

- 这套 workflow 只整理本地已有结果，不自动发起任何 SSH / 远端脚本。
- 对仍然必须上板的步骤，例如 `quality-vs-SNR` 和 profiler-enabled runtime 验证，runbook 里只保留手工命令。

### 飞腾杯冲奖救援文档（2026-03-19）

如果当前目标是把既有工程结果重构成答辩可用的飞腾系统叙事，优先看下面这些：

- `reports/award_rescue_metric_truth_table_20260319.md`
- `reports/award_rescue_execution_checklist_20260319.md`
- `reports/defense_deck_outline_20260319.md`
- `reports/defense_talk_track_5min_20260320.md`
- `reports/defense_talk_track_2min_20260320.md`
- `reports/defense_demo_operator_card_20260320.md`
- `reports/project_reframing_for_feiteng_cup_20260319.md`

## OpenAMP 控制面证据入口（2026-03-15）

如果当前目标是答辩 / 演示 OpenAMP 控制面，而不是继续做 TVM benchmark，优先看下面这些：

| 目的 | 路径 |
|---|---|
| OpenAMP 证据包索引 | `reports/openamp_control_plane_evidence_package_20260315/README.md` |
| OpenAMP demo / 答辩材料索引 | `reports/openamp_control_plane_evidence_package_20260315/demo_materials_index.md` |
| OpenAMP demo 最新 live 双路径状态（2026-03-17） | `reports/openamp_demo_live_dualpath_status_20260317.md` |
| OpenAMP demo dashboard 本地启动验收（2026-03-17） | `reports/openamp_demo_dashboard_local_acceptance_20260317.md` |
| OpenAMP demo 最终交付快照（2026-03-17） | `reports/openamp_demo_live_delivery_snapshot_20260317.md` |
| OpenAMP demo 交接清单 / handoff manifest（M10） | `reports/openamp_demo_handoff_manifest_m10_20260319.md` |
| OpenAMP demo 最终交付索引（M11） | `reports/openamp_demo_delivery_index_m11_20260319.md` |
| OpenAMP demo 视频脚本口径同步（2026-04-03） | `reports/openamp_demo_video_script_alignment_2026-04-03.md` |
| OpenAMP demo 首屏验收口径说明（2026-04-03） | `reports/openamp_demo_topline_acceptance_note_2026-04-03.md` |
| OpenAMP demo presentation-day 核对清单（2026-04-03） | `reports/openamp_demo_presentation_day_checklist_2026-04-03.md` |
| OpenAMP demo 彩排结果回填 / GO-NO-GO 模板（2026-04-03） | `reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| OpenAMP demo 本地启动健康检查（2026-04-03） | `reports/openamp_demo_local_launch_healthcheck_2026-04-03.md` |
| OpenAMP demo 文档收尾总览（2026-04-03） | `reports/openamp_demo_docs_closure_summary_2026-04-03.md` |
| OpenAMP demo 任务完成判定矩阵（2026-04-03） | `reports/openamp_demo_task_completion_gate_matrix_2026-04-03.md` |
| 项目双层口径 / 双层主叙事正式说明（2026-04-03） | `reports/project_dual_layer_narrative_and_wording_system_2026-04-03.md` |
| 当前正式发布基线 + 历史优化谱系总览（2026-04-03） | `reports/project_release_baseline_and_optimization_lineage_2026-04-03.md` |
| 飞腾平台表述策略正式说明（2026-04-03） | `reports/phytium_platform_wording_strategy_2026-04-03.md` |
| 文档冻结后项目下一步真实 blocker / 优先级说明（2026-04-03） | `reports/project_next_real_blockers_after_docs_freeze_2026-04-03.md` |
| P2 后置差异化 / 暂缓 / 备线策略说明（2026-04-03） | `reports/post_closure_differentiator_gating_policy_2026-04-03.md` |
| OpenAMP 剩余协议 / FIT 缺口执行计划（2026-04-03） | `reports/openamp_remaining_protocol_fit_runplan_2026-04-03.md` |
| `TC-002/010` 答辩边界说明（2026-04-03） | `reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md` |
| 集成 OpenAMP demo dashboard 启动器 | `scripts/run_openamp_demo.sh` |
| cockpit_native 原生座舱答辩讲稿 | `runbooks/cockpit_native_demo_talk_track_2026-03-24.md` |
| cockpit_native demo packet 索引 | `runbooks/cockpit_native_demo_packet_index_2026-03-24.md` |
| cockpit_native 一键彩排脚本 | `scripts/run_cockpit_native_demo_rehearsal.sh` |
| cockpit_native GO / NO-GO 摘要 | `scripts/print_cockpit_native_go_no_go.sh` |
| cockpit_native 交付包构建脚本 | `scripts/build_cockpit_native_demo_packet.sh` |
| OpenAMP demo 软件说明 | `demo/openamp_control_plane_demo/README.md` |
| 只读板级状态探针 | `scripts/probe_openamp_board_status.py` |
| 四幕演示 runbook | `reports/openamp_control_plane_evidence_package_20260315/demo_four_act_runbook.md` |
| 答辩讲稿 / 页结构提纲 | `reports/openamp_control_plane_evidence_package_20260315/defense_talk_outline.md` |
| live 不稳时的降级方案 | `reports/openamp_control_plane_evidence_package_20260315/degraded_demo_plan.md` |
| OpenAMP 总报告 | `reports/openamp_control_plane_evidence_package_20260315/summary_report.md` |

### 当前仍真实未完成的主项（2026-04-03）

如果你只想知道“现在项目还真差什么”，优先看这几类：

1. **Demo 真实彩排 / UI / operator flow 回填**
   - 四幕 Demo
   - 首屏字段稳定露出
   - 第三幕只出现两条正式口径
   - 三个 fault 按钮是否在最终 build 中形成诚实的 replay/live 体验
   - 先跑：`bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness`
   - 若只差一次运行时 password：`bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness-prompt-password`
   - 准备继续 live 时：`bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password`
   - 若希望启动时就顺手做一次只读探板：`bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password-probe-startup`
   - 若希望“一次启动 + 抓三口 + 自动关停”并把原始 JSON 落盘：`bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password`
   - 若希望同一轮里也主动触发 fresh `/api/probe-board`：`bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password --post-probe-board`
   - 若希望这条 fresh probe 在失败时直接给出非零退出码（便于自动化/严格检查）：`bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password --strict-probe-board`
   - 若希望直接验证 startup probe 路径但保持诚实 capture：优先用上一条 helper，而不是手工起服务再 curl
   - 当前这条 helper 已真实跑通，但抓到的仍是 `保存的只读 SSH 探板`；随后对 `/api/probe-board` 的 fresh probe 也已真实触发，并如实返回 `SSH 认证失败`（strict 模式下也会给出非零退出码），说明当前主 blocker 已进一步收窄为“真实可用 SSH 凭据”，而不是 endpoint/launcher 缺失
   - 如需直接脚本输出：`python3 ./session_bootstrap/scripts/check_openamp_demo_session_readiness.py --format text`
   - 入口：`reports/openamp_demo_presentation_day_checklist_2026-04-03.md`、`reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`、`reports/openamp_demo_local_launch_healthcheck_2026-04-03.md`
2. **OpenAMP 剩余真机协议 / FIT 缺口**
   - `FIT-04/05`
   - `TC-007/008/009/010`
   - 入口：`reports/openamp_remaining_protocol_fit_runplan_2026-04-03.md`
3. **P2 仍未做的后置差异化项**
   - 跨框架对比：TVM vs MNN vs NCNN / ORT
   - TVM hotspot 定向深搜
   - 手写 TIR 等更后置扩展

说明：big.LITTLE、双层口径、发布基线谱系、平台表述策略、Demo 文档链等定义层/接入层事项，当前都已完成或已 docs-frozen，不再是主要 blocker。对 Demo 线来说，launcher 级 readiness / prompt-password 入口也已具备；后续主 blocker 更偏向真实板侧交互与彩排回填，而不是本地会话字段无法注入。
| OpenAMP 统一 coverage matrix / FIT summary | `reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md` |
| FIT-02 历史 `batch=4` 故障正式案例卡（2026-04-03） | `reports/openamp_fit02_batch_contract_case_card_2026-04-03.md` |
| `TC-002/010` 答辩口径拆分说明（2026-04-03） | `reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md` |
| 历史时间线真相源 | `PROGRESS_LOG.md` |

如果你只想知道“现在应该复现哪条线”，默认优先：
- current trusted artifact：`tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- trusted SHA256：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- current 历史最佳 e2e 参考：`reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- big.LITTLE 首选 apples-to-apples compare：`reports/big_little_compare_20260318_123300.md`
- big.LITTLE 板态漂移复盘：`reports/big_little_board_state_drift_20260318.md`
- 推荐验证入口：`scripts/run_inference_benchmark.sh` + `config/inference_tvm310_safe.2026-03-10.phytium_pi.env`

如果当前目标是直接演示 OpenAMP 控制面，优先执行：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

如需把只读 SSH 板级状态探针也接进 dashboard：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --probe-env ./session_bootstrap/config/phytium_pi_login.env
```

## 飞腾派登录固化

最小用法：

1. 复制模板并按需填写密码（可留空）：
   `cp ./session_bootstrap/config/phytium_pi_login.example.env ./session_bootstrap/config/phytium_pi_login.env`
2. 进入交互 shell：
   `bash ./session_bootstrap/scripts/connect_phytium_pi.sh --env ./session_bootstrap/config/phytium_pi_login.env`
3. 执行远端命令：
   `bash ./session_bootstrap/scripts/connect_phytium_pi.sh --env ./session_bootstrap/config/phytium_pi_login.env -- "hostname && whoami"`

说明：
- 不传 `--env` 时，脚本默认连接 `user@100.121.87.73:22`。
- 若 `PHYTIUM_PI_PASSWORD` 已配置且系统存在 `sshpass`，脚本可非交互登录；否则走普通 `ssh` 交互输入密码。

## 如何推进（每晚标准动作）

1. 复制 `config/local.example` 为本机配置并填入路径/设备信息。  
2. 在 `tasks/backlog.md` 标注今晚唯一改动变量。  
3. 运行 `scripts/run_quick.sh --env ./config/local.env` 验证 quick 链路和落盘。  
4. 如 quick 成功，运行 `scripts/run_full_placeholder.sh --env ./config/local.env` 进行 full 骨架夜跑。  
5. 使用 `templates/experiment_record_template.md` 记录实验参数。  
6. 运行 `scripts/summarize_to_daily.sh --env ./config/local.env` 生成日报草稿，再按模板补充结论。

## Quick 最小闭环（当前可执行）

1. 基于样例生成本机配置：`cp config/local.example config/local.env`。  
2. 将 `config/local.env` 中 `QUICK_BASELINE_CMD` 与 `QUICK_CURRENT_CMD` 替换为真实命令。  
3. 运行：`bash scripts/run_quick.sh --env ./config/local.env`。  
4. 检查产物：`logs/<execution_id>.log`、`reports/<execution_id>.md`、`reports/<execution_id>_raw.csv`。  

如需先做脚手架级 smoke 验证（不依赖 TVM），可直接运行：  
`bash scripts/run_quick.sh --env ./config/quick_smoke.env`

说明：
- quick 任一步骤失败会输出失败状态报告（`status=failed_baseline/failed_current`），并保留日志与 raw csv。
- 远端 `run_remote_tvm_payload.sh` 在 quick 模式下默认使用 `REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY=fresh-process`，避免对大体积 Relax/VM 产物进行同进程 repeated `load_module()` 导致板子失稳。
- 如需回退旧行为，可显式设置 `REMOTE_PAYLOAD_QUICK_LOAD_STRATEGY=same-process`（不推荐用于 current/current-like 产物）。
- 兼容入口：`run_quick_placeholder.sh` 已转发到 `run_quick.sh`。

### 独立安全推理基准（Inference Benchmark）

当你需要验证“真实 one-shot load + VM init + inference run”而不是 quick 的 load/probe 门禁时，可执行：

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh \
  --env ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env
```

说明：
- 默认通过 `run_remote_tvm_inference_payload.sh` 在远端执行：`load_module()` 一次、`relax.VirtualMachine(...)` 一次、warmup 若干次、正式推理若干次。
- 默认比较 `REMOTE_TVM_PRIMARY_DIR`（baseline）和 `REMOTE_TVM_JSCC_BASE_DIR`（current）；也可用 `INFERENCE_BASELINE_ARCHIVE` / `INFERENCE_CURRENT_ARCHIVE` 覆盖。
- 常用变量：`INFERENCE_REPEAT`、`INFERENCE_WARMUP_RUNS`、`INFERENCE_TIMEOUT_SEC`、`INFERENCE_ENTRY`。
- current-safe 路径现在支持 `INFERENCE_CURRENT_EXPECTED_SHA256`（或更通用的 `INFERENCE_EXPECTED_SHA256`）做远端 `optimized_model.so` 身份校验；建议在飞腾派 current-safe benchmark / smoke 中始终带上它，避免远端 artifact 漂移后静默跑偏。
- `run_remote_tvm_inference_payload.sh` 的 JSON payload 现在会显式输出 `artifact_path`、`artifact_sha256`、`artifact_sha256_expected`、`artifact_sha256_match`；`run_inference_benchmark.sh` 会把这些字段同步写进日志和最终 report。
- `run_inference_benchmark.sh` 现在既能解析 JSON payload，也能解析 legacy `tvm_002.py` 风格日志，例如：`批量推理时间（1 个样本）: 0.1129 秒`。
- 因此 baseline 不是 Relax VM artifact 时，可以显式覆盖 `INFERENCE_BASELINE_CMD`，例如复用旧的 realcmd：

### 飞腾派 baseline-style current rebuild-only 一键复现

当你要用**更公平的 baseline-style payload 语义**来重建并验证 current（避免 legacy/current mixed 路径）时，可直接执行：

```bash
bash ./session_bootstrap/scripts/run_phytium_baseline_style_current_rebuild.sh
```

说明：
- 默认会读取：
  - `config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`
  - `config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env`
- 语义：本地 rebuild current `.so` -> 上传到飞腾派 current archive -> 通过 `run_remote_tvm_inference_payload.sh --variant current` 跑 payload-symmetric inference -> 保存 summary。
- wrapper 会强制校验 `INFERENCE_BASELINE_CMD` / `INFERENCE_CURRENT_CMD` 都指向 payload runner；如果 inference env 还在走 `run_remote_legacy_tvm_compat.sh`，会直接报错，避免脚本语义把 current 跑慢。
- 该入口只接受 rebuild-only env（`TUNE_TOTAL_TRIALS=0`）；如需 nonzero-budget warm-start 增量调优，继续使用 `run_phytium_baseline_seeded_warm_start_current_incremental.sh`。
- 默认 report/log 前缀是 `phytium_baseline_style_current_rebuild_*`；常用覆盖项仍包括 `--report-id`、`--repeat`、`--warmup-runs`、`--target`、`--remote-archive-dir`、`--upload-db`。

### 飞腾派 baseline-seeded current-safe rebuild-only 一键复现

当你要复现**当前已验证的 baseline-seeded warm-start current rebuild-only + safe runtime**路径（只做 current，不碰 baseline/compat）时，可直接执行：

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh
```

说明：
- 默认会读取：
  - `config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`
  - `config/inference_tvm310_safe.2026-03-10.phytium_pi.env`
- 默认使用推荐 target：`{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}`
- `config/inference_tvm310_safe.2026-03-10.phytium_pi.env` 现在默认已写入 `INFERENCE_CURRENT_EXPECTED_SHA256`，用于保护飞腾派 current-safe 远端 artifact 身份；如果你 intentional deploy 了新的 current-safe `.so`，先更新 SHA 再跑。
- 语义：复用历史 tuning DB，按 `total_trials=0` 做 rebuild-only warm-start current 基线，不是独立 fresh search line。
- 执行顺序：本地 rebuild current `.so` -> 上传到飞腾派 current archive -> 远端 safe runtime one-shot inference -> 保存 summary
- 默认输出：
  - `session_bootstrap/tmp/<report_id>/optimized_model.so`
  - `session_bootstrap/reports/<report_id>.md`
  - `session_bootstrap/reports/<report_id>.json`
- summary 现在会显式落 `total_trials`、`runner`、`search_mode`，避免把这条 rebuild-only 路线误写成“真正独立 current”。
- 这个入口保留的是既有 current-safe wrapper 语义；如果你需要 payload-symmetric 的 fair baseline-style current 重建入口，优先用 `run_phytium_baseline_style_current_rebuild.sh`。
- 如需显式比较其他 **baseline-seeded current + safe runtime** target，可通过 `--target '<json>'` 覆盖。

### 飞腾派 baseline-seeded warm-start current 增量调优

当你要进入**下一阶段的真实 nonzero-budget current 增量调优**时，直接执行：

```bash
bash ./session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh
```

说明：
- 默认会读取：
  - `config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`
  - `config/inference_tvm310_safe.2026-03-10.phytium_pi.env`
- 语义：复用同一份历史 tuning DB，但要求 `TUNE_RUNNER=rpc` 且 `TUNE_TOTAL_TRIALS>0`，然后沿用 current-safe 上传与 safe runtime 验证路径。
- 因为 inference env 已带 `INFERENCE_CURRENT_EXPECTED_SHA256`，这个入口在最终 safe runtime 验证时也会受 artifact SHA guard 保护；若换了新的 current-safe `.so`，别忘了同步更新 expected SHA。
- 默认增量预算来自 env（当前为 `500` trials），也可通过 `--total-trials <n>` 覆盖。
- wrapper 会先尝试拉起 RPC 服务并执行 readiness；如你已确认服务在线，可用 `--skip-services` / `--skip-readiness` 缩短流程。
- 该入口会把新的 `.so` 和更新后的 `tuning_logs` 一并部署到 remote current archive，再跑 safe runtime inference。
- 仓库内没有伪造任何 Pi 结果；在真正连通 RPC/SSH 之前，这个入口只提供脚本和文档准备。

### 飞腾派 baseline-seeded current-safe 双 target 对比

当你要把当前最重要的两个 **baseline-seeded current + safe runtime** target 连续跑完并生成简洁对比报告时，可直接执行：

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_target_compare.sh
```

说明：
- 固定比较两个 target：
  - stable：`{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}`
  - experimental：`{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}`
- 内部会复用 `run_phytium_current_safe_one_shot.sh` 跑两次，因此默认比较的是两条 **rebuild-only baseline-seeded current** 路线。
- compare 现在会检查两次输出的 `optimized_model.so sha256`；如果 target 不同但 hash 相同，则直接把 compare 标成 invalid 并返回非零退出码。
- 2026-03-10 的既有 smoke/sample compare 报告因为 stable/experimental hash 相同，现在应视为“rebuild-only workflow smoke evidence”，而不是有效 target 差异证据。
- 默认输出：
  - `session_bootstrap/reports/<report_id>.md`
  - `session_bootstrap/reports/<report_id>.json`
  - `session_bootstrap/reports/<report_id>_stable.md`
  - `session_bootstrap/reports/<report_id>_experimental.md`

```bash
export INFERENCE_BASELINE_CMD='bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" --port "${REMOTE_SSH_PORT:-22}" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/full\" && \"$REMOTE_TVM_PYTHON\" tvm_002.py --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/full\" --snr \"$REMOTE_SNR_BASELINE\" --batch_size \"$REMOTE_BATCH_BASELINE\""'
```

- current 仍可继续使用默认的 VM payload，或同样用 `INFERENCE_CURRENT_CMD` 覆盖为自定义命令。
- 产物会写到 `session_bootstrap/reports/<RUN_ID>.md` 与 `session_bootstrap/reports/<RUN_ID>_raw.csv`。

## Full 骨架（当前可执行）

1. 在 env 中配置 full 命令（建议）：
   - `FULL_BASELINE_CMD`
   - `FULL_CURRENT_CMD`
2. 运行：`bash scripts/run_full_placeholder.sh --env ./config/local.env`
3. 检查产物：`logs/<execution_id>.log`、`reports/<execution_id>.md`、`reports/<execution_id>_raw.csv`

说明：
- full 命令未配置时，会回退使用 `QUICK_BASELINE_CMD/QUICK_CURRENT_CMD`。
- 支持 `EXECUTION_ID` 或 `FULL_EXECUTION_ID` 指定执行ID。
- 任一步骤失败会立即退出并写入失败状态报告。

## 日报汇总（当前可执行）

按当日聚合 `logs/` 与 `reports/` 的关键字段并生成日报 markdown：

`bash scripts/summarize_to_daily.sh --env ./config/local.env`

可选参数：
- `--date YYYY-MM-DD`：指定汇总日期（默认今天）。
- `--output <path>`：指定输出路径（默认 `reports/daily_<date>.md`）。

兼容入口：`summarize_results_placeholder.sh` 已转发到 `summarize_to_daily.sh`。

## 首轮真机 RPC 闭环（新增）

1. 先做 readiness 审查：
   `bash scripts/check_rpc_readiness.sh --env ./config/rpc_armv8.example.env`
2. 生成 tracker/server/client 命令模板：
   `bash scripts/rpc_print_cmd_templates.sh --env ./config/rpc_armv8.example.env`
3. 执行首轮闭环（quick + full + daily + experiment）：
   `bash scripts/run_rpc_first_round.sh --env ./config/rpc_armv8.example.env`
4. 无真机时可离线模拟：
   `bash scripts/run_rpc_first_round.sh --env ./config/rpc_armv8_smoke.env --simulate`

详细步骤见：`runbooks/rpc_first_round_runbook.md`。

## 自动化脚本（无人值守 + 共用会话）

### 1) 生成唯一轮次 env（每轮必须先做）

```bash
bash scripts/prepare_round_env.sh \
  --base-env ./config/rpc_armv8.phytium_pi.2026-03-01.env
```

说明：
- 会生成新的 `*.run_<timestamp>.env`；
- 该 `phytium` base env 已按 2026-03-08 复核收敛到 `generic + neon`，不再保留无现场证据的 `+crypto,+crc`；
- 自动注入唯一的：
  - `EXECUTION_ID`
  - `FULL_EXECUTION_ID`
  - `DAILY_REPORT_FILE`

### 2) 本地无人值守串行执行（不依赖 Agent）

```bash
bash scripts/auto_round_local.sh \
  --base-env ./config/rpc_armv8.phytium_pi.2026-03-01.env
```

说明：
- 执行顺序：`readiness -> quick -> full -> daily`；
- 内置 `flock` 防并发重复跑；
- 失败会保留产物并返回非零退出码；
- 可选：`--skip-full`。

### 3) 通过 OpenClaw Agent 提交（共用 `main` 会话上下文）

```bash
bash scripts/submit_round_to_agent.sh \
  --base-env ./config/rpc_armv8.phytium_pi.2026-03-01.env \
  --session main
```

说明：
- 入口走 `oc-live "...任务..." main`，与你在 `oc-tui --session main` 共用上下文；
- 会自动生成唯一轮次 env，再把固定步骤提交给 Agent；
- 可选：`--skip-full`。

### 3.1) 定时给主对话追加“继续”

```bash
bash scripts/send_continue_hourly.sh --start-in-min 1 --count 8
```

说明：
- 默认发送到 `main`，会继续复用 `oc-tui --session main` 的历史对话，而不是新开会话；
- 可直接用 `--start-in-min 1` 表示从未来 1 分钟开始；
- 默认每 20 分钟发一次带“最近对话锚点”的 `继续` 提示，尽量优先续接最新上下文；
- 在本仓库里，auto-continue 现在默认会把目标锁定到 `tvm-飞腾派项目`，即使最近聊天里出现别的工程，也会优先回到本项目清单继续推进；
- 如需改成别的固定项目，可加 `--project-focus "你的项目名"`；
- 自动续跑生成的助手回复不会再被当成下一轮锚点，避免脚本自我续写；
- 如果会话尾部自上次成功自动发送后完全没变化，脚本默认会先跳过 1 轮，再在下一轮重发一次；
- 如需改成“主对话里上一轮任务真正结束后，再发下一条继续”，可加：`--schedule-mode after-complete`；这个模式现在会在发送前先等待 `main` 会话上一轮任务结束，而不是只等待脚本自己上一条 auto-continue 的 run；
- 对 `Connection error.`、`fetch failed`、HTTP 502-504 这类瞬时中转/网络错误，脚本会每 15 秒自动重试；`after-complete` 模式下若 run 因这类错误结束，也会自动重提当前这一轮；
- 如果旧 sender 还占着锁，可直接加：`--replace-existing`，脚本会自动接管；
- 可选：`--count 8` 表示只发 8 次，`--dry-run` 只打印计划不实际发送；
- 可选：`--always-send` 恢复成每个定时点都强制发送；
- 如需后台运行：

```bash
nohup bash scripts/send_continue_hourly.sh --start-in-min 1 --count 8 > /tmp/send_continue_hourly.out 2>&1 &
```

### 4) 设备自动调度（飞腾派在线跑 final，不在线跑骁龙 prep）

```bash
bash scripts/dispatch_round.sh \
  --mode local \
  --target phytium \
  --run-tag nightly
```

说明：
- `--target phytium`：选 `rpc_armv8.phytium_pi.*.env` 跑 final；
- `--target snapdragon`：选 `rpc_armv8.lenovo.*.env` 跑 prep；
- 每轮都会记录到 `reports/dispatch_history.csv`，用于追踪“任务-设备-结果”对应关系。

常用可选项：
- `--mode agent --session main`：用 agent 通道执行（保留 main 会话上下文）
- `--auto-detect`：启用自动探测（你不想手动选目标时再用）
- `--prep-skip-full`：当选择骁龙 prep 时只跑 readiness+quick+daily

### 5) Agent 决策 + Local 执行闭环（MetaSchedule 外环）

```bash
bash scripts/agent_closed_loop.sh \
  --target phytium \
  --rounds 3 \
  --session main \
  --run-tag msloop
```

说明：
- 每轮执行：`readiness -> quick -> full -> daily`（本地执行，稳定可观测）；
- 每轮结束后（除最后一轮）自动给 Agent 提交分析任务；
- Agent 需要落盘 `delta.env`，脚本自动合并到工作 env，进入下一轮；
- 这样 Agent 负责“策略决策”，脚本负责“可靠执行”。
- 当 `--target snapdragon` 时，会强制校验 `MODEL_NAME/TARGET/SHAPE_BUCKETS/THREADS` 与 `phytium final` 配置一致，不一致直接中止。

常用可选项：
- `--target snapdragon --prep-skip-full`：做骁龙前置任务，避免 full 夜跑
- `--delta-wait-sec 90`：等待 Agent 落盘 `delta.env` 的最长时间
- `--allow-command-edits`：允许 Agent 修改 QUICK/FULL 命令（默认禁用，防误改）
- `--require-agent-delta`：要求每轮必须产出 delta，否则中止

补充：
- `config/rpc_armv8.lenovo.2026-03-01.env` 已切换到真实 prep payload（`run_remote_tvm_payload.sh`）。
- 在跑 `--target snapdragon` 前，必须先填完该 env 的 `REMOTE_*` 骁龙连接与归档路径；readiness 会强制拦截占位值。
- `run_remote_tvm_payload.sh` 支持 `REMOTE_MODE=ssh|local`：
  - `ssh`：通过 SSH 在远端执行（默认）；
  - `local`：直接本机执行（不依赖飞腾派网络）。
- `REMOTE_MODE=local` 时，readiness 会额外检查：
  - `REMOTE_TVM_PYTHON` 是否可 `import tvm`；
  - 各 archive 是否包含 `tvm_tune_logs/optimized_model.so` 与 `tuning_logs/database_*.json`。
- 可直接参考：`config/rpc_armv8.snapdragon_local.2026-03-01.env`。

## 飞腾派 Python 入口更新（2026-03-08）

已确认飞腾派旧环境 `/home/user/venv/bin/python`（Python 3.9.5）**不兼容** TVM 0.24 Python 侧代码；
后续飞腾派执行入口应统一切到：

```bash
/home/user/anaconda3/envs/tvm310/bin/python
```

推荐更新项：
- `REMOTE_TVM_PYTHON=/home/user/anaconda3/envs/tvm310/bin/python`
- 保留旧 `venv` 仅作回退参考，不再作为 TVM 0.24 默认入口。

迁移详情见：`reports/phytium_tvm24_python310_migration_2026-03-08.md`

## RPC Tune 闭环（笔记本搜索/编译 + 飞腾派测量）

架构：笔记本（骁龙 ARM）做 tracker + builder + 搜索/编译，飞腾派（ARMv8）只做 RPC runner 测量。
搜索和编译利用笔记本算力加速，测量数据来自飞腾派真机。

### 飞腾派 target 备注（2026-03-08 → 2026-03-10 更新）

- 当前 builder（LLVM 18）对 `aarch64-linux-gnu` **不接受** `mcpu=phytium` / `mcpu=ft2000plus`，因此不能把飞腾专有 `mcpu` 名称当成默认方案。
- 在飞腾派真机上完成 `tvm310_safe + TVM 0.24.dev0` 路径修复后，已经对 `current` 做过一轮真实 VM 推理 target 对比。
- 结论是：**旧的 `generic + neon` 过于保守，不再推荐作为 current 默认 target。**

当前推荐默认 target（current 路径）：

```bash
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
```

继续实验 target（更激进，median 更好但抖动更大）：

```bash
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}'
```

说明：
- 这轮结论只针对 **current + safe 0.24dev runtime**；baseline 仍然依赖旧 compat runtime 路径。
- 详情见：
  - `reports/phytium_tvm24_rebuild_plan_and_llvm_matrix_20260309.md`
  - `reports/phytium_current_target_comparison_safe_runtime_20260310.md`
  - `config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env`

### 新增脚本

- `scripts/rpc_tune.py`：RPC 调优核心（ONNX -> Relax IR -> RPCRunner MetaSchedule tune -> .so + database）。
- `scripts/manage_rpc_services.sh`：一键管理 tracker（本机）和 rpc_server（飞腾派 via SSH）。
- `scripts/run_rpc_tune.sh`：完整闭环编排（services -> readiness -> tune -> deploy current artifact -> quick -> full -> daily）。
- `scripts/extract_hotspot_tasks.py`：提取/排序当前模型在指定 target 下的 MetaSchedule 任务，输出 markdown/json 报告与推荐 `FULL_HOTSPOT_TASKS`。
- `config/rpc_armv8.phytium_rpc_tune.env`：RPC tune 专用配置模板。
- `config/rpc_tune_real.2026-03-09.phytium_pi.env`：Phytium Pi 首轮真机 RPC 调优配置（warm-start + rpc runner + nonzero trials）。

### 首次使用

1. 复制配置模板并填写笔记本局域网 IP：

```bash
cp config/rpc_armv8.phytium_rpc_tune.env config/rpc_tune_local.env
# 编辑 RPC_TRACKER_HOST 为笔记本 LAN IP
```

2. 从飞腾派拉取 ONNX 模型到本机：

```bash
bash scripts/manage_rpc_services.sh --env config/rpc_tune_local.env prepare
```

3. 一键执行完整闭环（tune + quick + full + daily）：

```bash
bash scripts/run_rpc_tune.sh --env config/rpc_tune_local.env
```

### Phytium Pi / WSL 当前推荐拓扑（2026-03-09）

如果飞腾派无法通过 Tailscale 反向连回本地 tracker（当前 WSL 环境有入站限制），优先使用：
- **远端 tracker（飞腾派）**
- **远端 runner（飞腾派）**
- **本地 builder/orchestrator（笔记本）**

对应配置见：
- `config/rpc_tune_real.2026-03-09.phytium_pi.env`

先起服务：

```bash
bash scripts/manage_rpc_services.sh --env config/rpc_tune_real.2026-03-09.phytium_pi.env start-all
bash scripts/manage_rpc_services.sh --env config/rpc_tune_real.2026-03-09.phytium_pi.env status
```

### 常用操作

```bash
# 手动启动/停止 RPC 服务
bash scripts/manage_rpc_services.sh --env config/rpc_tune_local.env start-all
bash scripts/manage_rpc_services.sh --env config/rpc_tune_local.env status
bash scripts/manage_rpc_services.sh --env config/rpc_tune_local.env stop-all

# 仅 tune + quick（跳过 full 夜跑）
bash scripts/run_rpc_tune.sh --env config/rpc_tune_local.env --skip-full

# 本机 smoke test（不需要飞腾派）
bash scripts/run_rpc_tune.sh --env config/rpc_tune_local.env --runner local --skip-services

# 查看命令模板
bash scripts/rpc_print_cmd_templates.sh --env config/rpc_tune_local.env
```

### RPC Tune env 新增字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `ONNX_MODEL_PATH` | 本机 ONNX 模型路径 | `/home/tianxing/.../model.onnx` |
| `REMOTE_ONNX_PATH` | 飞腾派上的 ONNX 路径（prepare 用） | `/home/user/Downloads/temp_simp.onnx` |
| `LOCAL_TVM_PYTHON` | 笔记本 TVM Python 路径 | `/home/tianxing/.venvs/tvm-ms/bin/python` |
| `TUNE_INPUT_SHAPE` | 模型输入 shape | `1,32,32,32` |
| `TUNE_TOTAL_TRIALS` | MetaSchedule 搜索总试次 | `500` |
| `TUNE_OUTPUT_DIR` | tune 产物输出目录 | `./session_bootstrap/tmp/rpc_tune_output` |
| `TUNE_EXISTING_DB` | 上一轮 tuning database（warm-start） | 留空或路径 |
| `TUNE_RUNNER` | runner 类型 | `rpc` 或 `local` |
| `TUNE_TIMEOUT_SEC` | tune 超时秒数 | `7200` |

### Readiness 检查

当 env 中设置了 `ONNX_MODEL_PATH` 时，`check_rpc_readiness.sh` 会额外检查：
- ONNX 文件是否存在
- 本机 TVM 是否可用（`import tvm` + `from_onnx`）
- `TUNE_INPUT_SHAPE` 格式是否正确
- `TUNE_TOTAL_TRIALS` 是否已配置
- `TUNE_REQUIRE_REAL=1` 时是否真的满足 `runner=rpc && trials>0`
- `TUNE_EXISTING_DB`（若配置）是否含有完整 warm-start 数据库
- `TUNE_OUTPUT_DIR` 是否可写
- Tracker 端口是否可达

## 最低完成标准

- 有可复现 quick 结果。  
- 有可追溯 full 日志。  
- 有一份当日日报和一份实验记录。
