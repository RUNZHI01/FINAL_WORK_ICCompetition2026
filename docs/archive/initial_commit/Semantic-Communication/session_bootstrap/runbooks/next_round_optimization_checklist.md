# 下一轮性能优化执行清单（论文任务体系对齐版）

更新时间：`2026-03-12`  
来源：`paper/集创赛冲奖调优方案_2026-03-12.md`  
适用范围：飞腾派 TVM / MNN 下一轮冲奖调优。本文不是旧版“只围绕 current-safe 工程线”的顺序复述，而是把论文第 4-7 章任务体系，按第 10/11 章推荐的实际排期、依赖和风险分层，落成可执行 runbook。

---

## 0. 本清单与论文的对应关系

- 本清单直接派生自论文的任务系统：`P0 必做`、`P1 建议做`、`P2 加分项`、`硬核差异化方向`。
- 本清单的推荐执行顺序，以论文 **第 10 章“行动计划与排期”** 和 **第 11 章“最终执行方案 / 关键依赖关系”** 为唯一骨架。
- 本清单保留当前仓库里已经验证过的 trusted artifact / SHA / env / report 资产；这些不是附录，而是每个任务能否被接受的基线。
- 本清单只覆盖“下一轮优化”本身。论文里的 `6.2 端到端 Demo` 属于答辩收尾工作，不是本轮优化的主 gating item，因此在这里仅作为尾部备注，不纳入主执行链。

### 0.1 执行原则

- 所有比较都先锚定 trusted current 产物：`1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- 所有新结论都必须落到 `session_bootstrap/reports/` 下的独立新报告，不能只停留在终端输出。
- 不允许把多条高风险主线同时推进。每个阶段只允许一个主变量前进，其余工作以“采证 / 并行准备”为主。
- `5.1 算子级 profiling` 是 `4.2 更大 MetaSchedule 预算` 和 `7.1 手写 TIR + NEON` 的前置。
- `4.1 质量指标` 是 `4.3 TVM 量化` 的前置，也是 `6.1 多 SNR`、`7.4 RSSI 真信道版` 的评价基线。
- `5.3 资源分析` 要先于“继续加预算 / 上 TIR / 上量化”的大决策，避免在 CPU、内存或 I/O 已经成为瓶颈时继续盲打算子调优。
- `7.2 big.LITTLE 流水线` 与 `4.1 / 5.3 / 5.1` 相互独立，可以并行做。

---

## 1. 论文任务体系映射与本轮处理方式

### 1.1 P0 / P1 / P2 / 硬核方向映射

| 论文任务 | 级别 | 本轮处理方式 | 执行车道 | 关键依赖 | 本轮主交付物 |
|---|---|---|---|---|---|
| `4.1` 质量指标（PSNR / SSIM / LPIPS） | P0 | 必做 | 立即可做 | trusted 真实重建输出存在 | 质量报告 + 可写入论文的表格 |
| `5.3` 资源分析（功耗 / 内存 / CPU / 产物大小） | P1 | 建议优先前置 | 立即可做 | trusted current 产物可复跑 | 资源画像报告 |
| `7.2` big.LITTLE 异构流水线 | 硬核 | 早做，作为高 ROI 硬核方向 | 立即可做 | 核心拓扑确认 | 吞吐提升数据 + 流水线脚本 |
| `5.1` 算子级 profiling | P1 | 必须前置 | 立即可做 | trusted artifact / target 对齐 | hotspot 证据 + 后续 op 名单 |
| `4.2` 更大 MetaSchedule 预算 | P0 | 夜间长跑主任务 | 夜间长跑 | `5.1` 完成；RPC 正常 | 新 `.so` + 新 SHA + 验证报告 |
| `6.1` 多 SNR 测试 | P2 | 白天并行补数据 | 中风险白天并行 | `4.1` 质量度量流程可复用 | PSNR vs SNR 曲线 |
| `4.4` MNN 深度优化 | P0 | 白天并行推进 | 中风险白天并行 | MNN 工具链 / benchmark harness | MNN 从 `1.85x` 走向 `3-4x` 的数据 |
| `5.2` 跨框架对比（NCNN / ORT） | P1 | 第三阶段再做 | 中风险白天并行 | TVM current / MNN 数据已定稿更佳 | TVM vs MNN vs NCNN vs ORT 表格 |
| `7.4` RSSI 真信道版 | 硬核 | 第三阶段再做 | 中风险白天并行 | `4.1` 与 `6.1` 的评价链路已打通 | RSSI 采样 + 真信道质量对比 |
| `7.1` 手写 TIR + NEON | 硬核 | 后置，且必须基于热点 | 中风险迭代 | `5.1`，最好再参考 `4.2` 结果 | 手写 schedule 对比数据 |
| `4.3` TVM 量化 | P0 | 后置高风险试探 | 高风险后置 | `4.1` 完成；FP32 基线稳定 | INT8/FP16 试探结果或失败归档 |
| `7.5` 模型-硬件协同剪枝 | 硬核 | 明确延期 | 后续工作 | 训练数据 + GPU fine-tune | 只保留设计 |
| `7.3` 自定义 TVM Pass | 硬核 | 明确延期 | 后续工作 | Relax API 稳定性 | 只保留设计 |
| `6.3` TVM 动态形状 | P2 | 明确延期 | 后续工作 | 多 shape 独立调优 | 只保留方案 |

### 1.2 必须分开的四条执行车道

#### 立即可做

- `4.1` 图像质量指标
- `5.3` 资源分析
- `7.2` big.LITTLE 流水线
- `5.1` 算子级 profiling

#### 夜间长跑

- `4.2` MetaSchedule 扩预算

#### 中风险白天并行

- `6.1` 多 SNR 测试
- `4.4` MNN 深度优化
- `5.2` 跨框架横向对比
- `7.4` RSSI 真信道版
- `7.1` 手写 TIR + NEON

#### 高风险后置 / 明确延期

- 后置高风险：`4.3` TVM 量化
- 明确延期：`7.5`、`7.3`、`6.3`

---

## 2. 本轮统一可信基线（所有任务共用）

| 项目 | 固定值 | 本轮用途 |
|---|---|---|
| trusted current 本地产物 | `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so` | 本轮 TVM current 统一比较基线 |
| trusted current 本地文件大小 | `1653592` bytes | 资源分析的起始 size |
| trusted current SHA256 | `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644` | artifact 身份保护 |
| trusted current 远端路径 | `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so` | 飞腾派 current archive |
| trusted payload 报告 | `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md` | `1844.1 -> 153.778 ms` |
| trusted 真实端到端报告 | `session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301.md` | `1830.3 -> 255.931 ms/image` |
| trusted current-only payload 对比 | `session_bootstrap/reports/current_scheme_b_compare_20260311_195303.md` | `2479.246 -> 152.36 ms`，speedup `16.272x` |
| trusted 增量突破总结 | `session_bootstrap/reports/phytium_current_incremental_breakthrough_20260311.md` | 当前 trusted artifact 总入口 |
| payload 推荐 env 快照 | `session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.env` | 固定 `repeat=10`、`warmup=2`、payload runner |
| 真实端到端推荐 env 快照 | `session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env` | 固定 real reconstruction 语义 |
| 增量调优推荐 env | `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env` | `4.2` 的起点 |
| safe runtime guard 基础 env | `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env` | current SHA guard 基线 |
| 当前 hotspot 参考报告 | `session_bootstrap/reports/hotspot_tasks_20260311_0008.md` / `.json` | `5.1` 的已知起点 |
| trusted real reconstruction baseline 输出目录 | `/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_baseline/reconstructions` | `4.1` / `6.1` / `7.4` 的 baseline 图像来源 |
| trusted real reconstruction current 输出目录 | `/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_current/reconstructions` | `4.1` / `6.1` / `7.4` 的 current 图像来源 |

### 2.1 目前已经成立的已知结论

- payload 级 current-safe 正式结论：`153.778 ms`，方差 `1.100888`
- 真实端到端 current 正式结论：`255.931 ms/image`
- trusted current 产物输出 shape：`[1, 3, 256, 256]`
- 当前已知 task-stage hotspot 参考前列：`reshape2`、`fused_variance1_add3_tir_sqrt1`、`reshape1`、`fused_mean1_subtract1_divide1_multiply1_add4`、`fused_conv2d1_add2`、`fused_conv2d2_add2`

注意：

- 上面的 hotspot 名单来自 task-stage 权重，不等于最终 runtime 耗时排行。
- `7.1` 不能只看这份名单就开做，必须等待 `5.1` 的 runtime profiling 证据。

---

## 3. 开跑前统一门禁（所有阶段都先做）

### 3.1 本地 trusted artifact 与 SHA

命令模板：

```bash
sha256sum \
  session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so

stat -c '%s %n' \
  session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so
```

通过标准：

- SHA 必须等于 `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- 文件大小应记录为 `1653592` bytes；如果不同，先解释原因

失败判定：

- 文件不存在
- SHA mismatch
- 文件大小异常但没有对应的新报告 / 新 SHA

需要记录：

- `artifact_path`
- `artifact_sha256`
- `artifact_size_bytes`

### 3.2 关键 env 仍然 pin 到 trusted SHA

命令模板：

```bash
rg -n \
  'INFERENCE_CURRENT_EXPECTED_SHA256|INFERENCE_CURRENT_CMD|INFERENCE_BASELINE_CMD|INFERENCE_REPEAT|INFERENCE_WARMUP_RUNS|INFERENCE_OUTPUT_PREFIX|INFERENCE_LEGACY_OUTPUT_PREFIX|INFERENCE_EXECUTION_ID' \
  session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.env \
  session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
```

必须看到：

- payload env：
  - `INFERENCE_CURRENT_EXPECTED_SHA256=1946...c644`
  - `INFERENCE_CURRENT_CMD='bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current'`
  - `INFERENCE_REPEAT=10`
  - `INFERENCE_WARMUP_RUNS=2`
- real env：
  - `INFERENCE_CURRENT_EXPECTED_SHA256=1946...c644`
  - `INFERENCE_CURRENT_CMD='bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current'`
  - `INFERENCE_REPEAT=1`
  - `INFERENCE_WARMUP_RUNS=0`
  - `INFERENCE_OUTPUT_PREFIX=inference_real_reconstruction_compare_run_20260311_212301`

失败判定：

- current SHA guard 被改掉
- payload env 与 real reconstruction env 命令混写
- 准备用于本轮实验的 env 没有复制，而是直接覆写 trusted env

### 3.3 RPC readiness

命令模板：

```bash
bash session_bootstrap/scripts/check_rpc_readiness.sh \
  --env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
```

通过标准：

- 脚本退出码 `0`
- checklist 中无 blocker
- 能识别为 baseline-seeded warm-start current incremental 模式

### 3.4 RPC 服务状态

命令模板：

```bash
bash session_bootstrap/scripts/manage_rpc_services.sh \
  --env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  status
```

如未启动，再执行：

```bash
bash session_bootstrap/scripts/manage_rpc_services.sh \
  --env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  start-all
```

通过标准：

- tracker `LISTENING`
- runner `LISTENING`
- query 能看到 device

### 3.5 命名与覆写保护

执行规则：

- 每个任务都生成新的 `RUN_ID`
- trusted env 只复制，不原地覆盖
- 默认保持 `ALLOW_REPORT_OVERWRITE=0`
- 除非已经有新 SHA 验证报告，否则不更新 trusted registry

命令模板：

```bash
RUN_ID="$(date +%Y%m%d_%H%M%S)"
echo "$RUN_ID"
```

---

## 4. 推荐的实际执行顺序（严格按论文第 10 / 11 章）

### 4.1 阶段骨架

1. **阶段一：零依赖快速出数据**
   - `4.1` 质量指标
   - `5.3` 资源分析
   - `7.2` big.LITTLE 流水线
   - `5.1` 算子级 profiling
2. **阶段二：利用 profiling 结果做深挖**
   - `4.2` 更大 MetaSchedule 预算（夜间）
   - `6.1` 多 SNR 测试
   - `4.4` MNN 深度优化
3. **阶段三：横向对比 + 硬核方向**
   - `5.2` 跨框架对比
   - `7.4` RSSI 真信道版
   - `7.1` 手写 TIR + NEON
4. **阶段四：高风险试探**
   - `4.3` TVM 量化
5. **明确延期**
   - `7.5`、`7.3`、`6.3`

### 4.2 关键依赖图

```text
4.1 质量指标 ──→ 6.1 多 SNR
              └→ 7.4 RSSI 真信道版
              └→ 4.3 TVM 量化

5.3 资源分析 ──→ 判断下一轮重点是继续算子优化，还是先处理 I/O / 内存 / CPU 利用率

5.1 算子级 profiling ──→ 4.2 更大 MetaSchedule 预算（尤其是 --op-names）
                        └→ 7.1 手写 TIR + NEON

7.2 big.LITTLE 流水线：可与 4.1 / 5.3 / 5.1 并行

4.2 新产物 / 新热点证据：最好在 7.1 前拿到，避免手写 schedule 盲打旧瓶颈
```

### 4.3 本轮推荐节奏

- 白天先做“零依赖采证”：`4.1`、`5.3`、`7.2`、`5.1`
- 夜间只跑一个长任务：`4.2`
- 第二天白天并行补 `6.1` 与 `4.4`
- 第三阶段才进入横向对比和硬核深挖：`5.2`、`7.4`、`7.1`
- `4.3` 量化只在前面都已经有可交差数据后再试，不允许抢占前面阶段

---

## 5. 阶段一：立即可做（零依赖快速出数据）

### 5.1 任务 `4.1`：补充图像重建质量指标（PSNR / SSIM / LPIPS）

定位：

- 这是论文定义的 P0 必做项。
- 这是量化、真信道和多 SNR 的评价基线。
- 先把 FP32 current 与 baseline 的质量问题钉死，再讨论任何“更快是否掉质”的问题。

已知输入：

- trusted baseline 重建目录：`/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_baseline/reconstructions`
- trusted current 重建目录：`/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_current/reconstructions`
- latent 输入目录：`/home/user/Downloads/jscc-test/简化版latent`
- trusted 真实端到端报告：`session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301.md`

当前状态：

- 仓库内已补充 `session_bootstrap/scripts/compute_image_quality_metrics.py`。
- 该脚本按统一约定输出 `session_bootstrap/reports/<run_id>.md` 与 `session_bootstrap/reports/<run_id>.json`。
- `2026-03-30` 起，仓库还补了 `session_bootstrap/scripts/build_quality_matrix_report.py`，用于把多份 `quality_metrics_*.json` 收口成 judge-facing 正式质量报告。

执行计划：

1. 生成与 trusted real run 同一批 `300` 个 latent 对应的 PyTorch reference 重建图。
2. 保证 reference / baseline / current 三组图像文件名可一一对应。
3. 计算三组对比：
   - `PyTorch vs TVM baseline`
   - `PyTorch vs TVM current`
   - `TVM baseline vs TVM current`
4. 输出 `md + json` 双份报告，并把表格准备成可直接抄入论文的格式。

建议的运行接口：

```bash
RUN_ID="quality_metrics_$(date +%Y%m%d_%H%M%S)"
REF_DIR="/path/to/pytorch_reference_reconstructions"
BASE_DIR="/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_baseline/reconstructions"
CUR_DIR="/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_run_20260311_212301_current/reconstructions"

python3 session_bootstrap/scripts/compute_image_quality_metrics.py \
  --ref-dir "$REF_DIR" \
  --test-dir "$BASE_DIR" \
  --comparison-label "pytorch_vs_tvm_baseline" \
  --report-prefix "session_bootstrap/reports/${RUN_ID}_pytorch_vs_tvm_baseline"

python3 session_bootstrap/scripts/compute_image_quality_metrics.py \
  --ref-dir "$REF_DIR" \
  --test-dir "$CUR_DIR" \
  --comparison-label "pytorch_vs_tvm_current" \
  --report-prefix "session_bootstrap/reports/${RUN_ID}_pytorch_vs_tvm_current"

python3 session_bootstrap/scripts/compute_image_quality_metrics.py \
  --ref-dir "$BASE_DIR" \
  --test-dir "$CUR_DIR" \
  --comparison-label "tvm_baseline_vs_tvm_current" \
  --report-prefix "session_bootstrap/reports/${RUN_ID}_tvm_baseline_vs_tvm_current"
```

脚本要点：

- 默认比较同名 `PNG`，文件名不一致会直接报错；只有显式加 `--allow-mismatch` 才会退化为公共子集比较。
- 默认 `--size-mismatch crop`，尺寸不一致时裁到公共区域，并在报告中记录 `cropped_pair_count`。
- `--lpips auto` 为默认行为：环境里有 `torch + lpips` 时计算 LPIPS，否则继续产出 PSNR / SSIM 报告并在 md/json 里记录跳过原因。
- json 含每张图的明细；md 含 aggregate 表和可直接抄入论文的单行汇总。

通过标准：

- `PyTorch vs TVM baseline`：`PSNR >= 40 dB`、`SSIM >= 0.99`、`LPIPS <= 0.01`
- `PyTorch vs TVM current`：`PSNR >= 40 dB`、`SSIM >= 0.99`、`LPIPS <= 0.01`
- `TVM baseline vs current`：`PSNR >= 45 dB`、`SSIM >= 0.999`、`LPIPS <= 0.005`

失败 / 阻塞条件：

- 没有 PyTorch reference 图像
- 文件名或数量对不上 `300`
- trusted real reconstruction 输出被覆盖，无法确认比较对象
- `LPIPS` 环境缺包且无替代方案

本任务完成后必须产出：

- `session_bootstrap/reports/quality_metrics_<RUN_ID>.md`
- `session_bootstrap/reports/quality_metrics_<RUN_ID>.json`
- 一张可以直接进入论文的汇总表
- 如需答辩 / 评委材料总表，再执行：

```bash
python3 ./session_bootstrap/scripts/build_quality_matrix_report.py \
  --report-prefix ./session_bootstrap/reports/judge_quality_formal_report_$(date +%Y%m%d)
```

### 5.2 任务 `5.3`：资源分析（功耗 / 内存 / CPU / 产物大小）

定位：

- 这是论文建议第一天就补齐的 P1 数据。
- 本任务是“先搞清资源画像，再决定后续继续砸 compute 还是处理系统瓶颈”。

当前已知资产：

- trusted artifact size 已知：`1653592` bytes
- trusted payload 报告已知：`153.778 ms`
- trusted real reconstruction 报告已知：`255.931 ms/image`

执行策略：

- 当前仓库已有可直接复用的远端资源采样脚本：
  `session_bootstrap/scripts/run_remote_resource_profile.sh`
- 最小闭环是：先拿 **current trusted** 的资源画像；baseline / MNN / 量化行可以后补。

建议采集项：

- 运行前后内存快照：`free -h`
- 运行前后系统快照：`top -b -n 1`
- 运行期间系统级采样：`vmstat 1`
- 产物大小：`stat -c '%s'` / `ls -lh`
- 如没有外接功率计，则功耗列明确标记为“暂无板级功率计，当前只提供 CPU / 内存 / 产物大小”

建议命令模板：

```bash
sha256sum \
  session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so

stat -c '%s %n' \
  session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so
```

远端采样执行计划：

1. 以 trusted current artifact 为对象，运行：
   `bash ./session_bootstrap/scripts/run_remote_resource_profile.sh`
2. 该脚本默认走 trusted env，并在目标命令运行期间并行启动 `vmstat`，同时采集前后 `free -h` / `top -b -n 1`。
3. 采集的最小原始文件：
   - `target.command.log`
   - `vmstat.log`
   - `free_pre_h.txt` / `free_post_h.txt`
   - `top_pre.txt` / `top_post.txt`
4. 汇总生成：
   - `session_bootstrap/reports/resource_profile_<RUN_ID>.md`
   - `session_bootstrap/reports/resource_profile_<RUN_ID>.json`
   - `session_bootstrap/reports/resource_profile_<RUN_ID>/`

通过标准：

- 至少拿到 current trusted 的 `系统内存快照 / CPU+等待占比趋势 / artifact size`
- 报告里明确指出瓶颈更像 compute、memory 还是 I/O
- 如果 CPU 低利用率或 I/O 明显拖累，后续 `7.2`、真实端到端优化优先级上升

失败 / 阻塞条件：

- 只能测到本地 SSH wrapper，测不到板端进程资源
- 输出目录被旧 run 覆盖
- 资源采样窗口过短，无法覆盖 300 张数据的 steady state

### 5.3 任务 `7.2`：big.LITTLE 异构流水线

定位：

- 这是论文推荐第一天就启动的硬核方向。
- 目标不是降低单张 `model_run_ms`，而是把 `read latent -> decode -> write PNG` 的吞吐量做成真正的系统优化亮点。

为什么现在做：

- 与 `4.1`、`5.3`、`5.1` 独立，不会互相阻塞。
- trusted real reconstruction 已给出当前串行基线：`255.931 ms/image`

输入：

- trusted current 远端 artifact：`/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- trusted real 输入目录：`/home/user/Downloads/jscc-test/简化版latent`
- trusted current 输出语义：`run_remote_current_real_reconstruction.sh --variant current`

当前状态：

- 仓库内还没有 `big_little_pipeline.py`
- 因此本任务按实现计划推进

必须先确认的基础信息：

```bash
lscpu
lscpu -e=CPU,CORE,SOCKET,NODE,MAXMHZ,MINMHZ
```

执行计划：

1. 在飞腾派确认大核 / 小核编号，以及 `sched_setaffinity` 是否可用。
2. 新建 `session_bootstrap/scripts/big_little_pipeline.py`：
   - 大核：TVM 推理
   - 小核：latent 预加载、输出保存
3. 使用与 trusted real reconstruction 完全相同的 `300` 个 latent 输入、相同 artifact、相同输出格式跑一轮。
4. 对比：
   - 串行 trusted real reconstruction：`255.931 ms/image`
   - 流水线版本的总耗时、吞吐、文件数、图像质量

最小交付物：

- `session_bootstrap/scripts/big_little_pipeline.py`
- `session_bootstrap/reports/big_little_pipeline_<RUN_ID>.md`
- `session_bootstrap/reports/big_little_pipeline_<RUN_ID>.json`

通过标准：

- 输出数量仍为 `300`
- 图像结果与 current trusted 在质量上等价，不引入新误差
- 批量吞吐提升达到论文建议区间的下界：优先目标 `>= 25%`

失败 / 阻塞条件：

- 无法确认核心拓扑
- `sched_setaffinity` 失败或权限不足
- 推理与 I/O 解耦后出现丢图 / 重图 / 顺序错乱

### 5.4 任务 `5.1`：算子级 profiling 热点分析

定位：

- 这是后续 `4.2` 和 `7.1` 的真正前置。
- 这一步不做，后面的扩预算和手写 TIR 都是在盲打。

当前可直接复用的脚本：

- `session_bootstrap/scripts/extract_hotspot_tasks.py`

第一层：先重新生成 task-stage hotspot 报告

命令模板：

```bash
RUN_ID="hotspot_tasks_$(date +%Y%m%d_%H%M%S)"

python session_bootstrap/scripts/extract_hotspot_tasks.py \
  --env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  --top-k 8 \
  --output "session_bootstrap/reports/${RUN_ID}.md" \
  --json-output "session_bootstrap/reports/${RUN_ID}.json"
```

通过标准：

- `recommended_full_hotspot_tasks` 非空
- 至少拿到 `top 3-8` 个 task
- 与参考报告 `session_bootstrap/reports/hotspot_tasks_20260311_0008.md` 对比时，差异可解释

第二层：补 runtime 级 profiling

说明：

- 论文要的是“瓶颈算子耗时占比”，不仅是 task-stage 权重。
- 当前仓库没有现成的 runtime profiling 包装脚本，因此这里按执行计划推进。

执行计划：

1. 优先尝试 `vm.profile("main", input_data)`。
2. 若 TVM 0.24 当前环境不可用，则退回：
   - 手工插桩
   - 或 `perf stat`
   - 或围绕热点 task 的 micro / partial benchmark
3. 最终输出一张“算子 / fused op / PrimFunc”耗时分布表，能回答：
   - 哪些算子最慢
   - 占比多少
   - 与 `extract_hotspot_tasks.py` 的 stage 权重是否一致

特别注意：

- 目前已有参考 hotspot 排名里，`reshape2` / `variance` / `mean` 排位靠前；这提示“stage 权重”未必等于“runtime 最贵算子”。
- `7.1` 绝不能只凭当前 hotspot markdown 直接锁定 conv2d，必须等待 runtime 证据。

本任务完成后的强制输出：

- `session_bootstrap/reports/profiling_<RUN_ID>.md`
- `session_bootstrap/reports/profiling_<RUN_ID>.json`
- 一个用于 `4.2` 的 `FULL_HOTSPOT_TASKS` 候选列表
- 一个用于 `7.1` 的 top-1 / top-2 runtime hotspot 名单

---

## 6. 阶段二：profiling 驱动的深挖（夜间长跑 + 白天并行）

### 6.1 任务 `4.2`：MetaSchedule 扩预算（明确依赖 `5.1`）

定位：

- 这是论文 P0 主线，但必须放在 `5.1` 之后执行。
- 先拿到 profiling / hotspot 证据，再决定是全局扩预算还是 `--op-names` 定向深搜。

原则：

- 第一个夜跑仍然沿 trusted current 的现有工程线推进，不跳线。
- 先从 `500 -> 1000` 做增量验证，再根据 `5.1` 结果决定是否进入 `2000-3000` 的热点定向搜索。

#### 6.1.1 夜间第一步：从 `500` 增到 `1000`

命令模板：

```bash
RUN_ID="phytium_baseline_seeded_warm_start_current_incremental_1000_$(date +%Y%m%d_%H%M%S)"

bash session_bootstrap/scripts/manage_rpc_services.sh \
  --env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  start-all

bash session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh \
  --rebuild-env session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  --inference-env session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env \
  --total-trials 1000 \
  --report-id "$RUN_ID" \
  --repeat 10 \
  --warmup-runs 2
```

通过标准：

- 生成新目录：`session_bootstrap/tmp/${RUN_ID}/`
- 生成新 `.so`
- wrapper 明确落盘
- 若命中旧 SHA guard，不视为调优失败，只说明需要单独做新 SHA 验证

#### 6.1.2 第二步：基于 `5.1` 结果做热点定向深搜

说明：

- 这一轮才真正对齐论文的“profiling 后再定向加预算”原则。
- 不要在 `5.1` 没完成时就盲目开 `2000-3000 trials + --op-names`

建议模板：

```bash
RUN_ID="phytium_baseline_seeded_warm_start_current_incremental_hotspot_$(date +%Y%m%d_%H%M%S)"
ENV_COPY="session_bootstrap/tmp/${RUN_ID}.env"
FULL_HOTSPOTS="<用 5.1 最终确认的 top-3~top-5 task 名单，逗号分隔>"

cp session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env "$ENV_COPY"

sed -i \
  -e "s#^TUNE_TOTAL_TRIALS=.*#TUNE_TOTAL_TRIALS=2000#" \
  -e "s#^TUNE_OUTPUT_DIR=.*#TUNE_OUTPUT_DIR=./session_bootstrap/tmp/${RUN_ID}#" \
  "$ENV_COPY"

cat >> "$ENV_COPY" <<EOF
TUNE_OP_NAMES=${FULL_HOTSPOTS}
EOF

bash session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh \
  --rebuild-env "$ENV_COPY" \
  --inference-env session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env \
  --report-id "$RUN_ID" \
  --repeat 10 \
  --warmup-runs 2
```

#### 6.1.3 新 SHA 验证（命中旧 guard 时必须立刻做）

命令模板：

```bash
NEW_ARTIFACT="session_bootstrap/tmp/${RUN_ID}/optimized_model.so"
NEW_SHA="$(sha256sum "$NEW_ARTIFACT" | awk '{print $1}')"
VALIDATE_ID="inference_compare_currentsafe_validate_$(date +%Y%m%d_%H%M%S)"
ENV_COPY="session_bootstrap/tmp/${VALIDATE_ID}.env"

cp session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.env "$ENV_COPY"
sed -i \
  -e "s#^INFERENCE_EXECUTION_ID=.*#INFERENCE_EXECUTION_ID=${VALIDATE_ID}#" \
  -e "s#^INFERENCE_CURRENT_EXPECTED_SHA256=.*#INFERENCE_CURRENT_EXPECTED_SHA256=${NEW_SHA}#" \
  -e "s#^ALLOW_REPORT_OVERWRITE=.*#ALLOW_REPORT_OVERWRITE=0#" \
  "$ENV_COPY"

bash session_bootstrap/scripts/run_inference_benchmark.sh --env "$ENV_COPY"
```

晋升 trusted 的最低门槛：

- 相比 trusted payload `153.778 ms`，有稳定收益 `> 3%`
- 或性能持平但 tail / variance 更优

失败 / 阻塞条件：

- `5.1` 未完成却硬开热点定向
- readiness / services 不稳定
- 新 `.so` 生成了但没有新 SHA 验证
- 只看单次最优值，不看 variance 和 repeat

### 6.2 任务 `6.1`：多 SNR 鲁棒性测试

定位：

- 这是论文第二阶段的 P2 加分项。
- 这个任务要复用 `4.1` 的质量评价管线；没有质量指标就不要开跑。

推荐 SNR 点位：

- `1`
- `4`
- `7`
- `10`
- `13`

命令模板（先跑 current trusted real reconstruction）：

```bash
for snr in 1 4 7 10 13; do
  RUN_ID="snr_${snr}_$(date +%Y%m%d_%H%M%S)"
  ENV_COPY="session_bootstrap/tmp/${RUN_ID}.env"
  cp session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env "$ENV_COPY"
  sed -i \
    -e "s#^INFERENCE_EXECUTION_ID=.*#INFERENCE_EXECUTION_ID=${RUN_ID}#" \
    -e "s#^INFERENCE_OUTPUT_PREFIX=.*#INFERENCE_OUTPUT_PREFIX=${RUN_ID}#" \
    -e "s#^INFERENCE_LEGACY_OUTPUT_PREFIX=.*#INFERENCE_LEGACY_OUTPUT_PREFIX=${RUN_ID}#" \
    -e "s#^REMOTE_SNR_CURRENT=.*#REMOTE_SNR_CURRENT=${snr}#" \
    "$ENV_COPY"
  bash session_bootstrap/scripts/run_inference_benchmark.sh --env "$ENV_COPY"
done
```

后续必须补的评价动作：

- 对每个 `snr` 的 current 输出目录，用 `4.1` 的质量脚本计算 `PSNR / SSIM / LPIPS`
- 汇总成 `snr -> metrics` 曲线
- `2026-03-30` 起，优先用 `session_bootstrap/scripts/build_snr_robustness_report.py` 汇总历史 / 新补采的 SNR 点，并输出 `md + json + svg`

本任务输出：

- 每个 SNR 各一份 inference report
- 一份汇总 `session_bootstrap/reports/snr_sweep_<RUN_ID>.md`
- 一份机器可读 `session_bootstrap/reports/snr_sweep_<RUN_ID>.json`
- 一张 `PSNR vs SNR` 曲线图
- judge-facing 汇总入口：

```bash
python3 ./session_bootstrap/scripts/build_snr_robustness_report.py \
  --summary-md ./session_bootstrap/reports/snr_sweep_<RUN_ID>.md \
  --report-prefix ./session_bootstrap/reports/judge_snr_robustness_$(date +%Y%m%d)
```

通过标准：

- 每个 SNR 点都成功处理 `300` 个输入
- 指标曲线单调趋势合理，无明显异常点
- 文档中能说清楚“速度不随 SNR 明显变化，质量随 SNR 变化”

失败 / 阻塞条件：

- `4.1` 尚未产出可复用的质量计算脚本 / 流程
- 不同 SNR 点输出目录混写
- 输出数量不足 `300`

### 6.3 任务 `4.4`：MNN 深度优化

定位：

- 这是论文 P0 项，但不应抢占 TVM 主线的夜跑窗口。
- 第二阶段白天推进最合适：一边等 `4.2` 夜跑结果，一边补 MNN 竞争力数据。

当前已知 MNN 基线：

- 论文当前状态：`300` 张不同尺寸图片，总耗时 `123 s`，单张约 `410 ms`
- 当前加速比：`1.85x`

执行目标：

- 把 MNN 结果推到论文建议的 `3-4x` 区间，或至少给出“尝试了哪些深度优化、有效哪些、无效哪些”的完整证据链。

建议推进顺序：

1. `FP16` 转换
2. 线程数实验（至少 `1 / 2 / 4`）
3. 半自动搜索 / benchmark 首轮搜索
4. 若有校准数据，再尝试 `INT8`

命令模板（转换侧）：

```bash
./MNNConvert \
  --modelFile decoder_dynamic.onnx \
  --MNNModel decoder_fp16.mnn \
  --framework ONNX \
  --fp16

./MNNConvert \
  --modelFile decoder_dynamic.onnx \
  --MNNModel decoder_int8.mnn \
  --framework ONNX \
  --weightQuantBits 8 \
  --weightQuantAsymmetric
```

命令模板（benchmark / 搜索侧）：

```bash
./benchmark.out models/ 10 2 4 0
./timeProfile.out decoder_fp16.mnn 10 4
```

当前仓库状态说明：

- 仓库内还没有统一的 MNN benchmark harness；如果现有 MNN 代码在别处，先锁定一套统一输入集和统一计时口径，再汇总到本仓库报告目录。
- 若要做 `INT8`，必须复用 `4.1` 的质量评价标准，避免只报速度。

本任务完成后的交付物：

- `session_bootstrap/reports/mnn_deep_opt_<RUN_ID>.md`
- `session_bootstrap/reports/mnn_deep_opt_<RUN_ID>.json`
- 一张配置对比表：`FP32 / FP16 / INT8`、线程数、是否搜索、速度、质量

通过标准：

- 至少完成 `FP16 + 多线程 + 搜索` 三维实验矩阵
- 选出当前 MNN 最优配置
- 若做了低精度，必须给出质量结论

失败 / 阻塞条件：

- benchmark 口径与论文旧数据不一致
- 只报速度，不报质量
- INT8 没有校准数据却硬上

---

## 7. 阶段三：横向对比 + 硬核方向

### 7.1 任务 `5.2`：跨框架横向对比（NCNN / ONNX Runtime）

定位：

- 这是论文第三阶段的 P1 项。
- 必须等 TVM current 与 MNN 结果相对稳定后再做，否则横向对比表会反复重算。

TVM / MNN 已知可预填行：

- TVM current payload：`153.778 ms`
- TVM current real reconstruction：`255.931 ms/image`
- MNN 当前已知：约 `410 ms`

目标：

- 构建一张最小但可信的比较表：`PyTorch / TVM / MNN / NCNN / ORT`

NCNN 命令模板：

```bash
git clone https://github.com/Tencent/ncnn.git
cd ncnn && mkdir build && cd build
cmake -DCMAKE_TOOLCHAIN_FILE=../toolchains/aarch64-linux-gnu.toolchain.cmake \
      -DNCNN_BUILD_BENCHMARK=ON ..
make -j4

python -m onnx2ncnn temp_simp.onnx decoder.param decoder.bin
./benchncnn decoder.param 10 4 0 0
```

ONNX Runtime 命令模板：

```bash
pip install onnxruntime

python - <<'PY'
import onnxruntime as ort
import numpy as np
import statistics
import time

sess = ort.InferenceSession("temp_simp.onnx", providers=["CPUExecutionProvider"])
inp = np.random.randn(1, 32, 32, 32).astype("float32")

for _ in range(5):
    sess.run(None, {"input": inp})

times = []
for _ in range(100):
    t0 = time.perf_counter()
    sess.run(None, {"input": inp})
    times.append((time.perf_counter() - t0) * 1000)

print("median_ms", statistics.median(times))
print("mean_ms", statistics.mean(times))
PY
```

执行要求：

- 输入形状固定为 `1,32,32,32`
- 所有框架都明确记录：模型格式、精度、线程数、warmup、repeat
- 结果最终统一落到 `session_bootstrap/reports/cross_framework_<RUN_ID>.md`

通过标准：

- 至少完成 `TVM / MNN / NCNN / ORT` 四行有效数据
- 所有行的计时口径可解释
- 论文里能够回答“为什么 TVM / MNN 值得选”

失败 / 阻塞条件：

- 不同框架的输入口径不一致
- NCNN / ORT 只测本地 x86，不测飞腾派
- 对比表里 TVM / MNN 不是 trusted / latest validated 结果

### 7.2 任务 `7.4`：真实信道 RSSI 版

定位：

- 论文第三阶段硬核方向。
- 这不是直接替代 AWGN，而是把“理想 AWGN”扩展为“基于飞腾派 WiFi RSSI 的实测信道近似”。

前置：

- `4.1` 的质量评价流程必须通
- 最好先完成 `6.1`，因为 `7.4` 本质上会复用 `SNR -> 质量` 这条分析链

采样命令模板：

```bash
while true; do
  iw dev wlan0 station dump | grep -E "signal|rx bitrate|tx bitrate"
  sleep 0.1
done > wifi_channel_log.txt
```

执行计划：

1. 在飞腾派采集一段稳定的 WiFi RSSI 日志。
2. 把 RSSI 映射为等效 SNR 分布。
3. 用该分布替换原固定 SNR 的 AWGN 设置，驱动 real reconstruction。
4. 复用 `4.1` / `6.1` 的质量脚本计算真信道下的质量指标。

最小交付物：

- `wifi_channel_log.txt`
- `session_bootstrap/reports/rssi_channel_<RUN_ID>.md`
- `session_bootstrap/reports/rssi_channel_<RUN_ID>.json`
- 一张 `AWGN vs RSSI-realized channel` 对比表

通过标准：

- 采样日志可解析
- 真信道实验至少跑通 `300` 个输入
- 有一组可以进入论文的对比：`AWGN 10dB` vs `RSSI 实测近似信道`

失败 / 阻塞条件：

- `iw` 在板子上不可用或驱动不支持
- RSSI 日志无法稳定映射出可用 SNR 分布
- 没有质量指标，只剩“跑过了但不知道好坏”

### 7.3 任务 `7.1`：手写 TensorIR Schedule + ARM NEON

定位：

- 这是论文里最能体现“优化深入到指令 / cache / schedule 层”的硬核方向之一。
- 但它必须后置，因为没有 `5.1` 的 runtime hotspot 证据就不知道该手写谁。

必须满足的前置：

- `5.1` 完成，并明确 top-1 / top-2 runtime hotspot
- 最好已有 `4.2` 的新热点证据，避免手写到已经不是瓶颈的 task

当前提醒：

- 现有 task-stage hotspot 报告把 `reshape` / `variance` / `mean` 排得很高；这不必然等于最终最值得写 TIR 的算子。
- 论文理论上预期 `conv2d / deconv` 是热点，但是否成立，必须以 `5.1` 的 runtime 数据为准。

执行计划：

1. 从 `5.1` 产物中锁定 `top-1` 真实瓶颈算子。
2. 提取对应 PrimFunc / TIR 结构。
3. 按论文建议，围绕 Cortex-A72 的：
   - `L1 32KB`
   - `NEON 128-bit`
   - tile / vectorize / unroll
   做手工 schedule。
4. 与 MetaSchedule 最优结果对比，验证是否有额外收益。

当前仓库执行要求：

- 新代码 / 试验报告必须落入 `session_bootstrap/` 体系
- 不得直接覆盖 trusted current artifact
- 若只是实验 schedule，可先单独导出 benchmark 结果，不急于并入主线

最小交付物：

- 手写 schedule 代码
- 一份 benchmark 报告
- 一张“手写 schedule vs MetaSchedule”的对比表

通过标准：

- 至少在 `top-1` 热点上拿到稳定可复验结果
- 相比 MetaSchedule 自动最优有正收益，或至少有可解释的失败结论
- 代码与硬件参数的对应关系能直接用于答辩说明

失败 / 阻塞条件：

- 热点选错
- 只做理论 schedule，没有真机 benchmark
- 为了手写 TIR 去破坏 current trusted 主线

---

## 8. 阶段四：高风险后置任务

### 8.1 任务 `4.3`：TVM 量化（INT8 / FP16，明确后置）

定位：

- 这是论文 P0，但也是全部任务里风险最高的一项。
- 本清单明确将其放在最后，不允许抢占 `4.1 / 5.1 / 4.2 / 7.2 / 4.4` 的窗口。

强制前置：

- `4.1` 必须先完成，且有 FP32 质量基线
- trusted FP32 主线必须仍稳定可复跑
- 最好已经完成 `5.3`，知道当前是否真的是 compute / memory 瓶颈

为什么后置：

- TVM 0.24dev / Relax 量化 API 仍有不稳定风险
- 如果没有质量基线，量化结果即使更快也无法被采信

执行顺序建议：

1. 先试 Relay PTQ
2. 若 INT8 不通或精度不行，再试 FP16
3. 如果两天内没有成型结果，立即转入“后续工作”表述，不继续吞时间

当前建议方案接口：

- 产物名与 FP32 主线分开：
  - `optimized_model_int8.so`
  - `optimized_model_fp16.so`
- 报告名分开：
  - `session_bootstrap/reports/tvm_quant_int8_<RUN_ID>.md`
  - `session_bootstrap/reports/tvm_quant_fp16_<RUN_ID>.md`

量化后的强制验证：

1. 新 SHA 记录
2. payload benchmark
3. real reconstruction benchmark
4. `4.1` 同口径质量验证

可接受质量阈值（按论文）：

- `PSNR >= 28 dB`
- `SSIM >= 0.90`

通过标准：

- 至少一条量化路线成功跑通
- 有速度提升和质量结论
- 不覆盖 trusted FP32 artifact

失败 / 阻塞条件：

- 没有 `4.1` 基线
- 新产物只测速度不测质量
- 两天内跑不通还继续死磕

若失败，报告里应明确写：

- 已尝试的 API / 路线
- 卡在哪一层
- 为什么当前赛期内不继续追
- 用 `4.4` 的 MNN 量化结果替代回答“量化做了吗”的评审问题

---

## 9. 明确延期 / 后续工作（与论文保持一致）

### 9.1 `7.5` 模型-硬件协同剪枝

延期原因：

- 需要训练数据
- 需要 GPU fine-tune
- 本质上是独立训练子项目，不是赛前冲刺期的“下一轮优化”

### 9.2 `7.3` 自定义 TVM 编译器 Pass

延期原因：

- Relax API 变化快
- 调试周期不可控
- 创新价值高，但 ROI 不适合当前赛期窗口

### 9.3 `6.3` TVM 动态形状

延期原因：

- 每个 shape 需要独立调优
- ROI 低
- MNN 路线已经承担动态形状需求

统一文档策略：

- 这些方向不删除
- 只保留方案设计与后续工作说明
- 评审追问时强调“有完整设计，但赛期内优先级低于当前可落地结果”

---

## 10. 每轮实验统一记录模板

```md
# Next Round Experiment Log

- 日期：
- 论文任务编号：4.1 / 5.3 / 7.2 / 5.1 / 4.2 / 6.1 / 4.4 / 5.2 / 7.4 / 7.1 / 4.3
- 阶段：阶段一 / 阶段二 / 阶段三 / 阶段四
- run_id：
- env：
- local_artifact：
- remote_artifact：
- expected_sha256：
- actual_sha256：
- trusted_refs：
  - session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md
  - session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301.md
- 输入：
  - model / artifact：
  - input_dir：
  - shape / dtype：
  - SNR（如适用）：
- 输出：
  - report_md：
  - report_json：
  - raw_csv / raw_log：
- 关键结果：
  - payload_median_ms：
  - real_median_ms：
  - variance_ms2：
  - output_count：
  - quality_metrics：
  - hotspot_topk：
  - resource_summary：
- 结论：通过 / 持平 / 回退 / 不可信 / 阻塞
- 下一动作：
```

出发前勾选：

- [ ] 本轮任务已映射到论文编号
- [ ] 仍锚定 trusted SHA `1946...c644`
- [ ] 使用的是 trusted env 复制版，不是原地覆盖
- [ ] 新 `RUN_ID` 不覆盖旧报告
- [ ] 若生成新 `.so`，已安排新 SHA 验证
- [ ] 跑完后会落 `session_bootstrap/reports/`

---

## 11. 本轮执行结论（给自己看的短版）

- 先做：`4.1`、`5.3`、`7.2`、`5.1`
- 夜里只跑：`4.2`
- 第二天白天补：`6.1`、`4.4`
- 第三阶段再开：`5.2`、`7.4`、`7.1`
- 最后才试：`4.3`
- 明确不在本轮死磕：`7.5`、`7.3`、`6.3`

不要打乱顺序。  
这不是“流程保守”，而是论文已经明确给出的依赖关系：先拿质量、资源、热点证据，再扩大预算、做硬核优化、最后才碰量化。
