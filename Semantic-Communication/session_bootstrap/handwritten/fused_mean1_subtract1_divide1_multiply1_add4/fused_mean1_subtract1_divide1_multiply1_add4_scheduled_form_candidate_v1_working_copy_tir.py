# mean1 v1: fused (input - mean) * weight + bias with working set reduction.
#
# Shape: input [1, 96, 32, 32], mean [1, 96, 1, 1], weight [96, 1, 1], bias [96, 1, 1]
#        -> output [1, 96, 32, 32]
#
# This is an instance-norm-like elementwise operation. The key optimization
# is fusing all 4 operations (subtract, divide-by-std, multiply, add) into
# a single loop, and staging the per-channel parameters (mean, weight, bias)
# into local buffers to avoid redundant global memory reads.
#
# Note: the "divide" in the original op name refers to division by the
# standard deviation (from a separate variance op), NOT a reduction.
# mean_tensor here is actually the pre-computed std (variance output).
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_mean1_subtract1_divide1_multiply1_add4(
        input_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
        mean_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32"),
        weight_tensor: T.Buffer((T.int64(96), T.int64(1), T.int64(1)), "float32"),
        bias_tensor: T.Buffer((T.int64(96), T.int64(1), T.int64(1)), "float32"),
        output_tensor: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        T_mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_weight_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_bias_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        for ax0, ax1, k2, k3 in T.grid(T.int64(1), T.int64(96), T.int64(32), T.int64(32)):
            with T.sblock("fused_compute"):
                v_ax0, v_ax1, v_k2, v_k3 = T.axis.remap("SSSS", [ax0, ax1, k2, k3])
                T.reads(
                    input_tensor[v_ax0, v_ax1, v_k2, v_k3],
                    mean_tensor[v_ax0, v_ax1, T.int64(0), T.int64(0)],
                    weight_tensor[v_ax1, T.int64(0), T.int64(0)],
                    bias_tensor[v_ax1, T.int64(0), T.int64(0)],
                )
                T.writes(output_tensor[v_ax0, v_ax1, v_k2, v_k3])
                T_mean_local[0] = mean_tensor[v_ax0, v_ax1, T.int64(0), T.int64(0)]
                T_weight_local[0] = weight_tensor[v_ax1, T.int64(0), T.int64(0)]
                T_bias_local[0] = bias_tensor[v_ax1, T.int64(0), T.int64(0)]
                output_tensor[v_ax0, v_ax1, v_k2, v_k3] = (
                    (input_tensor[v_ax0, v_ax1, v_k2, v_k3] - T_mean_local[0])
                    * T_weight_local[0]
                    + T_bias_local[0]
                )
