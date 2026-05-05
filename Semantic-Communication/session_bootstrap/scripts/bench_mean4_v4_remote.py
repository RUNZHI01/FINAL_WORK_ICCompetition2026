#!/usr/bin/env python3
"""Benchmark mean4 v4 (4 inputs) on Phytium Pi."""
import sys, time, json, os
sys.path.insert(0, '/home/user/tvm_samegen_20260307/python')
sys.path.insert(0, '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages')
sys.path.insert(0, '/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages')
import numpy as np
import tvm

so_path = sys.argv[1]
func_name = "fused_mean4_subtract4_divide4_multiply4_add14_relu3"

# Load module
lib = tvm.runtime.load_module(so_path)
func = lib[func_name]

# Prepare 4 inputs + 1 output
np.random.seed(42)
lv335 = np.random.randn(1, 12, 256, 256).astype(np.float32)  # input
lv340 = np.random.randn(1, 12, 1, 1).astype(np.float32)     # std (pre-computed)
lv340 = np.abs(lv340) + 0.1  # ensure positive (std)
lv342 = np.random.randn(12, 1, 1).astype(np.float32)        # weight
lv344 = np.random.randn(12, 1, 1).astype(np.float32)        # bias
output = np.zeros((1, 12, 256, 256), dtype=np.float32)

# Reference
mean = lv335.mean(axis=(2,3), keepdims=True)
expected = np.maximum(((lv335 - mean) / lv340) * lv342 + lv344, 0.0)

dev = tvm.cpu(0)
lv335_t = tvm.runtime.tensor(lv335, dev)
lv340_t = tvm.runtime.tensor(lv340, dev)
lv342_t = tvm.runtime.tensor(lv342, dev)
lv344_t = tvm.runtime.tensor(lv344, dev)
out_t = tvm.runtime.tensor(output, dev)

# Warmup
for _ in range(5):
    func(lv335_t, lv340_t, lv342_t, lv344_t, out_t)

# Benchmark
times = []
for _ in range(30):
    t0 = time.perf_counter()
    func(lv335_t, lv340_t, lv342_t, lv344_t, out_t)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1e6)

result = out_t.numpy()
max_diff = float(np.max(np.abs(result - expected)))
median_us = float(np.median(times))

output = {
    "operator": func_name,
    "version": "v4_fused",
    "correctness": {"max_abs_diff": max_diff, "passed": max_diff < 1e-3},
    "performance_us": {"median": median_us, "mean": float(np.mean(times)), "std": float(np.std(times)), "samples": 30},
    "baseline_median_us": 5000,
    "delta_pct": round((median_us - 5000) / 5000 * 100, 2),
}
print("JSON_RESULT:" + json.dumps(output, indent=2))
