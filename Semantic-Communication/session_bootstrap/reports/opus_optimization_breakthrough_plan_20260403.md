# TVM 飞腾派算子优化突破方案（Opus 审阅版）

- generated_at: `2026-04-03T21:00:00+08:00`
- updated_at: `2026-04-03T22:30:00+08:00`
- author: `Claude Opus (代码审阅 + 方案设计 + 部分执行)`
- scope: 基于全项目代码审阅的优化突破方案
- status: `partially_executed — 代码层面完成，待编译上板`
- executor: `交由 OpenClaw 继续执行编译、上板测试与集成`

---

## ⚠️ TRUSTED CURRENT 安全规则（最高优先级，执行者必读）

**当前 Trusted Current 是项目答辩的生命线，任何操作都不得破坏它。**

### 不可变基线

| 字段 | 值 |
|------|------|
| Trusted current artifact | `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so` |
| Trusted current SHA-256 | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` |
| Trusted current payload | 130.219 ms |
| Trusted current e2e | 230.339 ms/image |

### 安全规则

1. **绝对禁止覆盖上述 artifact 文件**。所有新编译产物必须输出到独立目录（如 `session_bootstrap/tmp/opus_integrated_<timestamp>/`）。
2. **绝对禁止修改 `config/inference_tvm310_safe.2026-03-10.phytium_pi.env` 中的 `INFERENCE_CURRENT_EXPECTED_SHA256`**，除非新产物已通过全部验证且显式决定升级。
3. **飞腾板上的 remote artifact 目录不得被覆盖**。新产物上传到独立目录（如 `/home/user/Downloads/jscc-test/jscc_opus_candidate/`），不碰 `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/`。
4. 每个新编译产物都必须记录 SHA-256。
5. **回退方案**：如果任何新产物导致正确性或性能回退，直接丢弃该产物，Trusted Current 不受影响。

### 升级 Trusted Current 的条件（全部满足才可升级）

- [ ] 新产物正确性验证通过：300 张图像 max_abs_diff < 1e-3
- [ ] 新产物 payload benchmark 中位时间 < Trusted Current（130.219 ms）
- [ ] 新产物 e2e benchmark 中位时间 < Trusted Current（230.339 ms）
- [ ] 新旧产物的 SHA-256 均已记录
- [ ] 人工确认后才执行升级

---

## Opus 已完成工作清单（OpenClaw 从这里接手）

### ✅ 已完成：代码修改

| # | 操作 | 文件 | 状态 | TVM 解析验证 |
|---|------|------|------|-------------|
| 1 | variance3 v1: `T_multiply_red` 加 `scope="local"` | `handwritten/fused_variance3_add10_tir_sqrt3/...v1_working_copy_tir.py` | ✅ 已改 | ✅ exit 0 |
| 2 | variance4 v18: `T_multiply_red` 加 `scope="local"` | `handwritten/fused_variance4_add13_tir_sqrt4/...v18_working_copy_tir.py` | ✅ 已改 | ✅ exit 0 |
| 3 | variance3 v2: Welford 单遍算法全新 TIR | `handwritten/fused_variance3_add10_tir_sqrt3/...v2_working_copy_tir.py` | ✅ 已创建 | ✅ exit 0 |
| 4 | variance1 v1: Welford 单遍 TIR（shape [1,96,32,32]） | `handwritten/fused_variance1_add3_tir_sqrt1/...v1_working_copy_tir.py` | ✅ 已创建 | ✅ exit 0 |
| 5 | mean1 v1: 规范化到 handwritten 目录 | `handwritten/fused_mean1_subtract1_divide1_multiply1_add4/...v1_working_copy_tir.py` | ✅ 已创建 | ✅ exit 0 |
| 6 | mean1 v1 build script 备份 | `handwritten/fused_mean1_subtract1_divide1_multiply1_add4/...v1_build.py` | ✅ 已复制 | — |

### ✅ 已完成：信息收集

| 项目 | 结果 |
|------|------|
| variance1 shape | `[1, 96, 32, 32] → [1, 96, 1, 1]`，division=1024.0 |
| mean1 编译产物 | `/tmp/mean1_v1_cross.so` 存在（92312 bytes） |
| 开发机架构 | aarch64 Qualcomm Snapdragon 12 核（非 x86，无需交叉编译） |
| 飞腾派 L1d cache | 32 KB per core（Cortex-A72） |

### ❌ 未完成：需要 OpenClaw 执行

| # | 任务 | 优先级 | 预计时间 |
|---|------|--------|---------|
| A | 编译上述 6 个 TIR 为 `.so` 并上板 benchmark | P0 | 2 小时 |
| B | 创建 variance4 v20（Welford 版本，镜像 variance3 v2） | P0 | 30 分钟 |
| C | 创建 mean4 v4（5 循环融合版本） | P1 | 1 小时 |
| D | 将所有通过验证的优化集成到新 `.so`（不碰 Trusted Current） | P1 | 4 小时 |
| E | ARM Compute Library 编译与 conv2d 参考 | P2 | 1-2 周 |

---

## 零、方案背景与触发原因

### 项目当前状态

| 指标 | 数值 |
|------|------|
| Trusted current payload | 130.219 ms |
| Trusted current e2e | 230.339 ms/image |
| 手写算子成功 | 3/9（transpose1 v7 -1.97%, variance4 v18 -0.99%, variance3 v1 -23.18%） |
| 手写算子失败 | 6/9（conv2d 类全部回退） |
| 已集成到 trusted current | **0/3**（所有成功优化均未集成） |

### 触发本方案的四个发现

1. **报告中"交叉编译"表述有误**：开发机是 Qualcomm Snapdragon aarch64（12 核），与飞腾派同为 ARMv8，不需要交叉编译，只是跨微架构编译（target=cortex-a72）。
2. **飞腾派关键硬件参数**：Cortex-A72 L1d = 32 KB/core，这是 working set reduction 有效的根本原因。
3. **AI 写的手写 TIR 存在明显代码质量问题**：算法选择（两遍 vs 单遍 Welford）、存储标注遗漏（累加器未标 local）、缺乏向量化。
4. **ARM 开源生态有大量现成优化资源**：ARM Compute Library、XNNPACK 等包含针对 Cortex-A72 手写 NEON 内核，可直接参考或集成。

---

## 一、AI 手写 TIR 代码审阅报告

### 1.1 variance3 v1（-23.18%，本项目最大单算子提升）

**文件**：`session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py`

**发现的问题**：

| # | 问题 | 严重程度 | 具体位置 |
|---|------|---------|---------|
| A | `T_multiply_red` 累加器未标 `scope="local"` | 中 | 第 46 行 |
| B | 使用两遍扫描而非单遍 Welford 算法 | 高 | 第 52-67 行 (Pass 1) + 第 79-112 行 (Pass 2) |
| C | 完全没有向量化标注（NEON 可做 4x float32） | 中 | 全文 |
| D | reduction 循环无 tiling（128×128 展平） | 低 | 第 52-54 行 |
| E | `volatile_scope` 标注暗示对 codegen 理解不足 | 低 | 第 49 行 |

**问题 A 详解**：

```python
# 当前代码（第 46 行）——累加器在全局内存
T_multiply_red = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)))

# 应改为——24 个 float32 = 96 字节，完全可以放 local
T_multiply_red = T.alloc_buffer(
    (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
    "float32",
    scope="local",
)
```

对比：同一文件中 `lv_input_red`（第 32-36 行）和 `lv_input_mean_local`（第 38-42 行）都正确标了 `scope="local"`，唯独 `T_multiply_red` 遗漏了。

**问题 B 详解**：

当前算法执行两遍：

- Pass 1：遍历 24×128×128 = 393,216 次读 → 计算 sum → 算 mean
- Pass 2：再遍历 24×128×128 = 393,216 次读 → 计算 (x-mean)² sum

每个 channel 的输入数据 128×128×4B = 64 KB，**超过 Cortex-A72 L1d 的 32 KB**。Pass 1 结束后数据被 evict，Pass 2 必须从 L2（甚至主存）重读。

**Welford 单遍算法**只需遍历一次，内存流量减半：

```
对每个 channel:
    mean = 0, M2 = 0
    for i in 0..16383:
        x = input[channel][i]
        delta = x - mean
        mean += delta / (i+1)
        M2 += delta * (x - mean)
    variance = M2 / 16384
    output = sqrt(variance + eps)
```

### 1.2 variance4 v18（-0.99%）

**文件**：`session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy_tir.py`

与 variance3 v1 **完全相同的问题结构**：
- 第 45 行：`T_multiply_red` 未标 local（12 个 float32 = 48 字节）
- 两遍扫描（shape [1,12,256,256]，每 channel 256 KB，远超 L1d）
- 无向量化

**特别注意**：variance4 的每 channel 数据量是 256×256×4B = 256 KB，是 variance3 的 4 倍。在这种情况下 Welford 的收益可能更大（因为 L2 cache miss 的代价更高）。但 variance4 v18 目前只有 -0.99% 的提升，可能正是因为两遍扫描的内存惩罚抵消了 working set reduction 的收益。

### 1.3 transpose1 v7（-1.97%）

**文件**：`session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py`

这是一个 260 行的复杂 conv2d_transpose TIR。代码结构合理（dc_0 slice reuse 是有效的），但存在：
- `data_dilate` 和 `data_pad` 分配了完整的 48×127×127 和 48×130×130 缓冲区，实际每次只用 4 channel slice
- 复杂的 `T.where` 边界条件可能阻碍 LLVM 向量化
- 大量网格维度为 1（如 b_2=1, c_2=1, w_2=1），增加了代码冗余但不影响性能

**对 conv2d 类算子的判断**：手写 TIR 难以超越 MetaSchedule + LLVM 的组合优化。正确方向是引入专业的 ARM NEON 实现作为参考（见阶段 1）。

### 1.4 mean4 v3（ablation，未上板）

**文件**：`session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v3_working_copy_tir.py`

这是一个 instance-norm 类操作：`(input - mean) / std * weight + bias → relu`。

问题：
- 5 个独立的 elementwise 循环（subtract, divide, multiply, add, relu），每个都遍历 12×256×256。应该 fuse 成一个循环。
- `T_divide_intermediate` 标了 `scope="local"`（正确），但其他中间 buffer（`T_subtract_intermediate`、`T_divide_intermediate_1`、`T_multiply_intermediate`、`T_add_intermediate`）都在全局内存。
- 每个中间 buffer 都是 12×256×256 = 3.14 MB，5 个独立循环 = 5 次全量读写 = ~31 MB 内存流量。如果 fuse 成单循环，中间值都在寄存器中，内存流量降为 ~6 MB（只读一次 input + 写一次 output）。

**这解释了为什么 mean4 v2 回退了 +3.11%**——v2 的 "scalar epilogue handoff" 改动没有解决根本问题（循环未融合）。

---

## 二、具体执行方案

### 阶段 0：快速修复与低风险收割 ✅ Opus 已完成代码层面

#### 任务 0.1 ✅ 已完成：修复 variance3 v1 的 `T_multiply_red` scope

**已由 Opus 执行**：`T_multiply_red` 已加 `scope="local"`。TVM 解析验证 exit 0。

**OpenClaw 需要做**：编译此文件为 `.so` 并上板做 30 样本 microbenchmark，与 variance3 v1 baseline（2736 us）对比。如果回退则还原这一行改动。

#### 任务 0.2 ✅ 已完成：同样修复 variance4 v18

**已由 Opus 执行**：同上。

#### 任务 0.3 ✅ 已完成：确认 variance1 的 shape

**结果**：`float32[1, 96, 32, 32] → float32[1, 96, 1, 1]`，division=1024.0。

#### 任务 0.4 ✅ 已完成：mean1 v1 规范化

**已由 Opus 执行**：TIR 和 build script 已从 `/tmp` 复制到 `session_bootstrap/handwritten/fused_mean1_subtract1_divide1_multiply1_add4/`。原始编译产物仍在 `/tmp/mean1_v1_cross.so`（92312 bytes）。

### 阶段 0 续：OpenClaw 编译与上板测试指令

**编译环境**：

```bash
TVM_PYTHON=/home/tianxing/.venvs/tvm-ms/bin/python
TVM_SRC=/home/tianxing/tvm-src
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
```

**注意**：本机是 aarch64（Snapdragon），不需要交叉编译工具链。`tvm.build()` 直接生成 aarch64 `.so`。但 TVM `@I.ir_module` 装饰器**不能在 `-c` 内联代码中使用**，必须写独立 `.py` 文件再执行。

**编译模板**（以 variance3 v1.1 为例）：

```python
#!/usr/bin/env python3
"""Build variance3 v1.1 (scope fix) for Cortex-A72."""
import sys, os
sys.path.insert(0, '/home/tianxing/tvm-src/python')
os.environ['TVM_LIBRARY_PATH'] = '/home/tianxing/tvm-src/build'
import tvm

# 导入 TIR module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "variance3_v1_1",
    "session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/"
    "fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py"
)
# 注意：由于 @I.ir_module 限制，上面的 importlib 方式可能失败
# 如果失败，改用 subprocess 执行独立构建脚本

TARGET = tvm.target.Target({
    "kind": "llvm",
    "mtriple": "aarch64-linux-gnu",
    "mcpu": "cortex-a72",
    "mattr": ["+neon"],
    "num-cores": 4,
})

# 方案 B：直接在构建脚本中内联 TIR（参考 /tmp/build_mean1_v1.py 的模式）
```

**推荐的构建流程**：参考已验证可用的 `/tmp/build_mean1_v1.py`，为每个候选 TIR 创建类似的独立构建脚本。所有编译产物输出到 `session_bootstrap/tmp/opus_candidates_<timestamp>/`，**不碰 Trusted Current 目录**。

**上板 benchmark 流程**：
1. 上传 `.so` 到飞腾板**独立目录**（如 `/home/user/Downloads/jscc-test/jscc_opus_candidate/`）
2. 使用现有 benchmark 脚本做 30 样本微基准测试
3. 正确性检查：`max_abs_diff < 1e-3`
4. 性能对比：与各自的 baseline（profiling 报告中的 median 值）对比
5. **如果回退（慢于 baseline）：直接丢弃该候选，不做任何进一步操作**

### 阶段 1：Welford 算法重写 ✅ Opus 已完成 variance3 v2 和 variance1 v1

#### 任务 1.1 ✅ 已完成：variance3 v2（Welford 单遍）

**已创建文件**：`session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v2_working_copy_tir.py`

TVM 解析验证 exit 0。

**关键技术细节**：
1. Welford 中的 `1/(count+1)` 使用 `T.Cast("float32", v_k2 * 128 + v_k3 + 1)` 做运行时除法。如果性能不理想，可改用预计算倒数表或 Kahan compensated sum。
2. 所有中间变量（`welford_mean`, `welford_M2`, `delta_old`, `delta_new`）都在 `scope="local"`。
3. **正确性风险**：Welford 的逐步除法可能导致浮点累积误差。如果 `max_abs_diff > 1e-3`，回退到 v1.1（scope fix only），不用 Welford。

#### 任务 1.2 ❌ 未完成：variance4 v20（Welford）

**OpenClaw 需要做**：镜像 variance3 v2 的 TIR 结构，调整：
- shape: `[1, 12, 256, 256] → [1, 12, 1, 1]`
- channels: 12
- spatial: 256×256 = 65536
- division constant: 65536.0
- count 计算: `v_k2 * 256 + v_k3 + 1`

#### 任务 1.3 ✅ 已完成：variance1 v1（Welford）

**已创建文件**：`session_bootstrap/handwritten/fused_variance1_add3_tir_sqrt1/fused_variance1_add3_tir_sqrt1_scheduled_form_candidate_v1_working_copy_tir.py`

Shape: `[1, 96, 32, 32] → [1, 96, 1, 1]`，division=1024.0。TVM 解析验证 exit 0。

#### 任务 1.4 ❌ 未完成：mean4 v4（5 循环融合成单循环）

**OpenClaw 需要做**：把 mean4 v3 的 5 个独立 elementwise 循环融合成一个。参考 mean1 v1 的 fused 结构（已在 handwritten 目录中）。

核心思路：

```python
# 融合后：一次遍历完成 subtract + divide + multiply + add + relu
for ax0, ax1, ax2, ax3 in T.grid(1, 12, 256, 256):
    x = lv335[ax0, ax1, ax2, ax3]
    mean_val = T_divide_intermediate[ax0, ax1, 0, 0]  # local
    std_val = lv340[ax0, ax1, 0, 0]
    w = lv342[ax1, 0, 0]
    b = lv344[ax1, 0, 0]
    result = T.max(((x - mean_val) / std_val) * w + b, T.float32(0.0))
    compute_intermediate[ax0, ax1, ax2, ax3] = result
```

**预期收益**：内存流量从 ~31 MB 降至 ~6 MB。

### 阶段 2：集成到新候选产物（预计 4-6 小时）

> **重申**：此阶段的所有产物必须输出到独立目录，**绝不覆盖 Trusted Current**。只有全部验证通过并经人工确认后，才可考虑升级。

#### 任务 2.1：构建统一的 prim_func 替换编译流程

**目标**：建立一个自动化脚本，将多个已验证的手写 prim_func 替换到完整 IR module 中，编译出**候选** `.so`。

**技术路径**：
1. 从 MetaSchedule 数据库恢复完整的 post-tuning IR module
2. 使用 `tvm.ir.transform` 或手动替换目标 prim_func
3. 使用相同 target 编译：`{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}`
4. 计算新 SHA-256
5. **输出到**：`session_bootstrap/tmp/opus_integrated_<timestamp>/optimized_model.so`

**脚本位置**：`session_bootstrap/scripts/integrate_handwritten_to_trusted_current.py`

**重要参考**：项目中已有 post-db swap 的可用路径——transpose1 v7 和 variance4 v18 都是通过 `run_mean4_post_db_local_build.py` 类似的脚本完成的整模型替换编译。可以直接复用这个已验证的路径，而不需要从零构建。

#### 任务 2.2：集成已验证优化并做端到端 benchmark

**集成列表**（只集成通过独立验证的算子）：

| 算子 | 版本 | 独立验证 | 集成决策 |
|------|------|---------|---------|
| fused_conv2d_transpose1_add9 | v7 | ✅ -1.97% | 只有独立验证 < baseline 时才纳入 |
| fused_variance4_add13_tir_sqrt4 | v18/v20 (选最优) | ✅/-0.99% | 只有独立验证 < baseline 时才纳入 |
| fused_variance3_add10_tir_sqrt3 | v1.1/v2 (选最优) | ✅ -23.18% | 只有独立验证 < baseline 时才纳入 |
| fused_variance1_add3_tir_sqrt1 | v1 (Welford) | 待验证 | 只有独立验证 < baseline 时才纳入 |
| fused_mean1_..._add4 | v1 (fused) | 待验证 | 只有独立验证 < baseline 时才纳入 |
| fused_mean4_..._relu3 | v4 (fused) | 待创建 | 只有独立验证 < baseline 时才纳入 |

**端到端验证流程（严格顺序）**：

```
1. 编译候选产物 → 输出到独立目录
2. 计算 SHA-256 并记录
3. 上传到飞腾板独立目录（不碰 Trusted Current 的远端目录）
4. 正确性验证：300 张图像重建，max_abs_diff 对比
   → 如果 max_abs_diff > 1e-3：停止，丢弃候选
5. Payload benchmark：30 样本
   → 如果 median > 130.219 ms（Trusted Current）：停止，丢弃候选
6. E2e benchmark：30 样本
   → 如果 median > 230.339 ms（Trusted Current）：停止，丢弃候选
7. 全部通过 → 生成报告，等待人工确认是否升级 Trusted Current
```

**回退方案**：无论在哪一步失败，都直接丢弃候选产物。Trusted Current 的 `.so` 文件、SHA-256 和远端目录始终不变。

### 阶段 3：ARM Compute Library 参考与 conv2d 突破（预计 1-2 周）

#### 任务 3.1：在飞腾板上编译 ARM Compute Library

```bash
git clone https://github.com/ARM-software/ComputeLibrary.git
cd ComputeLibrary
scons Werror=0 arch=armv8a os=linux neon=1 opencl=0 build=native -j4
```

#### 任务 3.2：提取 ACL conv2d_transpose 的优化策略

ACL 中 conv2d_transpose 通常通过以下路径实现：
- **im2col + GEMM**：将 deconvolution 转化为矩阵乘法
- **Winograd**：对特定 kernel size（3×3）使用 Winograd 变换减少乘法
- **direct NEON kernel**：手写 NEON intrinsics 的直接卷积

从 ACL 源码中分析：
- `src/cpu/operators/CpuConv2d.cpp`
- `src/cpu/operators/CpuGemm.cpp`
- `src/core/NEON/kernels/arm_gemm/` 目录下的 NEON GEMM 内核

目标不是直接使用 ACL，而是**理解 ARM 专家如何优化 conv2d_transpose for A72**，然后将这些策略引入 TVM TIR。

#### 任务 3.3：评估 BYOC offload 可行性

如果 ACL 的 conv2d_transpose 显著优于 TVM MetaSchedule 的结果，可以考虑：
- **方案 A**：通过 TVM BYOC 将 conv2d_transpose 算子 offload 到 ACL
- **方案 B**：在 TIR 中嵌入 NEON intrinsics（`T.call_packed` 或 `T.call_intrin`）
- **方案 C**：用 ACL 的策略（如 Winograd/GEMM tiling）手写 TIR

**conv2d 类算子占 79% runtime**。如果能通过 ACL 参考实现哪怕 5% 的改进，端到端收益将远超 variance 类的所有优化总和。

### 阶段 4：论文与报告更新（预计 2 小时）

#### 任务 4.1：更新技术文档 4.1.2 节

需要增加的内容：
1. variance3 v1 的优化案例（-23.18%，本项目最大单算子提升）
2. Welford 算法改进（如果 v2 成功）
3. 方法论提炼："working set reduction" + "算法选择优于调度微调"
4. 如果集成成功，更新 4.1.3 节的整模型性能结果

#### 任务 4.2：修正技术表述

- 将"交叉编译"改为"跨微架构编译"（或直接写"编译 target 指定为 cortex-a72"）
- 补充 Cortex-A72 L1d = 32 KB 的硬件参数及其对优化策略的影响

---

## 三、风险评估与止损规则

| 阶段 | 风险 | 止损条件 |
|------|------|---------|
| 0.1 scope="local" 修复 | 极低 | 如果 benchmark 回退则还原 |
| 1.1 Welford 重写 | 中（浮点精度） | 如果 max_abs_diff > 1e-3 则用分块方案 |
| 1.4 mean4 循环融合 | 低 | 如果 benchmark 回退则还原 |
| 2 集成到 trusted current | 中（编译流程复杂） | 如果集成失败，保留独立 benchmark 数据 |
| 3 ACL 参考 | 高（工程量大） | 如果 ACL 编译失败或无明显优势，改为纯文档参考 |

---

## 四、预期成果汇总

### 保守估计（仅完成阶段 0+1+2）

| 来源 | 端到端节省 (us) | 占比 |
|------|----------------|------|
| variance3 scope fix + Welford | ~1000-1500 | ~0.4-0.6% |
| variance4 scope fix + Welford | ~500-1000 | ~0.2-0.4% |
| variance1 Welford | ~500-800 | ~0.2-0.3% |
| mean4 循环融合 | ~800-1200 | ~0.3-0.5% |
| transpose1 v7 集成 | 已有 | 已有 |
| **合计端到端改进** | **~3-5 ms** | **~1.3-2.2%** |

### 乐观估计（加上阶段 3 的 conv2d 突破）

如果通过 ACL 参考实现对 top-5 conv2d 算子获得 5% 改进：
- top-5 conv2d 合计 ~100 ms → 节省 ~5 ms
- 端到端改进可达 ~4%

---

## 五、OpenClaw 执行优先级排序

```
Opus 已完成（代码层面）
├── ✅ 0.1 variance3 v1 scope fix
├── ✅ 0.2 variance4 v18 scope fix
├── ✅ 0.3 确认 variance1 shape = [1,96,32,32]→[1,96,1,1]
├── ✅ 0.4 mean1 v1 规范化到 handwritten 目录
├── ✅ 1.1 variance3 v2 Welford TIR
└── ✅ 1.3 variance1 v1 Welford TIR

OpenClaw 第一轮：编译 + 上板（预计 2-3 小时）
├── A1. 为 variance3 v1.1 编写 build script + 编译     ← 参考 /tmp/build_mean1_v1.py
├── A2. 为 variance3 v2 编写 build script + 编译
├── A3. 为 variance1 v1 编写 build script + 编译
├── A4. 确认 /tmp/mean1_v1_cross.so 仍可用（或重编）
├── A5. 上传全部 .so 到飞腾板独立目录
├── A6. 各算子 30 样本 microbenchmark
└── A7. 生成 benchmark 报告

OpenClaw 第二轮：补写 + 编译（预计 2 小时）
├── B1. 创建 variance4 v20 Welford TIR（镜像 v3 v2）
├── B2. 创建 mean4 v4 循环融合 TIR
├── B3. 编译 + 上板 benchmark
└── B4. 生成 benchmark 报告

OpenClaw 第三轮：集成（预计 4-6 小时，仅当上面有正收益时）
├── C1. 选择各算子最优版本（scope fix vs Welford）
├── C2. 构建整模型替换编译脚本
├── C3. 编译候选产物到独立目录
├── C4. 上板端到端验证（正确性 + payload + e2e）
├── C5. 生成集成报告
└── C6. ⚠️ 等待人工确认后才考虑升级 Trusted Current

后续（如果时间允许）
├── D1. ACL 编译安装
├── D2. ACL conv2d_transpose 分析
└── D3. BYOC / NEON 策略评估
```

---

## 六、关联文件索引

### Opus 本轮修改/创建的文件（✅ = 已修改, 🆕 = 新创建）

| 状态 | 用途 | 路径 |
|------|------|------|
| ✅ | variance3 v1 TIR（scope fix 已应用） | `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py` |
| ✅ | variance4 v18 TIR（scope fix 已应用） | `session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy_tir.py` |
| 🆕 | variance3 v2 Welford TIR | `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v2_working_copy_tir.py` |
| 🆕 | variance1 v1 Welford TIR | `session_bootstrap/handwritten/fused_variance1_add3_tir_sqrt1/fused_variance1_add3_tir_sqrt1_scheduled_form_candidate_v1_working_copy_tir.py` |
| 🆕 | mean1 v1 fused TIR（规范化） | `session_bootstrap/handwritten/fused_mean1_subtract1_divide1_multiply1_add4/fused_mean1_subtract1_divide1_multiply1_add4_scheduled_form_candidate_v1_working_copy_tir.py` |
| 🆕 | mean1 v1 build script（复制自 /tmp） | `session_bootstrap/handwritten/fused_mean1_subtract1_divide1_multiply1_add4/fused_mean1_subtract1_divide1_multiply1_add4_scheduled_form_candidate_v1_build.py` |
| 🆕 | 本方案文档 | `session_bootstrap/reports/opus_optimization_breakthrough_plan_20260403.md` |

### 已有不变文件（参考）

| 用途 | 路径 |
|------|------|
| mean4 v3 TIR（OpenClaw 待融合重写为 v4） | `session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v3_working_copy_tir.py` |
| transpose1 v7 TIR（参考，不改动） | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py` |
| mean1 v1 已编译产物（/tmp，可能重启丢失） | `/tmp/mean1_v1_cross.so`（92312 bytes） |
| mean1 v1 原始 build script | `/tmp/build_mean1_v1.py` |

### 环境与基线

| 用途 | 路径/值 |
|------|---------|
| TVM venv | `/home/tianxing/.venvs/tvm-ms/bin/python` |
| TVM 源码 | `/home/tianxing/tvm-src/`（版本 0.24.dev0） |
| **Trusted current artifact（⚠️ 不可覆盖）** | `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so` |
| **Trusted current SHA（⚠️ 不可修改）** | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` |
| 编译 target | `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}` |
| 飞腾板 SSH | `user@100.121.87.73:22`（密码在 `config/phytium_pi_login.env`） |
| 飞腾板 TVM Python | `/home/user/anaconda3/envs/tvm310/bin/python` |
| 10-sample profiling 报告 | `session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md` |
| 前次状态交接报告 | `session_bootstrap/reports/project_status_handover_20260403_1908.md` |

---

## 七、开源参考资源

| 项目 | 链接 | 关键文件 | 用途 |
|------|------|---------|------|
| ARM Compute Library | https://github.com/ARM-software/ComputeLibrary | `src/cpu/operators/CpuConv2d.cpp`, `src/core/NEON/kernels/arm_gemm/` | conv2d_transpose NEON kernel 参考 |
| XNNPACK | https://github.com/google/XNNPACK | `src/f32-rsum/`, `src/f32-vmulcaddc/` | mean/variance NEON 实现参考 |
| Ruy | https://github.com/google/ruy | `ruy/kernel_arm64.cc` | GEMM micro-kernel 参考 |
| TVM AutoTVM Records | TVM 社区 | `python/tvm/meta_schedule/testing/` | ARM target 的 tuning 参考 |
| Ne10 | https://github.com/projectNe10/Ne10 | `modules/math/` | ARM NEON 数学运算参考 |
