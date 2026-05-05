# Editable scheduled-form candidate v1 working copy for fused_variance3_add10_tir_sqrt3.
#
# Strategy: apply the working set reduction + normalized-mean handoff principle
# that succeeded for variance4 v18, adapted for variance3's smaller shape.
#
# variance3: input [1, 24, 128, 128] -> output [1, 24, 1, 1]
#   - spatial reduction: 128*128 = 16384 elements per channel
#   - 24 channels (vs 12 for variance4)
#   - total working set per channel: 128*128*4 = 64 KB raw input
#
# Key optimization from variance4 v18:
#   1. Stage mean into a local buffer (one value per channel)
#   2. Fused subtract + square + reduce in a single pass with local intermediates
#   3. sqrt( var/N + eps ) at the end
#
# Differences from variance4:
#   - shape [1,24,128,128] vs [1,12,256,256]
#   - division constant: 16384.0 vs 65536.0
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_variance3_add10_tir_sqrt3(
        lv_input: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        # Stage 1: sum reduction to compute mean
        lv_input_red = T.alloc_buffer(
            (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        # Staged mean: one value per channel, kept in local
        lv_input_mean_local = T.alloc_buffer(
            (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        # One-element local for centered value reuse
        T_subtract_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        # Accumulator for sum-of-squares
        T_multiply_red = T.alloc_buffer(
            (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        # One-element local for squared value
        T_multiply_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T.attr(T_multiply_local.data, "volatile_scope", 1)

        # Pass 1: sum reduction
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(24), T.int64(1), T.int64(1), T.int64(128), T.int64(128)
        ):
            with T.sblock("lv_input_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(lv_input[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3]
                    + lv_input[v_ax0, v_ax1, v_k2, v_k3]
                )

        # Compute mean from sum
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1)):
            with T.sblock("lv_input_mean_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3])
                lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    lv_input_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(16384.0)
                )

        # Pass 2: fused subtract + square + reduce
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(24), T.int64(1), T.int64(1), T.int64(128), T.int64(128)
        ):
            with T.sblock("T_subtract_local"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(
                    lv_input[v_ax0, v_ax1, v_k2, v_k3],
                    lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3],
                )
                T.writes(T_subtract_local[0])
                T_subtract_local[0] = (
                    lv_input[v_ax0, v_ax1, v_k2, v_k3]
                    - lv_input_mean_local[v_ax0, v_ax1, v_ax2, v_ax3]
                )
            with T.sblock("T_multiply_local"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(T_subtract_local[0])
                T.writes(T_multiply_local[0])
                T_multiply_local[0] = T_subtract_local[0] * T_subtract_local[0]
            with T.sblock("T_multiply_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(T_multiply_local[0])
                T.writes(T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] + T_multiply_local[0]
                )

        # Final: sqrt(var/N + eps)
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_multiply_red[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(
                    T_multiply_red[v_i0, v_i1, v_i2, v_i3] / T.float32(16384.0)
                    + T.float32(9.9999997473787516e-06)
                )
