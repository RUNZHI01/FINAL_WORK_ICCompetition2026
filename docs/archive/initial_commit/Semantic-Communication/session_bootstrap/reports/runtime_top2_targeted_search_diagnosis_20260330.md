# Runtime-top2 定向深搜诊断结论（2026-03-30）

## 结论一句话

这轮 `runtime-top2` 定向深搜 **在被调两个 hotspot 上是成功的**，但 **集成后的新 artifact 不能进入 trusted current 主线**，因为 safe runtime payload / runtime profile 显示整体性能严重回归，热点已转移到未被调的其它算子。

## 本轮对象

- run id: `phytium_runtime_top2_targeted_search_20260330_1949`
- scaffold commit: `fe28a63` (`tvm: add runtime-top2 targeted search scaffold`)
- targeted ops:
  - `fused_conv2d_transpose2_add12`
  - `fused_conv2d_transpose1_add9`
- new artifact sha256: `2eb2f8777dd72b46747ebb82738eba5659b5c284983e6c20c349eb4f464d2ca5`
- trusted current sha256 (restored after diagnosis): `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## 1. 定向深搜本身拿到了明显收益

来自 tuning scheduler 的最终 best：

- `fused_conv2d_transpose2_add12`
  - start: `31922.4940 us`
  - best: `20248.3320 us`
  - delta: `-36.6%`
  - best GFLOPS: `16.8174`
- `fused_conv2d_transpose1_add9`
  - start: `31881.8405 us`
  - best: `18691.4922 us`
  - delta: `-41.4%`
  - best GFLOPS: `18.1971`

因此，**Step 2「runtime-top2 hotspot 定向深搜」方向本身成立**。

## 2. 但新 artifact 的 safe runtime payload 严重回归

新 artifact (`2eb2...`) 在 safe runtime payload 验证中的结果：

- report: `session_bootstrap/reports/phytium_runtime_top2_targeted_search_20260330_1949.md`
- `run_median_ms = 1470.67`
- `run_mean_ms = 1471.956`
- `run_variance_ms2 = 33.473725`

这与 trusted current 主线的正式口径不在一个量级，因此 **不能 promote**。

## 3. 为什么会回归：runtime hotspot 已经发生转移

对新 artifact 重新做 runtime per-op profiling（已更新 expected SHA 后复验）：

- report: `session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055.md`
- `run_median_ms = 1659.636`

新的 runtime top ops：

1. `fused_conv2d_transpose_add6` → `497266.467 us` (`32.59%`)
2. `fused_conv2d3_add15` → `281567.810 us` (`18.45%`)
3. `fused_conv2d_add2` → `61336.122 us` (`4.02%`)
4. `fused_conv2d2_add2` → repeated around `56.6 ms` each call

而本轮被调的两个 op 反而已经掉到：

- `fused_conv2d_transpose2_add12` → `20039.646 us` (`1.31%`)
- `fused_conv2d_transpose1_add9` → `19916.249 us` (`1.31%`)

这说明：

- top-2 deconv hotspot 的确被压下去了；
- 但集成后，系统瓶颈 **转移** 到了 `fused_conv2d_transpose_add6`、`fused_conv2d3_add15` 和一串 `fused_conv2d2_add2`；
- 因此这轮 artifact 的总体效果是 **局部成功、全局失败**。

## 4. 主线善后：已恢复 remote current archive

为避免坏 artifact 污染 trusted current 主线，已把 remote current archive 恢复到 trusted chunk4：

- restored local source:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- restored remote path:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- restored sha256:
  - `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

并已做最小 current real run 复验：

- `run_median_ms = 274.775` (single sample reprobe)
- `artifact_sha256_match = true`

说明主线 current 已从坏 artifact 中恢复。

## 5. 下一步建议（直接服务于 TVM 主线）

### 不建议

- 不建议把 `2eb2...` 这版 artifact 作为新的 current promote。
- 不建议立刻切手写 TIR，只因为 top-2 单算子收益很好；因为集成后的瓶颈已经转移了。

### 建议

下一轮定向深搜应改为 **runtime-shifted top set**，至少覆盖：

- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`
- 保留对 `fused_conv2d_transpose2_add12` / `fused_conv2d_transpose1_add9` 的已有结果作参考，而不是继续单独加预算

更具体地说：

1. 保留这轮结果，作为“runtime-top2 定向深搜可显著压低局部热点”的证据；
2. 下一轮不要再只盯原 top-2，而要基于 **新 artifact 的 runtime reprobe** 更新目标名单；
3. 如果再做手写 TIR / NEON，优先候选应转向新的 runtime top-1 / top-2，而不是继续围绕旧 top-2。

## 6. 可直接引用的证据入口

- 定向深搜 summary:
  - `session_bootstrap/reports/phytium_runtime_top2_targeted_search_20260330_1949.md`
- 新 artifact runtime reprobe:
  - `session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055.md`
- trusted current runtime hotspot old reference:
  - `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- trusted chunk4 artifact registry reference:
  - `session_bootstrap/runbooks/artifact_registry.md`
