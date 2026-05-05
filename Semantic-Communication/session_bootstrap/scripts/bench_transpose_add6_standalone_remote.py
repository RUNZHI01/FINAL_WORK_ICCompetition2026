#!/usr/bin/env python3
import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, '/home/user/tvm_samegen_20260307/python')
sys.path.insert(0, '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages')
sys.path.insert(0, '/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages')
import tvm

so_path = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else 'transpose_add6_v1_standalone'

np.random.seed(42)
input_np = np.random.randn(1, 96, 32, 32).astype('float32')
weight_np = np.random.randn(96, 48, 3, 3).astype('float32')
bias_np = np.random.randn(1, 48, 1, 1).astype('float32')
out_np = np.zeros((1, 48, 64, 64), dtype='float32')

dev = tvm.cpu(0)
lib = tvm.runtime.load_module(so_path)
func = lib['fused_conv2d_transpose_add6']

runtime = getattr(tvm, 'runtime', None)
runtime_tensor = getattr(runtime, 'tensor', None) if runtime is not None else None
if runtime_tensor is None and runtime is not None:
    runtime_ndarray = getattr(runtime, 'ndarray', None)
    if runtime_ndarray is not None:
        runtime_tensor = lambda arr, dev: runtime_ndarray.array(arr, dev)
if runtime_tensor is None:
    raise AttributeError('module tvm.runtime has neither tensor nor ndarray.array')

a = runtime_tensor(input_np, dev)
b = runtime_tensor(weight_np, dev)
c = runtime_tensor(bias_np, dev)
d = runtime_tensor(out_np, dev)

for _ in range(5):
    func(a, b, c, d)

samples = []
for _ in range(30):
    t0 = time.perf_counter()
    func(a, b, c, d)
    t1 = time.perf_counter()
    samples.append((t1 - t0) * 1e6)

res = {
    'label': label,
    'so_path': so_path,
    'median_us': float(np.median(samples)),
    'mean_us': float(np.mean(samples)),
    'min_us': float(np.min(samples)),
    'max_us': float(np.max(samples)),
    'std_us': float(np.std(samples)),
    'samples': 30,
    'output_shape': [1, 48, 64, 64],
}
print('JSON_RESULT:' + json.dumps(res, indent=2))
