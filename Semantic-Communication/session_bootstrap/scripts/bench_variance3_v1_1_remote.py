#!/usr/bin/env python3
"""Benchmark variance3 v1.1 (scope-fixed two-pass) on Phytium Pi."""
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
    def fused_variance3_add10_tir_sqrt3(
        lv_input: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        lv_input_red = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32", scope="local")
        lv_input_mean_local = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32", scope="local")
        T_subtract_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_multiply_red = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32", scope="local")
        T_multiply_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T.attr(T_multiply_local.data, "volatile_scope", 1)
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1), T.int64(128), T.int64(128)):
            with T.sblock("lv_input_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(lv_input[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] = lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] + lv_input[v_ax0, v_ax1, v_k2, v_k3]
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1)):
            with T.sblock("lv335_mean_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3])
                lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3] = lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(16384.0)
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1), T.int64(128), T.int64(128)):
            with T.sblock("T_subtract_local"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(lv_input[v_ax0, v_ax1, v_k2, v_k3], lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_subtract_local[0])
                T_subtract_local[0] = lv_input[v_ax0, v_ax1, v_k2, v_k3] - lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3]
            with T.sblock("T_multiply_local"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(T_subtract_local[0])
                T.writes(T_multiply_local[0])
                T_multiply_local[0] = T_subtract_local[0] * T_subtract_local[0]
            with T.sblock("T_multiply_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(T_multiply_local[0])
                T.writes(T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] + T_multiply_local[0]
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_multiply_red[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(T_multiply_red[v_i0, v_i1, v_i2, v_i3] / T.float32(16384.0) + T.float32(9.9999997473787516e-06))

target = tvm.target.Target({"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4})
with tvm.transform.PassContext(opt_level=3):
    rt = tvm.build(Mod, target=target)

np.random.seed(42)
input_np = np.random.randn(1, 24, 128, 128).astype(np.float32)
output_np = np.zeros((1, 24, 1, 1), dtype=np.float32)
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
print(json.dumps({"operator":"fused_variance3_add10_tir_sqrt3","version":"v1.1_scope_fixed","correctness":{"max_abs_diff":max_diff,"passed":max_diff<1e-3},"performance_us":{"median":median_us,"mean":float(np.mean(times)),"std":float(np.std(times)),"samples":30},"baseline_median_us":3562,"delta_pct":round((median_us-3562)/3562*100,2)}))
