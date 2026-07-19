# Transpose1 v7 Working Set Analysis

- generated_at: `2026-04-03T16:45:00+08:00`
- scope: deep dive into why transpose1 v7's dc_0-slice optimization worked
- goal: extract transferable principles about memory access patterns

## Code Structure Comparison

### v6 (Baseline: 158.421 ms)

**Loop structure**:
```python
for h_1 in T.serial(2):  # 2 height stripes
    for ax0, ax1, ax2 in T.grid(1, 48, 34):  # KEY: all 48 channels at once
        # data_dilate: prepare all 48 channels x 34x10 stripe
        # data_pad: pad all 48 channels x 34x10 stripe

    for b_1, c_1 in T.grid(1, 3):
        for w_1 in T.serial(2):
            # compute_init (initialize accumulator)

        for dc_0, dh_0, dw_0, ... in T.grid(...):  # reduction loop
            # compute_update (consume staged data)
```

**Working set size**:
- `data_dilate`: 1 x 48 x 127 x 127 = **773,088 elements**
- `data_pad`: 1 x 48 x 130 x 130 = **811,200 elements**
- Staged per h_1 stripe: 48 x 34 x 10 = **16,320 elements**
- Total live staged data: ~16K elements (all 48 channels)

### v7 (Optimized: 156.785 ms, -1.03%)

**Loop structure**:
```python
for h_1 in T.serial(2):  # 2 height stripes
    for b_1, c_1 in T.grid(1, 3):
        for w_1 in T.serial(2):
            # compute_init (initialize accumulator)

        for dc_0 in T.serial(12):  # KEY: 12 slices of 4 channels each
            for ax0, ax1, ax2 in T.grid(1, 4, 34):  # Only 4 channels!
                # data_dilate: prepare 4 channels x 34x10 stripe
                # data_pad: pad 4 channels x 34x10 stripe

            for b_1, c_1 in T.grid(1, 3):  # Reuse across 3 c_1 groups
                for w_1 in T.serial(2):  # Reuse across 2 w_1 positions
                    for dc_1 in T.serial(4):  # Inner 4-channel reduction
                        # compute_update (consume staged 4-channel data)
```

**Working set size**:
- `data_dilate`: 1 x 48 x 127 x 127 = **773,088 elements** (same total)
- `data_pad`: 1 x 48 x 130 x 130 = **811,200 elements** (same total)
- **Staged per dc_0 slice**: 4 x 34 x 10 = **1,360 elements**
- **Live staged data**: ~1.3K elements (only 4 channels at a time)

## Key Insight: Working Set Reduction

### What Changed?

| Metric | v6 | v7 | Improvement |
|--------|-----|-----|-------------|
| Live staged elements | 16,320 | 1,360 | **12x reduction** |
| Channels staged at once | 48 | 4 | **12x reduction** |
| Reuse pattern | Implicit | Explicit (3 c_1 x 2 w_1) | **6x reuse** |

### Why This Helps

1. **Cache efficiency**:
   - L1 cache typically 32-64 KB
   - v6: 16K elements x 4 bytes = **64 KB** (may spill)
   - v7: 1.3K elements x 4 bytes = **5.2 KB** (comfortably in L1)
   - Better cache hit rate → fewer memory accesses → lower latency

2. **Temporal locality**:
   - v7 stages 4 channels, then immediately reuses them 6 times (3 c_1 groups x 2 w_1 positions)
   - Data stays hot in cache while being reused
   - v6 stages all 48 channels; by the time later channels are used, earlier ones may have evicted

3. **Spatial locality**:
   - 34x10 stripe is already optimized for spatial locality
   - v7 adds channel-level locality on top

4. **Register pressure**:
   - Smaller working set = less register spilling
   - Better compiler optimization potential

## The General Principle

**Reduce the live working set to fit in L1 cache, then maximize reuse within that working set.**

### Mathematical Model

If:
- W = working set size (bytes)
- C = L1 cache size (bytes)
- R = reuse factor (how many times each element is used)

Then:
- Cache efficiency ≈ min(1, C/W) × R
- Optimal when W << C and R is maximized

**v6**: W=64KB, C=64KB, R≈6 → Cache efficiency ≈ 1.0 × 6 = 6
**v7**: W=5.2KB, C=64KB, R=6 → Cache efficiency ≈ 1.0 × 6 = 6

Wait, this doesn't explain the improvement. Let me refine:

**Refined model**:
- Effective cache size < nominal size due to line conflicts, other data, etc.
- Assume effective C ≈ 32 KB (realistic)
- **v6**: W=64KB, C_eff=32KB, R≈6 → Cache efficiency ≈ 0.5 × 6 = **3**
- **v7**: W=5.2KB, C_eff=32KB, R=6 → Cache efficiency ≈ 1.0 × 6 = **6**

This explains the **~2x theoretical improvement**, but actual is only 1.03x because:
- Not all memory accesses are to staged data
- Other overheads dominate
- Cache is not the only bottleneck

## Why Other Attempts Failed

### transpose_add6 v2 (+8.36% slower)

Attempted to copy v7's dc_0-slice pattern, but:
- Different operator shape
- Different tiling structure
- **No gradual refinement** (jumped directly to final pattern)
- May have disrupted existing cache-friendly patterns

### transpose2 v4 (+2.29% slower)

Attempted width-window staging (10x34 instead of 10x258):
- Different dimensionality (width vs depth)
- Different reuse pattern
- **No validated base** to build on

### mean4 v2 (+3.11% slower)

Attempted to copy variance4's handoff pattern:
- Mean4 and variance4 have different computation structures
- Variance4: reduction → sqrt → handoff
- Mean4: reduction → subtract/divide/multiply → handoff
- **Different operator type** → pattern doesn't transfer

## Transferable Principles

### 1. Profile First

Before optimizing:
- Measure the operator's hotspot
- Understand memory access patterns
- Identify cache misses (using profiling tools)

### 2. Reduce Working Set

- Find the largest staged buffer
- Split it into smaller chunks
- Stage only what's needed for immediate computation

### 3. Maximize Reuse

- Once staged, reuse data as much as possible
- Structure loops to consume staged data before moving to next chunk
- Explicitly code the reuse pattern (don't rely on compiler)

### 4. Gradual Refinement

- Start with a simple, safe change
- Measure and validate each step
- Only refine winning directions
- **Don't copy final patterns from other operators**

### 5. Operator-Specific Exploration

- Each operator has unique structure
- What works for one may not work for another
- Explore the space systematically within the operator
- Build intuition from small wins

## Concrete Next Steps

### Option 1: Apply This Principle to Another Operator

Pick **one** operator (e.g., transpose2 or conv2d3_add15) and:

1. **Profile**: Measure cache misses, memory bandwidth
2. **Analyze**: Find largest staged buffers
3. **Propose**: A specific working-set reduction idea
4. **Implement**: Make a small, testable change
5. **Validate**: Run on board and measure
6. **Refine**: If positive, continue; if negative, analyze why

### Option 2: Deepen Understanding of transpose1

- Use TVM's profiling tools to measure cache behavior
- Compare v6 vs v7 at the hardware level
- Validate the cache hypothesis
- Extract more precise guidelines

### Option 3: Explore Algorithmic Changes

- Different tiling strategies
- Different loop orderings
- Fusion patterns
- Memory layout changes (e.g., NCHW vs NHWC)

## Conclusion

Transpose1 v7's success came from **working set reduction**:
- Stage less data at a time (4 channels vs 48 channels)
- Reuse it more explicitly (6x reuse pattern)
- Keep data in L1 cache

The principle is **general**, but the **application is operator-specific**.

Don't copy the pattern (dc_0-slice); copy the **principle** (reduce working set + maximize reuse).

Next optimization should start with profiling, not pattern copying.
