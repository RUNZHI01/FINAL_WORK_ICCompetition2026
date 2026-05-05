#!/usr/bin/env python3
"""Cross-compile mean1 v1 handwritten TIR: (input - mean) * weight + bias with working set reduction."""
import sys, os, json
sys.path.insert(0, '/home/tianxing/tvm-src/python')
os.environ['LD_LIBRARY_PATH'] = '/home/tianxing/tvm-src/build'
os.environ['TVM_LIBRARY_PATH'] = '/home/tianxing/tvm-src/build'

import tvm
from tvm.script import ir as I, tir as T

TARGET = tvm.target.Target({"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4})

@I.ir_module
class Mean1V1:
    @T.prim_func
    def fused_mean1_subtract1_divide1_multiply1_add4(
        input_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
        mean_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32"),
        weight_tensor: T.Buffer((T.int64(96), T.int64(1), T.int64(1)), "float32"),
        bias_tensor: T.Buffer((T.int64(96), T.int64(1), T.int64(1)), "float32"),
        output_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        # Working set reduction: stage mean/weight/bias into per-channel locals
        T_mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_weight_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_bias_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_centered_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        for ax0, ax1, k2, k3 in T.grid(T.int64(1), T.int64(96), T.int64(32), T.int64(32)):
            with T.sblock("stage_and_compute"):
                v_ax0, v_ax1, v_k2, v_k3 = T.axis.remap("SSRR", [ax0, ax1, k2, k3])
                T.reads(
                    input_tensor[v_ax0, v_ax1, v_k2, v_k3],
                    mean_tensor[v_ax0, v_ax1, 0, 0],
                    weight_tensor[v_ax1, 0, 0],
                    bias_tensor[v_ax1, 0, 0],
                )
                T.writes(output_tensor[v_ax0, v_ax1, v_k2, v_k3])
                # Stage parameters once per channel element (not per spatial)
                T_mean_local[0] = mean_tensor[v_ax0, v_ax1, 0, 0]
                T_weight_local[0] = weight_tensor[v_ax1, 0, 0]
                T_bias_local[0] = bias_tensor[v_ax1, 0, 0]
                # Fused: (input - mean) * weight + bias
                T_centered_local[0] = input_tensor[v_ax0, v_ax1, v_k2, v_k3] - T_mean_local[0]
                output_tensor[v_ax0, v_ax1, v_k2, v_k3] = T_centered_local[0] * T_weight_local[0] + T_bias_local[0]

print("Building mean1 v1 for aarch64...")
with tvm.transform.PassContext(opt_level=3):
    rt_mod = tvm.build(Mean1V1, target=TARGET)

output_path = "/tmp/mean1_v1_cross.so"
rt_mod.export_library(output_path)
print(f"Exported to {output_path}, size={os.path.getsize(output_path)} bytes")
print("BUILD_SUCCESS")
