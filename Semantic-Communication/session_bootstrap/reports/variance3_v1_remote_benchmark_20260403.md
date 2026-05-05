# variance3 v1 远端 Benchmark 报告

- generated_at: 2026-04-03
- operator: fused_variance3_add10_tir_sqrt3
- shape: [1, 24, 128, 128] -> [1, 24, 1, 1]
- artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}

## 优化策略

应用 variance4 v18 验证过的 **working set reduction + normalized-mean handoff** 原理：

1. **Pass 1**: sum reduction over 128×128 = 16384 elements -> stage mean into local buffer
2. **Mean**: divide sum by 16384.0 -> one scalar per channel in local buffer
3. **Pass 2**: fused (subtract mean) × (square) × (accumulate) in single loop, intermediates in local
4. **Final**: sqrt(var/16384 + eps)

关键改进：两个 reduction pass 共享一次读输入，mean 结果在 local buffer 复用，避免重复从主存读。

## Benchmark 结果

| 指标 | 值 |
|---|---|
| 正确性 max_abs_diff | 2.265e-06 |
| 正确性 pass | **TRUE** (threshold 1e-3) |
| Median latency | **2736.4 us** |
| Mean latency | 2734.1 us |
| Min latency | 2712.3 us |
| Std | 14.3 us |
| Samples | 30 |

## 与 Baseline 对比

| | Median (us) | Delta |
|---|---|---|
| Baseline (AutoTVM/MetaSchedule) | 3562 | - |
| **v1 handwritten** | **2736** | **-23.18%** |

## 结论

variance3 v1 手写 TIR 取得 **-23.18% 的延迟降低**，从 3562 us 降至 2736 us。这是本项目继 transpose1 v7 (-1.97%) 和 variance4 v18 (-0.99%) 之后的第三个成功手写优化，也是**提升幅度最大的一次**。

优化原理与 variance4 v18 相同（working set reduction + normalized-mean handoff），再次验证了该原理在不同 shape 上的可迁移性。

## 影响分析

variance3 占总推理时间的 2.80%（3562 us / 127000 us total），优化后降至 ~2.15%，对端到端推理的贡献约为：

- 单次推理节省: 3562 - 2736 = **826 us**
- 端到端改善: 826 / 230750 (median e2e) ≈ **+0.36%**

## 相关文件

- TIR: `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py`
- Wrapper: `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1.py`
- Manifest: `session_bootstrap/handwritten/fused_variance3_add10_tir_sqrt3/scheduled_form_candidate_v1_working_copy_manifest.json`
