# 专家接手交接文档

更新时间：`2026-03-25`

本文面向第一次接手本仓库的专家，目标不是复述全部历史，而是帮助你在 1-2 天内判断：

- 这个仓库现在到底在交付什么
- 哪些结论已经被正式验证，哪些只是历史过程或演示素材
- 从哪里开始复现实验、演示、或继续工程化
- GitHub 发布前哪些内容需要先清理或重新定界

建议先读：[README.md](README.md)，然后直接回到本文。

## 1. 项目目标

本项目当前对外定位不是“泛 TVM 优化样例”，而是一个部署在飞腾平台上的、面向弱网/灾后/应急巡检场景的多核异构安全语义视觉回传系统。顶层定义见：

- [README.md](README.md)
- [paper/CICC0903540初赛技术文档.md](paper/CICC0903540初赛技术文档.md)

一句话拆解：

- 数据面：上位机或边缘侧处理 latent/语义张量，飞腾板侧做图像重建、显示与存储
- 性能主线：围绕 TVM MetaSchedule、safe runtime、baseline/current 对比、big.LITTLE 异构流水线做真机验证
- 控制面：围绕 OpenAMP 的准入、心跳、SAFE_STOP、FIT 测试和答辩演示做证据化交付
- 演示壳体：同时提供 Web dashboard 和 Qt/QML 原生座舱

## 2. 当前架构与模块

### 2.1 架构分层

1. 性能与执行主线
   主要在 [session_bootstrap/](session_bootstrap/)。
   这里不是单纯脚本目录，而是“脚本 + 配置 + 日志 + 报告 + runbook + 状态”的执行框架。

2. OpenAMP 控制面与演示主线
   Host 侧工程主要在 [session_bootstrap/demo/openamp_control_plane_demo/](session_bootstrap/demo/openamp_control_plane_demo/) 和 [session_bootstrap/scripts/](session_bootstrap/scripts/)。
   真机结论和答辩证据主要在 [session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/](session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/)。

3. 原生座舱展示主线
   主要在 [cockpit_native/](cockpit_native/)。
   这不是独立产品，而是复用现有 OpenAMP demo/operator server 合同的 PySide6/QML 原生壳体。

4. OpenAMP 最小 mock 与边界测试
   主要在 [openamp_mock/](openamp_mock/)。
   这是最小协议/状态机 mock，不是板侧真固件源码。

5. 论文与叙事材料
   主要在 [paper/](paper/) 和 [cicc_tech_doc/](cicc_tech_doc/)。
   前者更像交付叙事和阶段性技术文档，后者是 LaTeX 版技术文档工作区。

### 2.2 关键事实

- 仓库里有“真机性能结论”和“真机控制面证据”，但并不包含完整的板侧 OpenAMP 固件源码树。
- `openamp_mock` 负责 mock/边界验证；`session_bootstrap/scripts/*openamp*` 负责 host 侧 wrapper、probe、bridge、演示编排；板上固件变化主要通过报告和 runbook 留痕。
- `cockpit_native` 依赖现有 operator server；默认不是自己直接连板，而是通过已有 demo server 合同工作。见 [cockpit_native/README.md](cockpit_native/README.md) 和 [session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md)。

## 3. 关键目录说明

| 路径 | 角色 | 接手建议 |
|---|---|---|
| [README.md](README.md) | 顶层项目说明、当前入口索引 | 先读 |
| [session_bootstrap/README.md](session_bootstrap/README.md) | 执行框架说明、主要脚本入口、env 说明 | 必读 |
| [session_bootstrap/PROGRESS_LOG.md](session_bootstrap/PROGRESS_LOG.md) | 长时间线真相源，混有多轮历史结论 | 用于查时间线，不直接当单一结论页 |
| [session_bootstrap/runbooks/artifact_registry.md](session_bootstrap/runbooks/artifact_registry.md) | 当前可信产物、报告、脚本总索引 | 默认总入口 |
| [session_bootstrap/reports/](session_bootstrap/reports/) | 已验证报告、FIT bundle、比较结果、交付索引 | 结论源 |
| [session_bootstrap/config/](session_bootstrap/config/) | env 样例、推荐配置、历史快照 | 复制后使用，不直接覆写 trusted env |
| [session_bootstrap/scripts/](session_bootstrap/scripts/) | benchmark、调优、远端执行、OpenAMP wrapper、demo 启动脚本 | 主执行入口 |
| [session_bootstrap/demo/openamp_control_plane_demo/](session_bootstrap/demo/openamp_control_plane_demo/) | Web dashboard 与 backend | OpenAMP 演示主工程 |
| [cockpit_native/](cockpit_native/) | Qt/QML 原生座舱 | 演示壳体，不是性能主线 |
| [openamp_mock/](openamp_mock/) | 最小控制面 mock、协议/状态机测试 | 协议理解和边界测试入口 |
| [paper/](paper/) | 论文、答辩、方案、对齐文档 | 用于叙事和后续论文工作 |
| [TVM_LAST_understanding/](TVM_LAST_understanding/) | 针对 TVM 工程的个人理解笔记 | 辅助阅读，不是正式源 |
| [cicc_tech_doc/](cicc_tech_doc/) | LaTeX 技术文档工作区 | 当前包含明显构建中间产物 |

## 4. 当前已验证结果

下面只列当前最应该被引用的结果，不列所有历史对比。

### 4.1 性能主线

1. 最新 trusted current payload 正式结论
   证据： [session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md)

   - baseline median：`1846.9 ms`
   - current median：`130.219 ms`
   - 提升：`92.95%`
   - current SHA256：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

2. 最新 trusted current 真实端到端重建正式结论
   证据： [session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)

   - baseline median：`1850.0 ms/image`
   - current median：`230.339 ms/image`
   - 提升：`87.55%`
   - baseline/current count：`300 / 300`
   - current SHA256：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

3. healthy-board big.LITTLE apples-to-apples compare
   证据： [session_bootstrap/reports/big_little_compare_20260318_123300.md](session_bootstrap/reports/big_little_compare_20260318_123300.md) 和 [session_bootstrap/reports/big_little_real_run_summary_20260318.md](session_bootstrap/reports/big_little_real_run_summary_20260318.md)

   - serial current median：`231.522 ms/image`
   - pipeline current median：`134.617 ms/image`
   - 吞吐提升：`56.077%`

4. big.LITTLE 漂移调查的重要结论
   证据： [session_bootstrap/reports/big_little_board_state_drift_20260318.md](session_bootstrap/reports/big_little_board_state_drift_20260318.md)

   - 同日 direct rerun 序列：`347.375 -> 295.255 -> 239.233 ms/image`
   - CPU online：`0-2 -> 0-3`
   - 结论：板态 / CPU online set 是 primary factor，不只是 artifact lineage

### 4.2 OpenAMP 控制面主线

1. P0/P1 最终结论
   证据： [session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md](session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md)

   - P0 最小控制面里程碑：真机落证
   - P1 `FIT-01` / `FIT-02` / `FIT-03`：最终 `PASS`
   - `FIT-03` 保留了 pre-fix FAIL -> post-fix PASS 的完整链路

2. 当前 live 演示的历史快照
   证据： [session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md](session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md)

   - `current` live：`300 / 300`
   - `baseline` live：`300 / 300`

3. 但 2026-03-22 之后的 operator 默认语义发生收束
   证据： [session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md](session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md)

   - Scene 3 默认是 archived PyTorch reference
   - `2026-03-17` baseline `300 / 300` 应视为历史 live 证据，而不是默认 operator branch

### 4.3 演示座舱主线

1. `cockpit_native` 的最新交付入口
   证据：
   - [cockpit_native/README.md](cockpit_native/README.md)
   - [session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md)

2. 当前明显存在的口径差异
   `cockpit_native` 讲稿和 packet index 仍引用 `2026-03-11` 的 headline：`1844.1 ms -> 153.778 ms`。
   这组数据在仓库内有正式来源，但已经不是顶层 README 当前默认的最新 trusted current 指标。对外发布或新答辩时，必须决定是否统一到 `2026-03-13` 的更晚结果。

## 5. 环境与前置条件

### 5.1 要先接受的现实

这个仓库不是“一键从零搭环境”的项目。

- 根目录没有统一的 `requirements.txt`、`pyproject.toml` 或整仓环境锁文件
- 很多能力默认依赖外部已准备好的飞腾板环境、已有 TVM 构建、已有 SSH/RPC 通路
- 因此接手时应把“本地 Python 环境”和“板上 TVM/runtime 环境”视为外部前置条件，而不是期待仓库自动创建

### 5.2 本地侧最小准备

依据 [README.md](README.md) 和 [session_bootstrap/README.md](session_bootstrap/README.md)，本地建议至少准备：

- Python `3.10+`
- TVM `0.24dev`
- `onnx`
- `onnxsim`
- SSH 工具链

若要运行 `cockpit_native` 真 UI，还需要：

- `PySide6`

### 5.3 飞腾板侧最小准备

仓库现有文档能确认的关键约束：

1. 旧 `/home/user/venv/bin/python`（Python `3.9.5`）已被判定为不兼容 TVM 0.24 Python 路径。
   证据： [session_bootstrap/README.md](session_bootstrap/README.md) 的“飞腾派 Python 入口更新（2026-03-08）”部分。

2. 当前文档同时出现两类板侧 Python/runtime 入口：

   - 常规 TVM 0.24 入口：`/home/user/anaconda3/envs/tvm310/bin/python`
   - trusted current / safe runtime 入口：`tvm310_safe` 路径及其 FFI/LD_LIBRARY_PATH 包装

3. 对 expert 来说，最重要的不是重建这些环境，而是先理解：

   - 哪条 benchmark 走 compat runtime
   - 哪条 benchmark 走 current-safe runtime
   - 哪个 env 文件绑定了 trusted SHA

### 5.4 推荐的配置复制方式

最常用的复制起点：

```bash
cp ./session_bootstrap/config/local.example ./session_bootstrap/config/local.env
cp ./session_bootstrap/config/phytium_pi_login.example.env ./session_bootstrap/config/phytium_pi_login.env
cp ./session_bootstrap/config/rpc_armv8.example.env ./session_bootstrap/config/rpc_armv8.local.env
```

相关模板：

- [session_bootstrap/config/local.example](session_bootstrap/config/local.example)
- [session_bootstrap/config/phytium_pi_login.example.env](session_bootstrap/config/phytium_pi_login.example.env)
- [session_bootstrap/config/rpc_armv8.example.env](session_bootstrap/config/rpc_armv8.example.env)

不要直接覆写已作为历史证据使用的 trusted env；应复制出新的 env 再跑。

## 6. 如何运行主流程 / demo

### 6.1 OpenAMP Web dashboard

默认启动：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

可选只读板级 probe：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --probe-env ./session_bootstrap/config/phytium_pi_login.env
```

说明见：

- [session_bootstrap/demo/openamp_control_plane_demo/README.md](session_bootstrap/demo/openamp_control_plane_demo/README.md)
- [session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md](session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md)

### 6.2 OpenAMP mock 最小闭环

```bash
python3 -m openamp_mock.demo --scenario all --output-dir session_bootstrap/reports/openamp_mock_examples/smoke_20260313_p0p1 --run-id openamp_mock_smoke_20260313_p0p1
python3 -m unittest discover -s openamp_mock/tests -t .
```

入口说明见：

- [openamp_mock/README.md](openamp_mock/README.md)

### 6.3 trusted current payload benchmark

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh \
  --env ./session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
```

这是当前最重要的 payload formal compare 入口之一，前提是板侧 trusted current artifact 与 env 中的 expected SHA 一致。

### 6.4 当前 artifact 的真实重建路径

当前 README 给出的入口是：

```bash
bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
```

如果要理解它背后的 formal compare/历史结论，应同时读：

- [session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)
- [session_bootstrap/reports/inference_real_reconstruction_runner_handoff_20260311.md](session_bootstrap/reports/inference_real_reconstruction_runner_handoff_20260311.md)

### 6.5 rebuild-only current-safe 复现

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh
```

语义：复用历史 tuning DB，做 baseline-seeded rebuild-only current-safe 验证。

### 6.6 baseline-style current rebuild

```bash
bash ./session_bootstrap/scripts/run_phytium_baseline_style_current_rebuild.sh
```

语义：用更公平的 baseline-style payload 语义重建并验证 current。

### 6.7 baseline-seeded warm-start incremental tuning

```bash
bash ./session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh
```

语义：nonzero-budget current 增量调优主入口。

### 6.8 big.LITTLE 真机一键入口

```bash
bash ./session_bootstrap/scripts/run_big_little_first_real_attempt.sh
```

之后优先看：

- [session_bootstrap/reports/big_little_real_run_summary_20260318.md](session_bootstrap/reports/big_little_real_run_summary_20260318.md)
- [session_bootstrap/reports/big_little_compare_20260318_123300.md](session_bootstrap/reports/big_little_compare_20260318_123300.md)

### 6.9 原生座舱与交付包

最短启动：

```bash
bash ./session_bootstrap/scripts/run_cockpit_native.sh
```

彩排：

```bash
bash ./session_bootstrap/scripts/run_cockpit_native_demo_rehearsal.sh
```

打包：

```bash
bash ./session_bootstrap/scripts/build_cockpit_native_demo_packet.sh
```

说明见：

- [cockpit_native/README.md](cockpit_native/README.md)
- [session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md)

## 7. 什么是源码真相源，什么是生成物

### 7.1 应视为真相源的内容

1. 核心脚本与代码
   - [session_bootstrap/scripts/](session_bootstrap/scripts/)
   - [session_bootstrap/demo/openamp_control_plane_demo/](session_bootstrap/demo/openamp_control_plane_demo/)
   - [openamp_mock/](openamp_mock/)
   - [cockpit_native/](cockpit_native/)

2. 已整理过的总结型文档
   - [README.md](README.md)
   - [session_bootstrap/README.md](session_bootstrap/README.md)
   - [session_bootstrap/runbooks/artifact_registry.md](session_bootstrap/runbooks/artifact_registry.md)
   - [session_bootstrap/PROGRESS_LOG.md](session_bootstrap/PROGRESS_LOG.md)
   - [session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md](session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md)

3. 作为控制面 allowlist/准入依据的配置
   - [session_bootstrap/config/openamp_trusted_artifacts.json](session_bootstrap/config/openamp_trusted_artifacts.json)

### 7.2 “生成的，但现在被当作交付证据保留”的内容

这些东西 technically 是生成物，但现在已经进入交付叙事，不应在不了解上下文的情况下统一清掉：

- `session_bootstrap/reports/` 下大量 `.md`、`.json`、FIT bundle、`.raw.log`
- big.LITTLE compare 的 raw log 与 JSON
- OpenAMP FIT 目录下的 status snapshot、trace、summary
- 某些 `paper/` 下的材料和截图索引

换句话说：

- `reports/` 里很多文件是“实验生成物”
- 但当前仓库已经把它们当“正式证据资产”
- GitHub 发布前应筛选，而不是全删

### 7.3 更像本地运行产物或临时产物的内容

这些通常不应成为长期公开仓库内容，或至少要重新评估：

- `session_bootstrap/tmp/`
- `session_bootstrap/logs/`
- `cockpit_native/runtime/`
- `session_bootstrap/demo/openamp_control_plane_demo/runtime/`
- `.codex_tmp/`
- `__pycache__/`
- `cockpit_native/.venv/`
- `cicc_tech_doc/` 下 LaTeX 构建中间件，如 `.aux`、`.log`、`.fdb_latexmk`

## 8. 已知风险与坑

1. 不要混写不同语义的指标
   `payload`、`real reconstruction`、`big.LITTLE compare`、`degraded-board compare` 都不是同一种结论。
   目前最稳妥的引用组合是：
   - payload：`2026-03-13 17:58`
   - real reconstruction：`2026-03-13 17:58`
   - big.LITTLE healthy-board compare：`2026-03-18 12:33`
   - drift 说明：`2026-03-18`

2. current-safe 必须带 artifact identity guard
   `INFERENCE_CURRENT_EXPECTED_SHA256` 是关键边界。
   只要远端 `.so` 变了，env 里的 expected SHA 必须同步更新。
   相关入口：
   - [session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env](session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env)
   - [session_bootstrap/config/openamp_trusted_artifacts.json](session_bootstrap/config/openamp_trusted_artifacts.json)

3. big.LITTLE 性能高度受板态影响
   如果结果突然回落，不要先怀疑 artifact lineage，先检查 CPU online set、板态、reboot 影响。

4. `cockpit_native` 的 headline 仍引用旧一代 trusted current 结果
   这是文档一致性风险，不是代码 bug。
   若对外发布，应统一决定保留旧口径还是更新到 `2026-03-13` 的晚期 trusted current。

5. baseline live 与默认 operator branch 不是一回事
   `2026-03-17` 有 baseline live `300 / 300` 的历史证据；
   但 `2026-03-22` 之后 Scene 3 默认仍是 archived PyTorch reference。

6. safe runtime 环境很脆
   历史问题表明 `torch/libc10.so` 可能再次触发 `SIGILL` 相关问题。
   如非必要，不要跳过现有 safe wrapper 直接手搓 runtime。

7. 仓库当前工作树可能天然不干净
   接手者应假定：
   - 已有很多历史报告被跟踪
   - 也有很多运行时目录、草稿、LaTeX 中间件和本地缓存未清
   - 做发布整理时必须按类别处理，而不是一次性重置

8. 配置里可能含真实主机/IP/用户名/路径
   尤其是 `session_bootstrap/config/*.env`、README 和运行报告。
   GitHub 发布前必须逐项审查。

## 9. 推荐的前 1-2 天接手路径

### Day 1：理解边界，确认能跑最小链路

阅读顺序建议：

1. [README.md](README.md)
2. [EXPERT_HANDOFF.md](EXPERT_HANDOFF.md)
3. [session_bootstrap/runbooks/artifact_registry.md](session_bootstrap/runbooks/artifact_registry.md)
4. [session_bootstrap/PROGRESS_LOG.md](session_bootstrap/PROGRESS_LOG.md)
5. [session_bootstrap/reports/big_little_real_run_summary_20260318.md](session_bootstrap/reports/big_little_real_run_summary_20260318.md)
6. [session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md](session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md)
7. [session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md](session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md)

最小验证建议：

```bash
python3 -m unittest discover -s openamp_mock/tests -t .
python3 -m cockpit_native --smoke-import-check
python3 -m unittest discover -s ./session_bootstrap/demo/openamp_control_plane_demo/tests -p 'test_*.py'
```

若 `PySide6` 已安装，可继续：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
bash ./session_bootstrap/scripts/run_cockpit_native.sh
```

### Day 2：选一条线做真正复现

只选一条主线，不要并行三条都动：

1. 性能线
   从 [session_bootstrap/runbooks/artifact_registry.md](session_bootstrap/runbooks/artifact_registry.md) 出发，先复现一次 trusted current payload 或 real reconstruction。

2. OpenAMP demo 线
   从 [session_bootstrap/demo/openamp_control_plane_demo/README.md](session_bootstrap/demo/openamp_control_plane_demo/README.md) 和 [session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md](session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md) 出发，先跑 dashboard，再决定是否接 live probe。

3. 原生座舱线
   从 [cockpit_native/README.md](cockpit_native/README.md) 和 [session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md) 出发，先做彩排，再看是否需要统一 headline 和打包资产。

## 10. 术语表

- `baseline`
  历史基线实现。不同阶段里既出现过 legacy TVM compat 路径，也出现过 PyTorch reference/live 语义，必须看具体报告。

- `current`
  当前优化路线，通常指 TVM current artifact 和 safe runtime 路线。

- `trusted current`
  已经通过正式报告和 SHA guard 固定下来的 current artifact。当前顶层默认引用 SHA 是 `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`。

- `payload`
  偏向 `load + VM init + main()` 的推理口径，不含完整图像重建与输出保存语义。

- `real reconstruction`
  真实端到端图像重建口径，包含读取 latent、重建、写 PNG 等更完整流程。

- `current-safe`
  指 current artifact 走 safe runtime/guard 的执行路径。

- `compat runtime`
  历史 baseline/legacy 路线所依赖的兼容执行路径。

- `big.LITTLE pipeline`
  将不同阶段绑定到大小核 worker 并通过 pipeline overlap 提升吞吐的真机方案。

- `P0/P1 FIT`
  OpenAMP 控制面分层里程碑和正式功能/集成测试项。当前 evidence package 已收口到 `FIT-01/02/03 PASS`。

- `Scene 3`
  OpenAMP demo/cockpit 里的对比/演示场景；默认语义在后期收束为 archived PyTorch reference，而不是默认 baseline live。

## 11. 从哪里继续工作

### 11.1 如果目标是继续做性能优化

优先入口：

1. [session_bootstrap/runbooks/artifact_registry.md](session_bootstrap/runbooks/artifact_registry.md)
2. [session_bootstrap/runbooks/optimization_roadmap.md](session_bootstrap/runbooks/optimization_roadmap.md)
3. [session_bootstrap/runbooks/next_round_optimization_checklist.md](session_bootstrap/runbooks/next_round_optimization_checklist.md)

默认脚本：

- `run_inference_benchmark.sh`
- `run_phytium_current_safe_one_shot.sh`
- `run_phytium_baseline_style_current_rebuild.sh`
- `run_phytium_baseline_seeded_warm_start_current_incremental.sh`
- `run_big_little_first_real_attempt.sh`

### 11.2 如果目标是继续做 OpenAMP 控制面 / 演示

优先入口：

1. [session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md](session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md)
2. [session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md](session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md)
3. [session_bootstrap/demo/openamp_control_plane_demo/README.md](session_bootstrap/demo/openamp_control_plane_demo/README.md)

默认脚本：

- `run_openamp_demo.sh`
- `probe_openamp_board_status.py`
- `openamp_control_wrapper.py`
- `openamp_rpmsg_bridge.py`

### 11.3 如果目标是继续做原生座舱/现场演示包装

优先入口：

1. [cockpit_native/README.md](cockpit_native/README.md)
2. [session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_packet_index_2026-03-24.md)
3. [session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md](session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md)

需要尽快做的判断：

- 是否统一 headline 到最新 trusted current 结果
- 是否保留 `runtime/` 下现有静态包
- 是否把 `cockpit_native` 当作公开仓库内的演示组件，还是只保留源码，不发布生成交付包

### 11.4 如果目标是准备 GitHub 发布

先看：

- [GITHUB_PUBLISH_CHECKLIST.md](GITHUB_PUBLISH_CHECKLIST.md)

发布前核心动作不是写新代码，而是做三件事：

1. 划清源码、证据、纯运行产物边界
2. 审查真实主机/IP/路径/凭据痕迹
3. 统一公共叙事口径，避免 README、runbook、演示脚本分别引用不同代的 headline
