#!/usr/bin/env python3
"""Benchmark a pre-compiled .so module on Phytium Pi.
Usage: bench_so_module.py <so_path> <func_name> <input_shape> <output_shape> <version_label> [baseline_us]
"""
import sys, time, json, os
sys.path.insert(0, '/home/user/tvm_samegen_20260307/python')
sys.path.insert(0, '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages')
sys.path.insert(0, '/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages')
import numpy as np
import tvm

so_path = sys.argv[1]
func_name = sys.argv[2]
input_shape = tuple(int(x) for x in sys.argv[3].split(","))
output_shape = tuple(int(x) for x in sys.argv[4].split(","))
version_label = sys.argv[5]
baseline_us = float(sys.argv[6]) if len(sys.argv) > 6 else None

# Load pre-compiled module
lib = tvm.runtime.load_module(so_path)
func = lib[func_name]

# Prepare data
np.random.seed(42)
input_np = np.random.randn(*input_shape).astype(np.float32)
output_np = np.zeros(output_shape, dtype=np.float32)

# Reference computation (variance pattern)
if len(input_shape) == 4 and len(output_shape) == 4 and output_shape[2] == 1:
    reduce_axes = (2, 3)
    input_mean = input_np.mean(axis=reduce_axes, keepdims=True)
    centered = input_np - input_mean
    variance = (centered ** 2).mean(axis=reduce_axes, keepdims=True)
    expected = np.sqrt(variance + 9.9999997473787516e-06)
else:
    expected = output_np

dev = tvm.cpu(0)
input_tvm = tvm.runtime.tensor(input_np, dev)
output_tvm = tvm.runtime.tensor(output_np, dev)

# Warmup
for _ in range(5):
    func(input_tvm, output_tvm)

# Benchmark
n_samples = 30
times = []
for _ in range(n_samples):
    t0 = time.perf_counter()
    func(input_tvm, output_tvm)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1e6)

result = output_tvm.numpy()
max_diff = float(np.max(np.abs(result - expected)))
rel_diff = max_diff / (float(np.max(np.abs(expected))) + 1e-8)
median_us = float(np.median(times))

output = {
    "operator": func_name,
    "version": version_label,
    "so_file": os.path.basename(so_path),
    "correctness": {"max_abs_diff": max_diff, "relative_diff": rel_diff, "passed": max_diff < 1e-3},
    "performance_us": {"median": median_us, "mean": float(np.mean(times)), "min": float(np.min(times)), "max": float(np.max(times)), "std": float(np.std(times)), "samples": n_samples},
}
if baseline_us:
    output["baseline_median_us"] = baseline_us
    output["delta_pct"] = round((median_us - baseline_us) / baseline_us * 100, 2)

print("JSON_RESULT:" + json.dumps(output, indent=2))
