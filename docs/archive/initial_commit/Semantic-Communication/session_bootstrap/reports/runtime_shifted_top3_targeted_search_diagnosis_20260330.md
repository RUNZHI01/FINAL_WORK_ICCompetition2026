# Runtime-shifted-top3 定向深搜诊断结论（2026-03-30）

## 结论一句话

这轮 `runtime-shifted-top3` 定向深搜 **在新目标集上继续拿到了明显局部收益**，但 **集成后的新 artifact 仍然不能进入 trusted current 主线**；和上一轮一样，局部热点被压下去后，runtime 瓶颈再次转移，形成了新的“热点回弹”。

## 本轮对象

- run id: `phytium_runtime_shifted_top3_targeted_search_20260330_2103`
- base diagnosis: `session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- new artifact sha256: `23beda366cefda56f4f620bac29be1ed26e23ee2f290df00429a1c417e0720b3`
- trusted current sha256 (restored after diagnosis): `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## 1. Shifted-top3 局部调优本身是成功的

本轮 target ops：

- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`

调度器里可确认的改善：

- `fused_conv2d_transpose_add6`
  - first best: `25836.1172 us`
  - final best: `16769.0585 us`
  - delta: `-35.1%`
  - best GFLOPS: `20.2716`
- `fused_conv2d3_add15`
  - first best: `19080.4718 us`
  - final best: `11897.8224 us`
  - delta: `-37.6%`
  - best GFLOPS: `19.4496`
- `fused_conv2d2_add2`
  - first best: `1812.5572 us`
  - final best: `1154.7356 us`
  - delta: `-36.3%`
  - best GFLOPS: `16.4303`
  - 因为 `weight=10`，weighted latency 从 `18125.5719 us` 降到 `11547.3564 us`

因此，**第二轮 shifted-top3 retarget 方向本身也是成立的**。

## 2. 但 integrated artifact 在 safe runtime payload 上比上一轮回归更重

summary 见：

- `session_bootstrap/reports/phytium_runtime_shifted_top3_targeted_search_20260330_2103.md`

关键结果：

- `run_median_ms = 2110.348`
- `run_mean_ms = 2099.158`
- `run_variance_ms2 = 19069.838758`

这比上一轮 runtime-top2 新 artifact 的 `1470.67 ms` 还更差，也远离 trusted current 主线口径，因此 **绝不能 promote**。

## 3. 新 artifact 的 runtime per-op profile：瓶颈再次回弹到旧 top-2

对 `23beda...` 新 artifact 做 reprobe：

- report: `session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200.md`
- `run_median_ms = 1391.62` (single-sample reprobe)

新的 runtime top ops：

1. `fused_conv2d_transpose1_add9` → `522451.650 us` (`42.58%`)
2. `fused_conv2d_transpose2_add12` → `522262.929 us` (`42.57%`)
3. `fused_conv2d_add2` → `61507.705 us` (`5.01%`)
4. `fused_conv2d_transpose_add6` → `17088.022 us` (`1.39%`)
5. `fused_conv2d3_add15` → `12254.977 us` (`1.00%`)

也就是说：

- shifted-top3 的三个目标确实都被压下去了；
- 但 integrated artifact 的热点 **又反弹回** 上一轮 top-2：
  - `fused_conv2d_transpose1_add9`
  - `fused_conv2d_transpose2_add12`
- 这说明目前两轮定向深搜都在出现同一个模式：
  - **被调目标局部变快**；
  - **未被保护的其它关键路径在集成后重新主导 end-to-end runtime**。

## 4. 这意味着什么

当前不能再把结果简单解读成“热点名单不对”；更准确的解读是：

- 用单次 runtime hotspot 排名做少数 op 的定向深搜，**可以**拿到显著局部收益；
- 但对当前模型/target/runtime 组合来说，局部最优 schedule 很可能破坏整体执行平衡；
- 因此 integrated artifact 的真实性能不服从“单点热点逐个压下去就会全局更快”的简单规律。

换句话说：

> 现在的问题已经从“不会找热点”变成了“如何避免局部最优在 integrated artifact 上制造新的全局瓶颈”。

## 5. 主线善后：已恢复 remote current archive

为避免继续污染主线，已把 remote current archive 恢复到 trusted chunk4：

- restored local source:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- restored remote path:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- restored sha256:
  - `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

并已做最小 current real run 复验：

- `run_median_ms = 280.181` (single sample)
- `artifact_sha256_match = true`

说明主线 current 再次恢复干净。

## 6. 下一步建议

### 不建议

- 不建议立刻开第三轮“继续换 3 个新 hotspot 再定向”的 blind retarget。
- 不建议把 `23beda...` 这版 artifact 作为 current candidate 保留在远端 archive 中。

### 建议

下一步优先级应改成下面二选一（或先 A 后 B）：

#### A. 建立更严格的 promotion gate

在任何新 tuning artifact 上传覆盖 remote current archive 之前，先执行：

1. isolated archive / temp path 验证；
2. safe runtime payload 最小 repeat 验证；
3. runtime reprobe；
4. 只有通过门槛才 promote。

这样可以避免主线 repeatedly 被坏 artifact 污染。

#### B. 如果继续做性能线，改成“联合目标集 / 更保守搜索”

与其再做单次热点重定向，不如试：

- 联合目标集（例如原 top-2 + shifted-top3）
- 或降低单 task 进攻性，避免某个局部最优把整体 balance 打崩

### 手写 TIR 的位置

当前不建议直接上手写 TIR，除非先回答：

- 我们要优化的是局部 top op 本身；
- 还是要先解决 integrated artifact 的稳定全局平衡问题。

在没建立 promotion gate 之前，直接进入手写 TIR，很可能只是把“局部更优、整体更差”的问题做得更剧烈。

## 7. 可直接引用的证据入口

- shifted-top3 summary:
  - `session_bootstrap/reports/phytium_runtime_shifted_top3_targeted_search_20260330_2103.md`
- shifted-top3 artifact reprobe:
  - `session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200.md`
- first-round runtime-top2 diagnosis:
  - `session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- trusted artifact registry reference:
  - `session_bootstrap/runbooks/artifact_registry.md`
