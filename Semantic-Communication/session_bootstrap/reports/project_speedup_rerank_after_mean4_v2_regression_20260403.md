# Project Speedup Rerank After Mean4 v2 Regression

- generated_at: `2026-04-03T16:30:00+08:00`
- scope: rerank the handwritten speedup lanes after the third consecutive regression
- decision: `pause active handwritten optimization; recommend pivot to Demo / OpenAMP / judge-facing work`

## Facts This Rerank Must Absorb

### Completed Board Results

| Operator | Best Result | Latest Attempt | Latest Delta | Status |
|----------|-------------|----------------|--------------|--------|
| `fused_conv2d_transpose1_add9` | v7: 156.785 ms (-1.97%) | - | - | ✅ **Promoted** |
| `fused_variance4_add13_tir_sqrt4` | v18: 158.347 ms (-0.99%) | v19: 158.556 ms (+0.13%) | ✅ **Frozen at v18** |
| `fused_conv2d_transpose_add6` | v1: 159.503 ms (-0.28%) | v2: 172.836 ms (+8.36%) | ❌ Regressed |
| `fused_conv2d_transpose2_add12` | v1: 161.416 ms (+0.92%) | v4: 165.113 ms (+2.29%) | ❌ Regressed |
| `fused_mean4_subtract4_divide4_multiply4_add14_relu3` | - | v2: 340.201 ms (+3.11%) | ❌ Regressed |
| `fused_conv2d3_add15` | v1: 161.000 ms (+0.66%) | v2: 161.999 ms (+0.03%) | ❌ Regressed |

### Pattern Analysis

**Three consecutive regression pattern**:
1. `transpose_add6 v2`: locality edit (dc0-slice) → **+8.36%**
2. `transpose2 v4`: locality edit (width-window) → **+2.29%**
3. `mean4 v2`: handoff edit (scalar epilogue) → **+3.11%**

**Commonality**:
- All three attempted to transfer "winning patterns" from one operator to another
- `transpose_add6 v2` tried `transpose1`-style locality
- `transpose2 v4` tried width-window staging
- `mean4 v2` tried `variance4`-style scalar handoff

**Implication**:
- The optimization space is more operator-specific than expected
- Pattern transfer without deep operator-specific analysis is not paying off
- We may be hitting diminishing returns on the current optimization family

## Re-ranked Priorities

### Tier 1: High-Value Non-Optimization Work

Given the regression pattern, the highest-ROI work is **not** more handwritten optimization attempts, but:

1. **Demo 真实彩排 / UI / operator flow** (追踪板优先级 1)
   - `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`
   - This directly impacts presentation readiness
   - Blocked on:真实 SSH credentials and board access

2. **OpenAMP 剩余真机协议 / FIT 缺口** (追踪板优先级 2)
   - `session_bootstrap/reports/openamp_remaining_protocol_fit_runplan_2026-04-03.md`
   - FIT-04/05, TC-007/008/009
   - Blocked on: firmware patch application

3. **judge-facing 实测扩样本** (追踪板优先级 3)
   - Runtime profiling enablement
   - Multi-sample benchmark runs
   - Statistical confidence improvements

### Tier 2: Handwritten Optimization (Conditional)

Only resume handwritten optimization if:

1. **A materially different idea emerges**
   - Not more locality edits
   - Not more handoff micro-optimizations
   - Something genuinely new (e.g., NEON intrinsics, algorithm-level changes)

2. **Deep analysis of successful lanes**
   - Why did `transpose1 v7` work?
   - Why did `variance4 v18` work?
   - What's the operator-specific pattern?

3. **Return to already-successful lanes**
   - `transpose1`: explore v9 seam-carry with deeper analysis
   - `variance4`: different handoff shapes (not just scalar)

### Tier 3: Deprioritized

- **More locality edits**: `transpose_add6`, `transpose2`, `mean4` all tried this and regressed
- **More handoff micro-optimizations**: `mean4 v2` showed this doesn't transfer well
- **Blind pattern transfer**: the three regressions show operator-specificity matters

## Concrete Recommendation

**Pause active handwritten optimization** and pivot to:

1. **Demo 真实彩排** (highest immediate ROI)
   - Complete the presentation-day checklist
   - Verify UI / operator flow
   - Fill in the go-no-go template

2. **OpenAMP 剩余协议** (if firmware is available)
   - FIT-04/05
   - TC-007/008/009

3. **judge-facing work** (if time permits)
   - Runtime profiling
   - Multi-sample benchmarks

## When to Resume Handwritten Optimization

Only consider resuming when:

1. A genuinely new optimization direction emerges
2. OR deep analysis of `transpose1 v7` / `variance4 v18` reveals transferable insights
3. OR presentation/OpenAMP work is complete and there's time for exploratory work

## Evidence

- `transpose1 v7`: `session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- `variance4 v18`: `session_bootstrap/reports/variance4_v18_remote_benchmark_20260403_0239.md`
- `variance4 v19`: `session_bootstrap/reports/variance4_v19_remote_benchmark_20260403_0307.md`
- `transpose_add6 v2`: `session_bootstrap/reports/transpose_add6_v2_dc0_slice_remote_benchmark_20260403_0030.md`
- `transpose2 v4`: `session_bootstrap/reports/transpose2_v4_remote_benchmark_20260403_0343.md`
- `mean4 v2`: `session_bootstrap/reports/mean4_v2_remote_benchmark_20260403_1627.md`
