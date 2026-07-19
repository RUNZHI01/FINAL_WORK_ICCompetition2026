# TVM MetaSchedule Execution Project

面向极端场景应急巡检的飞腾多核异构安全语义图像回传系统。

- **参赛赛事：** 第八届全国大学生集成电路创新创业大赛（飞腾杯）
- **队伍编号：** CICC0903540
- **团队名称：** 逃离荒岛队
- **当前对外定位：** 不是 generic TVM/MNN 优化项目，而是部署在飞腾平台上的、可运行、可管控、可安全停机的弱网语义视觉回传系统。

## 先读这里

- **新接手专家优先阅读：** [`EXPERT_HANDOFF.md`](EXPERT_HANDOFF.md)
- **准备 GitHub 发布前先检查：** [`GITHUB_PUBLISH_CHECKLIST.md`](GITHUB_PUBLISH_CHECKLIST.md)

仓库当前主要由三条主线组成：

- `session_bootstrap/`：性能调优、真机 benchmark、OpenAMP demo、证据与 runbook
- `openamp_mock/`：最小控制面 mock 与协议/边界测试
- `cockpit_native/`：承接现有 demo 合同的原生 Qt/QML 演示座舱

## 当前最佳成绩

| 路线 | 指标 | 数值 |
|---|---|---|
| TVM 真实端到端重建 | baseline → current | 1850.0 → 230.339 ms/image（**87.55% 提升**） |
| TVM payload 级推理 | baseline → current | 1846.9 → 130.219 ms（**92.95% 提升**） |
| big.LITTLE 真机 apples-to-apples compare | serial current → pipeline current | 231.522 → 134.617 ms/image（健康板态默认引用，同轮吞吐 **+56.077%**） |
| TVM 增量调优加速比 | rebuild-only → incremental | **16.272x** |
| MNN 动态形状推理 | 加速比 | 1.85x（300 张不同尺寸图片） |

## 目录结构

```
.
├── paper/                          # 参赛文档
│   ├── CICC0903540初赛技术文档.md      # 初赛技术文档（正式提交）
│   └── 集创赛冲奖调优方案_2026-03-12.md  # 内部调优方案与执行计划
├── session_bootstrap/              # 执行脚手架（脚本、配置、日志、报告）
│   ├── scripts/                       # 执行脚本（调优、推理、部署、benchmark）
│   ├── config/                        # 环境配置（.env 文件）
│   ├── docs/                          # 持续维护的设计文档
│   ├── reports/                       # 实验报告与 benchmark 结果
│   ├── logs/                          # 运行日志
│   ├── runbooks/                      # 操作手册
│   ├── templates/                     # 日报与实验记录模板
│   ├── tasks/                         # 待办与优先级
│   ├── state/                         # 运行状态
│   ├── tmp/                           # 临时产物（调优输出、编译中间件）
│   ├── README.md                      # 执行命令说明
│   └── PROGRESS_LOG.md                # 进度日志（里程碑时间线）
├── TVM_LAST_understanding/         # TVM 工程结构理解文档
├── cicc_tech_doc/                  # LaTeX 版技术文档（PDF 生成）
└── README.md                      # 本文件
```

## 关键入口

| 用途 | 入口 |
|---|---|
| 了解项目全貌 | `paper/CICC0903540初赛技术文档.md` |
| 查看调优方案与执行计划 | `paper/集创赛冲奖调优方案_2026-03-12.md` |
| 查看进度与里程碑 | `session_bootstrap/PROGRESS_LOG.md` |
| 执行命令与脚本说明 | `session_bootstrap/README.md` |
| 当前成果 / 脚本 / 路径索引 | `session_bootstrap/runbooks/artifact_registry.md` |
| 评委补证工作流（quality / hotspot / resource / SNR / final pack） | `session_bootstrap/runbooks/judge_evidence_workflow_2026-03-30.md` |
| 评委技术证据总包（2026-03-30，latest） | `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md` |
| PSNR / SSIM / LPIPS 正式质量报告（2026-03-30，latest） | `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md` |
| 多 SNR 鲁棒性摘要（2026-03-30，latest） | `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md` |
| OpenAMP 控制面答辩证据包 | `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md` |
| OpenAMP demo / 答辩材料索引 | `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_materials_index.md` |
| OpenAMP demo 最新 live 双路径状态（2026-03-17） | `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md` |
| OpenAMP demo dashboard 本地启动验收（2026-03-17） | `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md` |
| OpenAMP demo 最终交付快照（2026-03-17） | `session_bootstrap/reports/openamp_demo_live_delivery_snapshot_20260317.md` |
| 启动集成 OpenAMP demo 软件 | `bash session_bootstrap/scripts/run_openamp_demo.sh` |
| OpenAMP demo 软件说明 | `session_bootstrap/demo/openamp_control_plane_demo/README.md` |
| ML-KEM / 后量子安全链路合入位置 | 见下方“ML-KEM 工作位置” |
| USRP latent 数据面方案（审查版） | `session_bootstrap/docs/design_usrp_latent_transport.md` |
| 下一轮性能优化执行清单 | `session_bootstrap/runbooks/next_round_optimization_checklist.md` |
| big.LITTLE 首次真机一键入口 | `bash session_bootstrap/scripts/run_big_little_first_real_attempt.sh` |
| big.LITTLE 真机结论摘要（推荐入口） | `session_bootstrap/reports/big_little_real_run_summary_20260318.md` |
| big.LITTLE 首选 apples-to-apples compare | `session_bootstrap/reports/big_little_compare_20260318_123300.md` |
| big.LITTLE 配套 pipeline wrapper 报告 | `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md` |
| big.LITTLE 板态漂移复盘 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md` |
| big.LITTLE 历史最佳 current e2e 参考 | `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` |
| big.LITTLE 首轮资源 profiling（支持性证据） | `session_bootstrap/reports/resource_profile_big_little_current_20260318_052922.md` |
| big.LITTLE 首跑前交接（历史） | `session_bootstrap/reports/big_little_overnight_handoff_20260318.md` |
| big.LITTLE 异构流水线 runbook | `session_bootstrap/runbooks/big_little_pipeline_runbook_2026-03-18.md` |
| 后续性能优化路线 | `session_bootstrap/runbooks/optimization_roadmap.md` |
| 飞腾派 RPC 调优 | `session_bootstrap/scripts/rpc_tune.py` |
| 真实端到端重建 benchmark | `session_bootstrap/scripts/current_real_reconstruction.py` |
| baseline vs current 推理对比 | `session_bootstrap/scripts/run_inference_benchmark.sh` |

## 当前可信产物（2026-03-18）

| 类别 | 当前可信入口 |
|---|---|
| trusted current 本地产物 | `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so` |
| trusted current SHA256 | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` |
| payload 基准结论 | `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`（`1846.9 → 130.219 ms`，`92.95%` 提升） |
| 历史最佳 direct current e2e 参考 | `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`（`1850.0 → 230.339 ms/image`，`87.55%` 提升） |
| big.LITTLE 首选 apples-to-apples compare | `session_bootstrap/reports/big_little_compare_20260318_123300.md`（健康板态下 serial current `231.522 ms/image` → pipeline current `134.617 ms/image`，吞吐 `+56.077%`） |
| big.LITTLE 板态漂移结论 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md`（same-day direct rerun `347.375 → 295.255 → 239.233 ms/image`，CPU online `0-2 → 0-3`，说明板态是 primary factor） |
| 详细产物 / 脚本 / 路径说明 | `session_bootstrap/runbooks/artifact_registry.md` |

### 评委补证材料（2026-03-30）

- `session_bootstrap/runbooks/judge_evidence_workflow_2026-03-30.md`
- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_latency.svg`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_quality.svg`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`
- `session_bootstrap/reports/defense_quick_reference_card_20260330_current_chunk4.md`

### 飞腾杯冲奖救援文档（2026-03-19）

- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/award_rescue_execution_checklist_20260319.md`
- `session_bootstrap/reports/defense_deck_outline_20260319.md`
- `session_bootstrap/reports/defense_ppt_pages_1_8_cn_20260319.md`
- `session_bootstrap/reports/defense_talk_track_5min_20260320.md`
- `session_bootstrap/reports/defense_talk_track_2min_20260320.md`
- `session_bootstrap/reports/defense_demo_operator_card_20260320.md`
- `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md`

## ML-KEM 工作位置

你朋友 `feat/ML-KEM` 分支的代码已经合入当前主线。现在这部分工作分成两层：

- **主线集成层（本仓库内）**：负责 cockpit 面板、HTTP API、运行时适配、测试入口
- **独立安全链路实现层（伴随仓库）**：负责 `mlkem_link`、`tcp_client.py`、`tcp_server.py` 等底层安全通信脚本

### 1. 主线集成层：现在在本仓库哪些位置

| 作用 | 位置 |
|---|---|
| ML-KEM 状态面板 UI | `cockpit_desktop/src/renderer/src/components/dashboard/CryptoStatusPanel/` |
| ML-KEM 前端 API 类型 | `cockpit_desktop/src/renderer/src/api/types/crypto.ts` |
| ML-KEM 前端请求入口 | `cockpit_desktop/src/renderer/src/api/client.ts` |
| Dashboard 挂载点 | `cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx` |
| 后端 `/api/crypto-status` `/api/crypto-toggle` `/api/crypto-test` | `session_bootstrap/demo/openamp_control_plane_demo/server.py` |
| 跨机器路径 / SSH / 环境适配层 | `session_bootstrap/demo/openamp_control_plane_demo/crypto_runtime.py` |
| 主线侧可移植性测试 | `session_bootstrap/demo/openamp_control_plane_demo/tests/test_crypto_runtime.py` |

### 2. 独立安全链路实现层：你朋友原始工作的主要位置

当前主线默认按“同级伴随仓库”方式去找这部分代码；也就是说，若当前仓库目录旁边存在 `ICCompetition2026/`，主线会优先在那里查找 ML-KEM 底层脚本。

你朋友原始工作的核心位置是：

| 作用 | 位置 |
|---|---|
| ML-KEM 会话 / KEM / AEAD 实现 | `../ICCompetition2026/mlkem_link/` |
| 上位机发送脚本 | `../ICCompetition2026/scripts/tcp_client.py` |
| 板端接收脚本 | `../ICCompetition2026/scripts/tcp_server.py` |
| 库级测试 | `../ICCompetition2026/mlkem_link/tests/test_session.py` |
| FIT / 篡改 / 套件隔离测试 | `../ICCompetition2026/scripts/test_fit.py` |
| 该仓库自身说明 | `../ICCompetition2026/README.md` |

如果目录结构不是“两个仓库同级”，请显式设置：

- `MLKEM_LOCAL_REPO_ROOT`
- `MLKEM_CLIENT_SCRIPT`
- `MLKEM_REMOTE_PROJECT_ROOT`
- `MLKEM_REMOTE_SERVER_SCRIPT`
- `MLKEM_REMOTE_STARTUP_CMD`

更多环境变量说明见 `cockpit_desktop/README.md`。

### 3. 当前主线对这部分工作的已知边界

- 当前主线里的 `run_crypto_test()` 已经能调用外部 `tcp_client.py` 做真实链路测试。
- 当前主线里的状态面板要求板端提供 HTTP `/status` 能力。
- 你朋友当前的 `tcp_server.py` 还没有 `--status-port` / `/status`，所以“加密传输能跑”与“面板状态轮询能跑”目前仍是两件事。

### 4. 已在本机验证过的相关测试

在当前开发机上，下面这些入口已经实际跑通过：

- `python3 -m unittest session_bootstrap.demo.openamp_control_plane_demo.tests.test_crypto_runtime`
- `python3 -m unittest session_bootstrap.demo.openamp_control_plane_demo.tests.test_server`
- `cd ../ICCompetition2026 && .venv/bin/python -m pytest mlkem_link/tests/test_session.py -q -rA`
- `cd ../ICCompetition2026 && .venv/bin/python -m pytest scripts/test_fit.py -q -rA`

如果你朋友回来继续接这部分，建议优先从：

1. `session_bootstrap/demo/openamp_control_plane_demo/server.py`
2. `session_bootstrap/demo/openamp_control_plane_demo/crypto_runtime.py`
3. `../ICCompetition2026/scripts/tcp_server.py`
4. `../ICCompetition2026/mlkem_link/`

这四个入口往下看。

## 项目一句话

前线无人机/巡检机器人在弱网或灾后场景下难以稳定回传原始图像，因此系统先在上位机提取语义特征，再把低负载语义张量传到飞腾边缘节点；Linux 主核负责图像重建、显示与存储，RTOS/Bare Metal 从核通过 OpenAMP 负责作业准入、心跳监护和安全停机。

## 技术架构

```
上位机（笔记本）                          飞腾派（端侧设备）
┌─────────────────────┐               ┌──────────────────────────┐
│ Encoder 推理         │               │ Decoder 推理（TVM/MNN）   │
│ ONNX 导出 + 简化     │    SSH/SCP    │ safe runtime (TVM 0.24)  │
│ MetaSchedule 调优    │ ←──────────→  │ Cortex-A72 × 2 (big)     │
│ (builder 侧)        │    RPC        │ Cortex-A55 × 2 (LITTLE)  │
│                     │               │ NEON 128-bit SIMD         │
└─────────────────────┘               └──────────────────────────┘
```

## 环境要求

- **上位机：** Python 3.10+, TVM 0.24dev, ONNX, onnxsim
- **飞腾派：** Anaconda `tvm310_safe` 环境, TVM 0.24.dev0 (safe runtime), MNN
- **连接：** SSH（密码或密钥认证），RPC tracker/runner（调优时）

## 快速开始

```bash
# 0. 启动集成 OpenAMP dashboard（默认离线证据模式）
bash session_bootstrap/scripts/run_openamp_demo.sh

# 1. 连接飞腾派
bash session_bootstrap/scripts/connect_phytium_pi.sh

# 2. 运行 baseline vs current 推理对比
bash session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env

# 3. 运行真实端到端重建对比
bash session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

# 4. 启动 RPC 调优（笔记本 builder + 飞腾派 runner）
python session_bootstrap/scripts/rpc_tune.py \
  --onnx-path <model.onnx> \
  --output-dir ./tune_output \
  --target '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}' \
  --total-trials 2000 \
  --input-shape 1,32,32,32 \
  --runner rpc
```
