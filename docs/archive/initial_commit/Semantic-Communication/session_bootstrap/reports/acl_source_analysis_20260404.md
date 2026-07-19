# ARM Compute Library (ACL) 源码分析报告 — conv2d_transpose 优化策略

- 日期: 2026-04-04
- 分析对象: ComputeLibrary (commit latest, ARM-software/ComputeLibrary)
- 目的: 理解 ARM 官方如何优化 conv2d_transpose for Cortex-A72，评估对飞腾派的适用性

## 一、ACL conv2d 策略选择机制

ACL 的 `CpuConv2d::configure()` 根据输入参数自动选择最优策略：

| 优先级 | 策略 | 实现类 | 适用条件 |
|--------|------|--------|---------|
| 1 | Winograd | `CpuWinogradConv2d` | 3×3 kernel, 特定数据类型 |
| 2 | GEMM Direct Conv2d | `CpuGemmDirectConv2d` | 通用路径（im2col + indirect GEMM） |
| 3 | Direct Conv2d | `CpuDirectConv2d` | NCHW 布局，小 batch |

**关键发现**: ACL 没有 explicit `conv2d_transpose`。转置卷积通过 im2col + GEMM 实现（与 TVM MetaSchedule 的方法一致）。

## 二、A72 NEON GEMM Micro-Kernel

Cortex-A72 使用的核心 GEMM kernel 是 `a64_ffinterleaved_fp32_mla_8x12`：

- **输出 tile**: 8 行 × 12 列（fp32）
- **指令**: NEON FMLA (fused multiply-accumulate)
- **数据布局**: Fixed-format interleaved（A 矩阵按 8 行交错存储）
- **寄存器压力**: 8×12 = 96 个 fp32 累加器 = 24 个 NEON Q 寄存器（A72 有 32 个 128-bit NEON 寄存器）

这个 tile size 是专门为 Cortex-A72 调优的：
- 32 个 Q 寄存器，24 个用于累加器，6 个用于 A/B 矩阵加载，2 个用于指针/常数
- 最大化寄存器利用率，减少 memory traffic

## 三、对飞腾派 CPU（implementer 0x70）的适用性

### 3.1 CPUID 不匹配问题

| 字段 | 标准 Cortex-A72 | 飞腾派 |
|------|----------------|--------|
| implementer | 0x41 (ARM) | **0x70 (Phytium)** |
| part | 0xd08 | 0x303 / 0x664 |
| NEON registers | 32 × 128-bit | **未知** |

ACL 的运行时 CPU 检测会：
1. 读取 implementer + part
2. 查找预定义的 CPU 特性表
3. 0x70 不在表中 → **回退到 generic ARMv8 NEON 路径**

**结论**: ACL 在飞腾派上不会使用 hand-tuned A72 kernel，性能可能不如 TVM MetaSchedule。

### 3.2 generic NEON 路径

generic 路径的特点：
- 使用基本 NEON intrinsics（无 pipeline-specific scheduling）
- 无 interleaved data layout 优化
- 无 micro-kernel tiling 调优
- 类似于 LLVM auto-vectorization 的输出质量

**预测**: ACL generic ≤ TVM MetaSchedule（因为 TVM 通过实测搜索找到了更优调度）

## 四、Winograd 策略分析

ACL 对 3×3 conv2d 优先使用 Winograd（F(2,3) 或 F(4,3)）：

```
标准 conv2d 3×3:  每个 output pixel 需要 3×3=9 次 multiply
Winograd F(2,3):  每 2×2=4 个 output pixel 需要 4×4=16 次 multiply
                   → 每个 pixel 4 次 multiply（减少 56%）
Winograd F(4,3):  每 4×4=16 个 output pixel 需要 6×6=36 次 multiply
                   → 每个 pixel 2.25 次 multiply（减少 75%）
```

**但 Winograd 对 conv2d_transpose 的适用性需要验证**：
- Winograd 原理上可以应用于 deconvolution（因为数学变换是对称的）
- 但 ACL 的 Winograd 实现只针对 conv2d（forward），不直接支持 transpose
- 需要将 transpose 转化为等价的 conv2d（im2col + GEMM）后才能应用

## 五、对我们项目的影响

### 5.1 对论文叙事的价值

ACL benchmark 数据可以支持以下论点：
1. "飞腾派使用自研 ARMv8 微架构，ARM Compute Library 无法识别，回退 generic 路径"
2. "TVM MetaSchedule 通过实测搜索在飞腾派上取得优于 ACL generic 的性能"
3. "证明了 search-based 方法对非标准 ARM 芯片的适配优势"

### 5.2 对进一步优化的启示

如果要在 TVM TIR 中复现 ACL 的策略：
1. **Winograd**: 可行但工程量大——需要在 TIR 中实现 input/filter/output 变换
2. **GEMM micro-kernel tiling**: 需要知道飞腾 CPU 的 NEON register file 大小（未知）
3. **Interleaved layout**: TIR 层面难以控制数据布局到这种粒度

**现实结论**: conv2d_transpose 的进一步优化在 TIR 层面收益有限，但"分析并解释为什么"本身有论文价值。

## 六、关键源码路径索引

| 内容 | 路径 |
|------|------|
| conv2d 策略选择 | `src/cpu/operators/CpuConv2d.cpp` |
| GEMM Direct Conv2d | `src/cpu/operators/CpuGemmDirectConv2d.cpp` |
| Winograd Conv2d | `src/cpu/operators/CpuWinogradConv2d.cpp` |
| A72 GEMM kernel | `src/core/NEON/kernels/arm_gemm/kernels/a64_ffinterleaved_fp32_mla_8x12.hpp` |
| GEMM fp32 策略表 | `src/core/NEON/kernels/arm_gemm/gemm_fp32.cpp` |
| CPUID 检测 | `src/core/NEON/INEKernel.h` + `src/cpu/CpuSelector.cpp` |

## 七、其他参考库

| 库 | 特点 | 适用性 |
|---|---|---|
| XNNPACK (Google) | TFLite 底层，更激进的 NEON 优化 | 有 f32-conv-transpose 和 f32-rsum kernel |
| Ruy (Google) | 纯 GEMM，ARM 专用 | 另一种 GEMM tiling 风格 |
| Ne10 (Community) | ARM NEON 数学基础库 | 较老，参考价值有限 |
