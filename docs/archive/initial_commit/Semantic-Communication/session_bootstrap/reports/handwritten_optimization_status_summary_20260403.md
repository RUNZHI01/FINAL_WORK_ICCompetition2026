# Handwritten Optimization Status Summary (2026-04-03)

- generated_at: `2026-04-03T16:50:00+08:00`
- scope: summary of all handwritten operator optimization attempts

## Overall Results

### Successful Optimizations (2/8 operators)

| Operator | Best Version | Median | vs Baseline | Status |
|----------|-------------|--------|-------------|--------|
| `fused_conv2d_transpose1_add9` | v7 | 156.785 ms | **-1.97%** | ✅ Promoted |
| `fused_variance4_add13_tir_sqrt4` | v18 | 158.347 ms | **-0.99%** | ✅ Frozen |

**Total gain**: ~3 ms improvement across 2 operators

### Failed Optimizations (6 attempts)

| Operator | Attempt | Median | vs Baseline | Status |
|----------|---------|--------|-------------|--------|
| `fused_conv2d_transpose_add6` | v2 | 172.836 ms | **+8.36%** | ❌ Dropped |
| `fused_conv2d_transpose2_add12` | v4 | 165.113 ms | **+2.29%** | ❌ Dropped |
| `fused_mean4_...` | v2 | 340.201 ms | **+3.11%** | ❌ Dropped |
| `fused_conv2d3_add15` | v2 | 161.999 ms | **+0.62%** | ❌ Dropped |
| `fused_variance4_...` | v19 | 158.556 ms | **+0.13%** | ❌ Dropped |
| `fused_conv2d_transpose1_add9` | v8 | - | - | ❌ Dropped (narrowing) |

**Pattern**: All recent attempts are regressions

## Key Learnings

### 1. Pattern Transfer Fails

Copying successful patterns from one operator to another **does not work**:

- transpose_add6 v2 tried to copy transpose1's dc_0-slice → +8.36%
- mean4 v2 tried to copy variance4's handoff → +3.11%
- transpose2 v4 tried a new direction without base → +2.29%

### 2. Gradual Refinement Works

Success came from **within-operator iterative refinement**:

- transpose1: v1 → v4 → v6 → **v7** (4 iterations)
- variance4: v15 → v17 → **v18** (3 iterations)

Each step was validated before the next.

### 3. Working Set Reduction Principle

**Extracted principle** (from transpose1 v7 analysis):
- Reduce live working set to fit in L1 cache
- Maximize reuse within that working set
- **Principle is general, application is operator-specific**

### 4. Operator Space is Exhausted

**Exhausted operators** (multiple failed attempts):
- transpose_add6 (v2 failed, no obvious next direction)
- transpose2 (P2, P4, v1/v2, v3, v4 all failed)
- mean4 (v2 failed)
- conv2d3_add15 (P2, P4, v2 all failed)
- variance4 (v19 failed, frozen at v18)

**Untouched operators**:
- mean3 (no handwritten lane yet)
- variance3 (no handwritten lane yet)

## Decision Point

### Current Situation

1. **High-value operators have been explored**
   - All top hotspots (transpose1/2, transpose_add6, conv2d3_add15, mean4, variance4) have attempts
   - Most have hit diminishing returns

2. **Recent success rate is low**
   - Last 6 consecutive attempts are regressions
   - Pattern transfer approach has been disproven

3. **Low-hanging fruit is gone**
   - Only remaining unexplored operators are smaller (mean3: 3.50%, variance3: 2.15%)
   - Expected upside is limited

### Options

#### Option A: Continue Handwritten Exploration

**Target**: `fused_mean3` or `fused_variance3`

**Approach**:
1. Create handwritten lane from scratch
2. Profile to understand memory access patterns
3. Apply working set reduction principle (not pattern copying)
4. Gradual refinement: one small change at a time
5. Validate each step on board

**Expected upside**: Small (operators are 3.50% and 2.15% of runtime)
**Expected effort**: High (new lane setup, multiple iterations)
**Risk**: High (recent success rate is low)

#### Option B: Pivot to Other High-Value Work

**Targets**:
1. **Demo 真实彩排 / UI / operator flow** (追踪板 priority 1)
   - Complete presentation-day checklist
   - Verify operator flow
   - Blocker: 需要 SSH 凭据和板卡访问

2. **OpenAMP 剩余真机协议 / FIT 缺口** (追踪板 priority 2)
   - FIT-04/05, TC-007/008/009
   - Blocker: 需要 firmware patch 应用

3. **judge-facing 实测扩样本** (追踪板 priority 3)
   - Runtime profiling
   - Multi-sample benchmarks

**Expected upside**: High (presentation readiness, evidence completeness)
**Expected effort**: Medium
**Risk**: Low (work is well-defined)

## Recommendation

Given:
- Recent 0/6 success rate on handwritten optimizations
- High-value operators are mostly exhausted
- Clear alternative high-value work exists

**Recommendation**: **Pivot to Demo / OpenAMP / judge-facing work**

Rationale:
1. Diminishing returns on handwritten optimization
2. Better ROI on presentation/evidence work
3. Can return to handwritten optimization if genuinely new ideas emerge

## If Continuing Handwritten Optimization

If decision is to continue despite the recommendation:

1. **Pick one operator**: mean3 or variance3
2. **Start with profiling**: Use TVM's profiling tools
3. **Propose specific hypothesis**: Don't just "try patterns"
4. **Make smallest testable change**: Validate principle, not pattern
5. **Accept smaller upside**: These operators are smaller hotspots

## Evidence

All reports referenced in:
- `session_bootstrap/reports/project_speedup_rerank_after_mean4_v2_regression_20260403.md`
- `session_bootstrap/reports/handwritten_optimization_success_pattern_analysis_20260403.md`
- `session_bootstrap/reports/transpose1_v7_working_set_analysis_20260403.md`
