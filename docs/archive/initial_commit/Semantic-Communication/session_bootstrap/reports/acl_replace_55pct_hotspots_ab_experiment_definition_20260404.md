# ACL 替换 55% 热点算子 vs 当前 MetaSchedule+handwritten 路线 A/B 对比实验定义

- date: 2026-04-04
- status: experiment-definition
- stage: `Opus 方案 / Phase 3 参考与突破实验`
- authority: `session_bootstrap/reports/opus_optimization_breakthrough_plan_20260403.md`

## 1. 目的

本实验的目标不是直接升级 Trusted Current，也不是把 stock ACL 直接宣布为当前主线替代品。

本实验的目标只有一个：

> 在严格遵守 `opus_optimization_breakthrough_plan_20260403.md` 约束的前提下，比较“当前 MetaSchedule+handwritten 路线”与“ACL 介入时长占比约 55% 的三条 transpose 热点算子”两条路线，判断 ACL 是否具备继续投入为 `conv2d_transpose` 突破方向的证据价值。

因此，本实验属于：

- **Phase 3 的参考/突破实验**
- **不触发 Trusted Current 升级**
- **所有产物必须与 Trusted Current 完全隔离**

## 2. Trusted Current 安全边界

以下规则直接继承自 `opus_optimization_breakthrough_plan_20260403.md`：

- Trusted current artifact 不可覆盖
- Trusted current SHA 不可修改
- 新产物必须输出到独立目录
- 飞腾板远端目录必须使用独立目录
- 任一步性能/正确性回退，直接丢弃候选

Trusted Current 基线：

- payload: `130.219 ms`
- e2e: `230.339 ms/image`
- artifact: `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- sha256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## 3. 55% 热点的定义

本实验中的“55% 热点”来自：

- `session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md`

三条热点如下：

| hotspot | runtime share | reference duration |
|---|---:|---:|
| `fused_conv2d_transpose1_add9` | `21.61%` | `~27.5 ms` |
| `fused_conv2d_transpose2_add12` | `17.68%` | `~22.5 ms` |
| `fused_conv2d_transpose_add6` | `16.00%` | `~20.4 ms` |
| **sum** | **55.29%** | — |

这三条是本实验唯一允许被称为“55% 热点”的对象。

## 4. A/B 两侧的正式定义

### A 侧：当前 MetaSchedule+handwritten 路线

A 侧代表项目当前已经成立、且与主线叙事一致的路线：

1. Trusted Current 的真实 profiling/top-op 证据
2. 已验证的 handwritten 候选与集成候选
3. 当前 `MetaSchedule + handwritten` 的有效结果集合

A 侧的主要数据来源：

- `session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md`
- `session_bootstrap/reports/opus_candidate_microbenchmark_results_20260403.md`
- `session_bootstrap/reports/opus_optimization_breakthrough_plan_20260403.md`

A 侧本实验中允许 claim 的内容：

- 当前 TVM 路线下，这三条热点的 runtime 占比与参考耗时
- 当前 handwritten 候选在独立 benchmark 或候选集成中的已知收益/回退
- 当前主线仍以 TVM 路线为准

### B 侧：ACL 介入路线

B 侧不是“已经成功替换 current 主线的 ACL 后端”，而是：

> 使用已编译完成的 ACL 库，对上述三条 `conv2d_transpose` 热点进行参考性替换/映射测试，用来判断 ACL 是否值得继续作为 Phase 3 突破方向推进。

B 侧的主要数据来源：

- `session_bootstrap/reports/acl_source_analysis_20260404.md`
- `session_bootstrap/reports/acl_f32_deconvolution_first_benchmark_20260404.md`

## 5. ACL 当前已确认边界

截至本定义落盘时，ACL 线已经确认：

1. ACL 已在飞腾派编译成功
2. 自定义 `F32` deconvolution benchmark 已成功运行
3. stock ACL `NEDeconvolutionLayer` 的输出尺寸由 `deconvolution_output_dimensions()` 决定
4. 当前 API **没有**可直接把 `63/127/255` 补成 `64/128/256` 的 `output_padding` 风格参数

因此，对于下列目标 shape：

- `64 -> 128`
- `128 -> 256`
- `32 -> 64`

stock ACL 在当前测试路径下自然得到的是：

- `64 -> 127`
- `128 -> 255`
- `32 -> 63`

这意味着：

> **当前 ACL 结果是“可运行参考”，不是“与 TVM 热点严格同语义的直接替换结果”。**

## 6. 本实验允许的两层口径

为避免乱做，本实验拆成两层，且必须分开报告。

### 层 1：Reference-layer A/B（允许立即执行）

这是当前最小、最诚实、最符合 Opus Phase 3 语义的一层。

#### A 侧测什么
- 直接引用 profiling 中三条热点的 TVM 参考耗时
- 必要时补跑当前 TVM hotspot microbenchmark

#### B 侧测什么
- 使用 ACL 自定义 `F32` deconvolution benchmark
- 对三条 hotspot 的对应 shape 做最接近映射的参考测量
- 保留 output shape mismatch 与语义边界说明

#### 层 1 允许 claim
- ACL 在飞腾派上可编译、可运行、可得到三条 transpose-like 的第一手数
- ACL 在这三条 shape-like case 上，相对 TVM hotspot reference 是“快/慢/不可直接公平比较”
- ACL 是否值得继续推进为 Phase 3 突破方向

#### 层 1 不允许 claim
- “ACL 已经替换当前 55% 热点并且更快”
- “ACL 已经可以直接集成进当前 trusted current”
- “ACL 已经在整模型 e2e 上优于 current”

### 层 2：Breakthrough-layer A/B（只有补齐语义后才允许）

只有在以下至少一个条件成立时，才能进入层 2：

1. ACL 侧实现能严格复现 `128/256/64` 输出几何与相关语义
2. 有明确的 shape adaptation / semantic normalization 方法，并经书面说明
3. 真正完成了局部替换集成，而不是仅做 standalone deconvolution reference

#### 层 2 允许做的事
- 构造更公平的 hotspot-level A/B
- 尝试局部替换/包裹某个 transpose op
- 再决定是否值得投入更重的 BYOC / custom call / TIR 反哺

#### 层 2 之前不该做的事
- 直接把 stock ACL benchmark 当作 current 的可替换实现
- 拿 `127/255/63` 结果硬宣称打赢 `128/256/64` 的 TVM hotspot

## 7. 本轮执行计划

本轮按层 1 执行，步骤固定如下：

1. 固定 A 侧参考值
   - 从 `profiling_judge_expanded_10samples_20260403.md` 提取三条热点的 reference duration/share
2. 固定 B 侧 ACL 参考值
   - 使用 `acl_f32_deconvolution_first_benchmark_20260404.md` 中已得到的三条数
3. 形成第一版 A/B 结果表
   - 每条 case 标注：`ACL slower` / `ACL faster-but-not-fair` / `inconclusive`
4. 给出是否值得继续推进 ACL 的工程判断
   - 仅判断“是否值得继续 Phase 3 投入”
   - 不触发 Trusted Current 升级

## 8. 第一版 claim matrix

| claim | 当前是否允许 |
|---|---|
| ACL 在飞腾派上已编译成功 | 允许 |
| ACL F32 deconvolution 已实测可跑 | 允许 |
| ACL 对 transpose1-like 当前慢于 TVM hotspot reference | 允许 |
| ACL 对 transpose2-like 当前慢于 TVM hotspot reference | 允许 |
| ACL 对 transpose_add6-like 当前数值上更快，但 shape 不公平 | 允许，必须附边界 |
| ACL 已直接替换 55% 热点并优于 current | **不允许** |
| ACL 已具备升级 Trusted Current 资格 | **不允许** |
| 当前应把 ACL 作为 Phase 3 继续观察方向 | 允许 |

## 9. 直接可复用的当前数值

### TVM hotspot reference

- `fused_conv2d_transpose1_add9`: `~27.5 ms`
- `fused_conv2d_transpose2_add12`: `~22.5 ms`
- `fused_conv2d_transpose_add6`: `~20.4 ms`

### ACL first runnable reference

- transpose1-like: `27.016 ms` (`127x127x24`)
- transpose2-like: `45.619 ms` (`255x255x12`)
- transpose_add6-like: `14.958 ms` (`63x63x48`)

## 10. 当前工程判断

基于现有证据，当前最稳妥的判断是：

1. ACL 已证明“可运行、可参考”
2. ACL 尚未证明“可直接替换当前 55% 热点”
3. 对 transpose1/transpose2 两条，ACL 当前参考结果没有显示出优于 TVM 的趋势
4. 对 transpose_add6 一条，ACL 当前数值更好，但 shape mismatch 使其不能直接作为胜出结论
5. 因此 ACL 目前更适合继续作为 **Phase 3 参考/突破方向**，而不是当前主线替换方案

## 11. 后续输出要求

本实验后续所有结果都必须在标题或摘要中明确标注以下之一：

- `reference-layer`
- `breakthrough-layer`

禁止把两者混写，禁止省略 ACL shape/semantic 边界说明。
