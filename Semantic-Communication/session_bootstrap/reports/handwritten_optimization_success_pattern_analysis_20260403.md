# Handwritten Optimization Success Pattern Analysis

- generated_at: `2026-04-03T16:35:00+08:00`
- scope: analyze why some optimizations worked and others failed
- goal: extract transferable insights from successful lanes

## Success Cases

### transpose1 v7 (-1.97%)

**Evolution path**:
- v1: baseline
- v4: first locality (-1.16% vs baseline)
- v6: h_1 stripe-staging
- v7: **dc_0-slice on top of v6** (-1.03% vs v6)

**Key insight**:
- Success came from **gradual refinement within the same operator**
- v7 built on v6's winning pattern
- Each iteration was tested and validated before the next
- Final pattern: staged 34x10 stripe → narrowed to dc_0 4-channel slice → reused across c_1/w_1

### variance4 v18 (-1.00%)

**Evolution path**:
- v1-v13: various attempts (many flat or negative)
- v14-v19: **handoff micro-optimization family**
- v18: **centered-value + normalized-mean handoff** (winner)

**Key insight**:
- Success came from **repeatedly refining the same handoff pattern**
- v15 → v17 → v18: each was a small tweak on the previous
- v18: materialized centered value once before squaring
- Pattern: reuse/handoff style micro-moves, not scope stacking

## Failure Cases

### transpose_add6 v2 (+8.36%)

**Attempt**: Copy transpose1's dc_0-slice pattern

**Why it failed**:
- transpose1 had v4 → v6 → v7 gradual refinement
- transpose_add6 v2 tried to jump directly to the final pattern
- No intermediate validation within the operator
- **Pattern transfer without gradual refinement**

### transpose2 v4 (+2.29%)

**Attempt**: Width-window staging (10x34)

**Why it failed**:
- Previous attempts (P2, P4, v2, v3) were all different directions
- v4 was a **new direction**, not a refinement
- No validated base pattern to build on
- **Jumped to a new pattern without establishing the base**

### mean4 v2 (+3.11%)

**Attempt**: Copy variance4's scalar handoff pattern

**Why it failed**:
- variance4 went through v15 → v17 → v18 gradual refinement
- mean4 v2 tried to copy the final pattern directly
- mean4 and variance4 have different computation structures
- **Pattern transfer across different operator types**

## Key Finding: Gradual Refinement vs Pattern Transfer

| Aspect | Success Pattern | Failure Pattern |
|--------|----------------|-----------------|
| Evolution | Within-operator gradual refinement | Cross-operator pattern copy |
| Iterations | 3-7 iterations in same lane | 1 attempt with borrowed pattern |
| Validation | Each step validated before next | Jump directly to final pattern |
| Base | Built on previous success in same op | No validated base in target op |

## Concrete Insight

**The optimization space is highly operator-specific**:

1. **transpose1**'s dc_0-slice worked because:
   - It was the 3rd refinement in a winning family
   - v6 established the stripe-staging base
   - v7 just narrowed the slice within that base

2. **variance4**'s handoff worked because:
   - It was the 4th refinement in the handoff family
   - v15-v17 explored different handoff shapes
   - v18 found the right combination

3. **transpose_add6 v2** failed because:
   - No v4/v6 equivalent in transpose_add6
   - Tried to copy the final pattern without the base

4. **mean4 v2** failed because:
   - No v15-v17 equivalent in mean4
   - Variance4's handoff pattern doesn't transfer to mean4's structure

## Actionable Recommendation

### Option 1: Deep Dive into Successful Operators

**transpose1**:
- Analyze why dc_0-slice worked at the TIR level
- Understand the memory access pattern
- Extract the **principle**, not the pattern

**variance4**:
- Analyze why handoff micro-optimizations worked
- Understand the reduction/epilogue structure
- Extract the **principle**, not the pattern

### Option 2: Gradual Exploration of New Operators

**For any new operator**:
1. Start with a simple, safe change (like v1 baseline)
2. Make one small change at a time
3. Validate each step on board
4. Only refine the winning direction
5. Don't copy final patterns from other operators

### Option 3: Algorithm-Level Changes

Instead of schedule-level micro-optimizations:
- Explore algorithmic changes
- Different tiling strategies
- Different loop organizations
- NEON intrinsics for critical compute

## Concrete Next Steps

Given the current evidence:

1. **Analyze transpose1 v7's TIR**:
   - What is the memory access pattern?
   - Why does dc_0-slice help?
   - Can we extract a general principle?

2. **Analyze variance4 v18's TIR**:
   - What is the handoff pattern?
   - Why does centered-value materialization help?
   - Can we extract a general principle?

3. **Pick one operator** and do gradual refinement:
   - Start simple
   - One change at a time
   - Validate each step
   - Don't jump to final patterns

4. **Consider a different approach**:
   - NEON intrinsics
   - Algorithmic changes
   - Fusion patterns
   - Memory layout changes

## Conclusion

The evidence strongly suggests that **gradual, operator-specific refinement** is the winning pattern, not **cross-operator pattern transfer**.

Next move should be either:
- Deep analysis of successful operators to extract principles
- OR gradual exploration of a new operator with validated intermediate steps
- OR a fundamentally different optimization approach (NEON, algorithmic)
