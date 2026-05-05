#!/usr/bin/env python3
"""Benchmark variance1 v1 (Welford single-pass) on Phytium Pi."""
import sys, time, json
sys.path.insert(0, '/home/user/tvm_samegen_20260307/python')
sys.path.insert(0, '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages')
sys.path.insert(0, '/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages')
import os
os.environ['TVM_FFI_DISABLE_TORCH_C_DLPACK'] = '1'
os.environ['LD_LIBRARY_PATH'] = '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build'
os.environ['TVM_LIBRARY_PATH'] = '/home/user/tvm_samegen_safe_20260309/build'

import numpy as np
import tvm
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Mod:
    @T.prim_func
    def fused_variance1_add3_tir_sqrt1(
        lv_input: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        welford_mean = T.alloc_buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32", scope="local")
        welford_M2 = T.alloc_buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32", scope="local")
        delta_old = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        delta_new = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(T.int64(1), T.int64(96), T.int64(1), T.int64(1), T.int64(32), T.int64(32)):
            with T.sblock("welford_update"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(lv_input[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(welford_mean[v_ax0, v_ax1, v_ax2, v_ax3], welford_M2[v_ax0, v_ax1, v_ax2, v_ax3], delta_old[0], delta_new[0])
                with T.init():
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                delta_old[0] = lv_input[v_ax0, v_ax1, v_k2, v_k3] - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] + delta_old[0] / (T.Cast("float32", v_k2 * T.int64(32) + v_k3 + T.int64(1)))
                delta_new[0] = lv_input[v_ax0, v_ax1, v_k2, v_k3] - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] + delta_old[0] * delta_new[0]
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(96), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(welford_M2[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(welford_M2[v_i0, v_i1, v_i2, v_i3] / T.float32(1024.0) + T.float32(9.9999997473787516e-06))

target = tvm.target.Target({"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4})
with tvm.transform.PassContext(opt_level=3):
    rt = tvm.build(Mod, target=target)

np.random.seed(42)
input_np = np.random.randn(1, 96, 32, 32).astype(np.float32)
output_np = np.zeros((1, 96, 1, 1), dtype=np.float32)
input_mean = input_np.mean(axis=(2,3), keepdims=True)
centered = input_np - input_mean
variance = (centered ** 2).mean(axis=(2,3), keepdims=True)
expected = np.sqrt(variance + 9.9999997473787516e-06)

dev = tvm.cpu(0)
input_tvm = tvm.nd.array(input_np, dev)
output_tvm = tvm.nd.array(output_np, dev)

for _ in range(5):
    rt(input_tvm, output_tvm)

times = []
for _ in range(30):
    t0 = time.perf_counter()
    rt(input_tvm, output_tvm)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1e6)

result = output_tvm.numpy()
max_diff = float(np.max(np.abs(result - expected)))
median_us = float(np.median(times))
print(json.dumps({"operator":"fused_variance1_add3_tir_sqrt1","version":"v1_welford","correctness":{"max_abs_diff":max_diff,"passed":max_diff<1e-3},"performance_us":{"median":median_us,"mean":float(np.mean(times)),"std":float(np.std(times)),"samples":30},"baseline_median_us":5000,"delta_pct":round((median_us-5000)/5000*100,2)}))
