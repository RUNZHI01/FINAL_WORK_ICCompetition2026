# ACL 替换 55% 热点算子 vs 当前 MetaSchedule+handwritten 路线 — Reference-layer A/B Result

- date: 2026-04-04
- status: reference-layer-result
- experiment_definition: `session_bootstrap/reports/acl_replace_55pct_hotspots_ab_experiment_definition_20260404.md`

## 1. Scope

本报告只做 `reference-layer` A/B，对比：

- A 侧：当前 TVM MetaSchedule+handwritten 路线的热点参考耗时
- B 侧：ACL `F32` deconvolution 在对应 transpose-like shape 上的第一手参考耗时

**本报告不是直接替换实验，不触发 Trusted Current 升级。**

## 2. Inputs

### A side (TVM hotspot reference)
Source: `session_bootstrap/reports/profiling_judge_expanded_10samples_20260403.md`

- `fused_conv2d_transpose1_add9`: `~27.5 ms` (`21.61%`)
- `fused_conv2d_transpose2_add12`: `~22.5 ms` (`17.68%`)
- `fused_conv2d_transpose_add6`: `~20.4 ms` (`16.00%`)

### B side (ACL first runnable reference)
Source: `session_bootstrap/reports/acl_f32_deconvolution_first_benchmark_20260404.md`

- transpose1-like: `27.016 ms` (`127x127x24`)
- transpose2-like: `45.619 ms` (`255x255x12`)
- transpose_add6-like: `14.958 ms` (`63x63x48`)

## 3. A/B Table

| hotspot | TVM reference | ACL reference | initial label | note |
|---|---:|---:|---|---|
| `fused_conv2d_transpose1_add9` | `~27.5 ms` | `27.016 ms` | `roughly comparable / slightly faster numerically` | ACL output is `127`, not `128`; cannot claim direct replacement winner |
| `fused_conv2d_transpose2_add12` | `~22.5 ms` | `45.619 ms` | `ACL slower` | even before fairness normalization, ACL is clearly slower |
| `fused_conv2d_transpose_add6` | `~20.4 ms` | `14.958 ms` | `ACL faster-but-not-fair` | ACL output is `63`, not `64`; direct winner claim is not allowed |

## 4. What this report supports

This report supports the following statements:

1. ACL has moved beyond compile-only status and now has runnable F32 deconvolution evidence on Phytium Pi.
2. ACL does **not** show a clear broad win across the 55% hotspot family.
3. The second hotspot (`transpose2`) is currently a clear negative signal for ACL in stock form.
4. The first hotspot (`transpose1`) is close enough numerically to justify further investigation, but not enough to claim replacement success.
5. The third hotspot (`transpose_add6`) is encouraging numerically, but shape mismatch prevents a direct fairness claim.

## 5. What this report does NOT support

This report does **not** support the following statements:

- ACL has already replaced the 55% hotspot set in current model execution.
- ACL is already faster than MetaSchedule+handwritten at model level.
- ACL should replace Trusted Current.
- ACL stock `NEDeconvolutionLayer` is already a semantics-identical implementation of the three TVM transpose hotspots.

## 6. Engineering conclusion

Based on the current `reference-layer` A/B only:

- ACL is **worth keeping as a Phase 3 reference direction**.
- ACL is **not yet a proven replacement path** for the 55% hotspot group.
- If further work is done, the most justified next target is:
  1. decide whether `transpose1` deserves deeper fairness alignment,
  2. stop over-investing in `transpose2` unless a different ACL path exists,
  3. treat `transpose_add6` as an interesting but still non-final signal.

## 7. Recommendation

For now, the defensible project stance is:

> ACL has produced first runnable evidence and remains useful as a Phase 3 `conv2d_transpose` reference/breakthrough direction, but the current stock-API results are insufficient to declare it faster than the project's `MetaSchedule + handwritten` route for the 55% hotspot set.
