# TVM-飞腾派项目当前状态详报（2026-04-03 19:08）

## 一、项目背景

**项目**：基于飞腾派（Phytium Pi, ARM Cortex-A72 四核）的图像语义通信系统，参加集创赛飞腾杯。

**核心工作**：使用 TVM MetaSchedule 对 JSCC 语义通信模型进行推理性能优化，并围绕 OpenAMP 异构控制面构建完整的答辩闭环。

**工作区**：`/home/tianxing/tvm_metaschedule_execution_project`

---

## 二、本次会话（2026-04-03 17:00-19:08）完成的工作

### 2.1 Runtime Profiling 扩样本（已完成）

**目标**：将 runtime per-op profiling 从 3 样本扩展到 10 样本，提升统计置信度。

**执行过程**：
1. 尝试运行 profiling 脚本，遇到两个配置问题并逐一修复：
   - `INFERENCE_CURRENT_EXPECTED_SHA256` 过期：env 文件中为 `1946b08e...`，实际 trusted current artifact 是 `6f236b07...`。已修正。
   - `REMOTE_TORCH_PYTHONPATH` 为空：latent 输入是 `.pt` 文件需要 torch，env 中未配置。已补齐为 `/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages`。
2. 成功运行 10-input profiling，10/10 样本全部 profiled。

**结果**：

| 指标 | 3-sample (2026-03-30) | 10-sample (2026-04-03) |
|---|---|---|
| median e2e | 246.697 ms | 230.75 ms |
| mean e2e | 257.31 ms | 232.829 ms |
| min | - | 197.776 ms |
| max | - | 303.851 ms |
| stddev | - | 25.965 ms |

**Top 10 算子 profiling（10 样本 median）**：

| rank | op | mean_us | pct | std_us | 已尝试手写优化 |
|---|---|---|---|---|---|
| 1 | fused_conv2d_transpose1_add9 | 27510 | 21.6% | 364 | ✅ v7 成功 (-1.97%) |
| 2 | fused_conv2d_transpose2_add12 | 22515 | 17.7% | 109 | ❌ v4 回退 |
| 3 | fused_conv2d_transpose_add6 | 20375 | 16.0% | 155 | ❌ v2 回退 |
| 4 | fused_conv2d2_add2 | 15685 | 12.3% | 302 | 未尝试 |
| 5 | fused_conv2d3_add15 | 14322 | 11.3% | 119 | ❌ v2 回退 |
| 6 | fused_variance4_add13_tir_sqrt4 | 7053 | 5.5% | 84 | ✅ v18 成功 (-0.99%) |
| 7 | **fused_variance3_add10_tir_sqrt3** | **3562** | **2.8%** | **74** | **✅ v1 成功 (-23.18%)** |
| 8 | fused_conv2d_add2 | 2670 | 2.1% | 53 | 未尝试 |
| 9 | fused_variance1_add3_tir_sqrt1 | 2282 | 1.8% | 21 | 未尝试 |
| 10 | fused_mean1_subtract1_divide1_multiply1_add4 | 1944 | 1.5% | 80 | 🔨 v1 已编译待测试 |

**报告**：`session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md`
**Commit**：`87c7b67`

---

### 2.2 variance3 手写算子优化（已完成，-23.18%）

**目标算子**：`fused_variance3_add10_tir_sqrt3`
- 输入：`float32[1, 24, 128, 128]`，输出：`float32[1, 24, 1, 1]`
- 计算：对每个 channel 在 128×128 spatial 维度上计算 variance + sqrt
- Baseline：median 3562 us（占总推理 2.8%）

**优化策略**：应用 variance4 v18 验证过的 **working set reduction + normalized-mean handoff** 原理：
1. Pass 1: sum reduction → 存入 local buffer
2. Compute mean = sum / 16384.0 → 存入 local buffer（一次读，多次复用）
3. Pass 2: fused (input - mean)² + accumulate → intermediates 全在 local buffer
4. Final: sqrt(var/N + eps)

**编译路径**：
- WSL 笔记本上有 TVM 源码 (`/home/tianxing/tvm-src/`) 和 LLVM codegen
- 使用 `/home/tianxing/.venvs/tvm-ms/bin/python` + 交叉编译 target `aarch64-linux-gnu cortex-a72 +neon`
- 编译产物 `.so` 上传到飞腾板 benchmark

**远端 benchmark 结果**：

| 指标 | 值 |
|---|---|
| 正确性 max_abs_diff | 2.265e-06 ✅ PASS |
| Median | **2736 us** |
| Mean | 2734 us |
| Min | 2712 us |
| Std | 14.3 us |
| **vs Baseline** | **-23.18% (3562 → 2736 us)** |

**关键发现**：
- 这是本项目**最大的单算子提升**（远超 transpose1 v7 的 -1.97% 和 variance4 v18 的 -0.99%）
- 验证了 working set reduction 原理在不同 shape（[1,24,128,128] vs [1,12,256,256]）上的可迁移性
- 端到端贡献：节省 826 us / 230750 us ≈ +0.36%

**文件**：
- TIR: `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py`
- Wrapper: `..._scheduled_form_candidate_v1.py`
- Manifest: `scheduled_form_candidate_v1_working_copy_manifest.json`
- Benchmark 报告: `session_bootstrap/reports/variance3_v1_remote_benchmark_20260403.md`

**Commit**：`f4d7633`

---

### 2.3 mean1 手写算子优化（进行中，已编译待测试）

**目标算子**：`fused_mean1_subtract1_divide1_multiply1_add4`
- 输入：`float32[1, 96, 32, 32]`
- 参数：mean `[1,96,1,1]`，weight `[96,1,1]`，bias `[96,1,1]`
- 输出：`float32[1, 96, 32, 32]`
- 计算：`(input - mean) * weight + bias`（instance-norm 类操作）
- Baseline：~1912 us（占总推理 1.45%）

**当前状态**：
- TIR 已编写（单循环 fused subtract+multiply+add，参数 staging 到 local buffer）
- 已在 WSL 本地交叉编译成功：`/tmp/mean1_v1_cross.so`（92312 bytes）
- **待做**：上传到飞腾板 benchmark

---

## 三、编译环境现状（重要约束）

### 飞腾板（100.121.87.73, user/user）
- TVM build (`tvm_samegen_*`) 全部是 **runtime-only**（无 LLVM codegen）
- 无法在板上执行 `tvm.build()`
- 只能 `tvm.runtime.load_module()` 加载已编译的 `.so`
- SSH 可用，`ssh_with_password.sh` 已验证可工作

### WSL 笔记本
- TVM 源码：`/home/tianxing/tvm-src/`，版本 0.24.dev0
- TVM venv：`/home/tianxing/.venvs/tvm-ms/bin/python`
- **有 LLVM codegen**，支持 `aarch64-linux-gnu` 交叉编译
- 编译的 `.so` 可直接在飞腾板运行
- `tvm.script.ir_module` 装饰器**不能**在 `-c` 内联代码中使用，必须写文件再执行

### 远端 Python 环境
- TVM 0.24.dev0 不支持旧 CLI target string（`"llvm -mcpu=xxx"`），必须用 JSON dict
- `tvm.nd.array` 不存在，需用 `tvm.runtime.empty()` + `copyfrom()`
- `.asnumpy()` 不存在，用 `.numpy()`
- `from_dlpack(numpy_array)` 需要 64 字节对齐

---

## 四、手写算子优化历史总览

| 算子 | 版本 | 结果 | Baseline → Optimized |
|---|---|---|---|
| fused_conv2d_transpose1_add9 | v7 | ✅ **-1.97%** | 159.938 → 156.785 ms |
| fused_variance4_add13_tir_sqrt4 | v18 | ✅ **-0.99%** | 159.919 → 158.347 ms |
| **fused_variance3_add10_tir_sqrt3** | **v1** | **✅ -23.18%** | **3562 → 2736 us** |
| fused_conv2d_transpose_add6 | v2 | ❌ +8.36% | 回退 |
| fused_conv2d_transpose2_add12 | v4 | ❌ +2.29% | 回退 |
| fused_mean4_..._relu3 | v2 | ❌ +3.11% | 回退 |
| fused_conv2d3_add15 | v2 | ❌ +0.62% | 回退 |
| fused_variance4_... | v19 | ❌ +0.13% | 回退 |
| fused_conv2d_transpose1_add9 | v8 | ❌ 放弃 | narrowing |

---

## 五、未尝试的算子（按 profiling 占比排序）

| 算子 | 占比 | mean_us | 结构描述 |
|---|---|---|---|
| fused_conv2d2_add2 | 12.3% | 15685 | conv2d+add, 已有尝试但全部回退 |
| fused_conv2d_add2 | 2.1% | 2670 | conv2d+add, 未尝试 |
| fused_variance1_add3_tir_sqrt1 | 1.8% | 2282 | variance+sqrt, 与 variance3/4 同构 |
| fused_variance2_add7_tir_sqrt2 | 0.27% | 349 | variance+sqrt, 太小 |
| fused_mean1_subtract1_divide1_multiply1_add4 | 1.5% | 1944 | instance-norm, 🔨 进行中 |
| fused_conv2d1_add2 | 1.4% | 1781 | conv2d+add |

---

## 六、项目级未完成事项（追踪板）

### Priority 1: Demo 真实彩排 / UI / operator flow
- docs-frozen 部分已完成，Go-no-go 判定：**GO_WITH_DOCS_FIRST_ONLY**
- Live 部分需要 `remoteproc0=running`（当前 offline），无法推进

### Priority 2: OpenAMP 剩余真机协议 / FIT 缺口
- FIT-04/05, TC-007/008/009/010 全部需要 remoteproc0=running

### Priority 3: judge-facing 实测扩样本
- ✅ Profiling 已从 3 样本扩到 10 样本（本次完成）
- 还可以继续扩到 30+ 样本

### P2: 后置差异化
- 跨框架对比、TVM hotspot 定向深搜、手写 TIR（当前正在做）

---

## 七、需要 Opus 给出方案的问题

1. **手写算子优化的下一步策略**：
   - variance3 v1 取得了 -23.18% 的意外大提升，但端到端只贡献 +0.36%。是否值得继续深挖更多 variance/mean 类算子（variance1、variance2、mean1），还是应该转向更大占比的 conv2d 类算子？
   - conv2d 类算子（rank 1-5）占 ~79% runtime，但之前 6 次尝试全部回退。是否有新的策略方向？

2. **如何把手写优化集成到 trusted current**：
   - 目前 variance3 v1 是独立编译的 `.so`，只替换了单个 prim_func。如何把这个替换集成到完整的模型 `.so` 中，使端到端推理真正受益？
   - 需要的流程是：提取 trusted current 的完整 IR module → 替换 variance3 prim_func → 重新编译 → 部署 → 端到端 benchmark

3. **profiling 样本量是否足够**：
   - 当前 10 样本的 median per-op std/mean < 2%，看起来足够稳定。是否需要扩到 30+？

4. **时间分配**：
   - 距离比赛提交的剩余时间如何分配在手写算子 vs Demo 彩排 vs judge-facing evidence 之间？

---

## 八、关键路径和文件索引

| 用途 | 路径 |
|---|---|
| 任务总清单 | `session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md` |
| 执行追踪板 | `session_bootstrap/tasks/赛题对齐执行追踪板_2026-03-13.md` |
| 项目入口 README | `session_bootstrap/README.md` |
| 10-sample profiling 报告 | `session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md` |
| variance3 v1 benchmark | `session_bootstrap/reports/variance3_v1_remote_benchmark_20260403.md` |
| 手写优化状态总结 | `session_bootstrap/reports/handwritten_optimization_status_summary_20260403.md` |
| 4/2-4/3 工作总结 | `session_bootstrap/reports/2026-04-02_04-03_work_summary.md` |
| inference env | `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env` |
| SSH 连接脚本 | `session_bootstrap/scripts/ssh_with_password.sh` |
| Trusted current SHA | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` |
| Trusted current payload | 130.219 ms |
| Trusted current e2e | 230.339 ms/image |
