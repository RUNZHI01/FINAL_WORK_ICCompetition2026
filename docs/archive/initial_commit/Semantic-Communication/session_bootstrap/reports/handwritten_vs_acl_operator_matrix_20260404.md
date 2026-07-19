# Handwritten vs ACL Operator Matrix（2026-04-04）

- date: `2026-04-04`
- board mode for latest fairness evidence: `OpenAMP 3-core`
- purpose:
  1. answer whether the current ACL line can evolve into a **multi-operator integrated replacement route**
  2. provide one consolidated table covering **all current handwritten lanes** and their relationship to ACL evidence

## 1. Short Answer

### 1.1 Can the current ACL line be turned into a multi-operator integrated route?

可以，但要分层回答：

1. **可以扩成“多 transpose 热点整合替换路线”**
   - 当前 ACL seam 已经证明可以沿 `packed-call` / runtime preload 方向继续走
   - 在当前项目里，最现实的 ACL 扩展目标是：
     - `fused_conv2d_transpose1_add9`
     - `fused_conv2d_transpose_add6`
     - `fused_conv2d_transpose2_add12`
   - 这三段都属于 transpose/deconvolution 家族，当前 repo 里也已经有 stock ACL `NEDeconvolutionLayer` 的实验基础

2. **不能直接等价替代我们现在的手写整合路线**
   - 当前手写整合路线真正成立的收益，不只来自 transpose
   - 还来自：
     - `fused_variance3_add10_tir_sqrt3`
     - `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
   - 这两段当前 repo 内**没有现成的 stock ACL 安全对位路径**

3. **所以更准确的结论是**
   - 当前 ACL **可以升级成“三个 transpose 一起替换”的 multi-op route**
   - 但**不能直接升级成“完整替代当前 handwritten final”的 route**
   - 如果真要做成和 handwritten route 同等级的整合路线，必须走：
     - `ACL(3 transpose) + 其它算子继续用 TVM/handwritten`
     - 或者 `ACL + 自定义 C++/NEON kernel`
     - 或者更重的 `BYOC / external codegen subgraph`

### 1.2 Practical Recommendation

如果目标是最短路径验证 ACL ceiling，我建议：

1. 不要再做 `transpose_add6` 单点
2. 直接把 ACL 扩到 `transpose1 + transpose_add6 + transpose2`
3. 但同时接受一个事实：
   - 即使三段 transpose 都换成 ACL，也**不自动等于**能打赢当前 handwritten route
   - 因为 handwritten 相对当前单点替换 line 的主要领先项，实际上来自 `mean4 + variance3`

## 2. Key Causal Finding

根据 OpenAMP 三核、当前计算图下的图内 runtime profiling：

- `Handwritten final` vs 当前 `602371c2...` 单点替换 line 的整图差距约为 **`-5.737 ms`**
- 这 `-5.737 ms` 的主要来源不是 transpose 单点，而是：
  - `mean4`: **`-6.530 ms`**
  - `variance3`: **`-0.942 ms`**
- 三段 transpose 两边其实已经很接近：
  - `transpose_add6`: `-0.513 ms`
  - `transpose1`: `-0.455 ms`
  - `transpose2`: `+0.470 ms`

所以当前项目里，**手写路线赢过单点 ACL 路线的根因，不是“单个 transpose 一定更强”，而是它覆盖了更多真正有收益的算子。**

## 3. Detailed Operator Table

说明：

- `最佳手写实测` 优先使用该 lane 自己最直接的实测结果：
  - 有 board payload 就用 board payload
  - 只有 standalone / synthetic A/B 时就注明类型
- `3-core 图内中位数` 指 OpenAMP 三核、当前 JSCC 图下的 runtime profiling
- `ACL 实测` 只填写 repo 内**当前真的有数字**的部分
- `可直接公平比较` 的标准很严格；没有满足时会明确写 `否`

| Operator | 当前手写状态 | 最佳手写实测 | OpenAMP 3-core 图内中位数 | stock ACL 当前有无直接对位 | ACL 实测 | 可直接公平比较 | 当前可 defend 的结论 |
|---|---|---|---:|---|---|---|---|
| `fused_conv2d_transpose1_add9` | `v7` promoted | board payload `156.785 ms`, vs ref `-1.97%` | trusted current `55.016 ms` | 有，`transpose1_asym` | standalone rerun `26.611 ms` | 否 | ACL 可以继续做，但当前 repo 里还没有 stock ACL 真正入图后的公平证据；手写这条已经 board-proven |
| `fused_conv2d_transpose_add6` | `v1` accepted, `v2` dropped | board payload `159.503 ms`, vs ref `-0.28%` | trusted current `40.916 ms` | 有，`transpose_add6_asym` | standalone rerun `16.771 ms` | **部分** | 这是 ACL 最值得继续追的 seam；但旧的 `ACL +33.9%` 口径已失效，不能再直接拿来写正文 |
| `fused_conv2d_transpose2_add12` | `v1` accepted baseline, follow-ups regressed | board payload `161.416 ms`, vs ref `+0.92%` | trusted current `43.912 ms` | 有，`transpose2_asym` | standalone rerun `51.505 ms` | 否 | 目前可见证据不支持把它写成 ACL 强项；即使走 ACL，也必须先补真入图证据 |
| `fused_variance4_add13_tir_sqrt4` | `v18` frozen | board payload `158.347 ms`, vs ref `-1.00%` | trusted current `~7.045 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 这是一个真实存在但幅度较小的手写正收益；ACL 现在没有对应落地线 |
| `fused_variance3_add10_tir_sqrt3` | `v1.1` keep | standalone `2771 us`, vs baseline `-22.2%`; `variance3_only` e2e `247.9 ms`, vs trusted `+0.39%` | trusted current `3.581 ms`; handwritten final `2.744 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 这是手写整合路线里的关键收益点之一，也是 ACL 目前没有覆盖到的原因之一 |
| `fused_variance1_add3_tir_sqrt1` | `v1` compiled and synthetic-tested, integrated result dropped | standalone `1315 us`, vs baseline `-73.7%`; `variance1_only` e2e `263.4 ms`, vs trusted `+4.6%` | trusted current `~5.163 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 典型例子：单算子很漂亮，但整图回归；也说明不能用 isolated benchmark 直接推端到端 |
| `fused_mean4_subtract4_divide4_multiply4_add14_relu3` | `v4` keep | standalone `4558 us`, vs baseline `-8.8%`; `mean4_only` e2e `242.9 ms`, vs trusted `-3.26%` | trusted current `3.102 ms`; handwritten final `4.648 ms`; current `602...` line `11.178 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 这是 handwritten 相对当前单点替换 line **最关键的领先来源**，也是当前 ACL 路线无法直接复现的原因之一 |
| `fused_mean1_subtract1_divide1_multiply1_add4` | `v1` compiled only, not batch-benchmarked on board | 暂无正式实测 | trusted current `~4.215 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 这条 lane 目前只有编译，没有正式性能证据 |
| `fused_conv2d3_add15` | `v2` dropped | board payload `161.999 ms`, vs baseline `+0.62%` | trusted current `~28.497 ms` | 当前 repo 无直接 ACL 路线 | N/A | 否 | 手写已证实这条线当前没有收益；ACL 也没有现成替换实验 |

## 4. ACL-Composable Subset

如果只看“当前最有可能被 ACL 组成 multi-op route 的子集”，实际上只有这三段：

| ACL-ready subset | Handwritten best | ACL current evidence | Route recommendation |
|---|---|---|---|
| `transpose1` | `156.785 ms` full-model payload (`v7`) | `26.611 ms` standalone asym | 可纳入 multi-transpose ACL route，但先别单独立结论 |
| `transpose_add6` | `159.503 ms` full-model payload (`v1`) | `16.771 ms` standalone asym | ACL 当前最值得追的单点 |
| `transpose2` | `161.416 ms` full-model payload (`v1`) | `51.505 ms` standalone asym | 现有 ACL 信号偏负，优先级最低 |

这意味着：

- **ACL multi-op route 的现实版本，不是“ACL 替代所有 handwritten 算子”**
- 而是 **“ACL 三个 transpose 一起替换，variance/mean 仍留在 TVM/handwritten 侧”**

## 5. Writing-Friendly Conclusion

如果你要把这部分自然写进正文，建议直接用下面这层逻辑：

1. 先说当前项目里真正有 ACL 实验基础的，是三个 transpose/deconvolution 热点。
2. 再说手写路线当前已经覆盖到 `variance3 + mean4 + transpose family` 的组合收益。
3. 接着说明：handwritten 相对当前单点替换 line 的主要领先项，实际上来自 `mean4 + variance3`，不是来自某一个 transpose 单点。
4. 最后自然落结论：

> 因此，当前项目里 ACL 更适合作为一个“可继续扩展到多 transpose 热点的替换路线”，而当前已经更成熟、更完整、端到端更可 defend 的路线，仍然是手写多算子整合优化。
