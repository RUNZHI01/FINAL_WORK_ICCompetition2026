# Welford single-pass variance1 v1 working copy.
#
# variance1: input [1, 96, 32, 32] -> output [1, 96, 1, 1]
#   - spatial reduction: 32*32 = 1024 elements per channel
#   - 96 channels
#   - total input: 96 * 32 * 32 * 4B = 384 KB (far exceeds 32 KB L1d)
#   - per-channel input: 32 * 32 * 4B = 4 KB (fits in L1d!)
#
# This operator is structurally identical to variance3/variance4 but with
# a much smaller spatial dimension (32x32 vs 128x128/256x256).
# Per-channel data (4 KB) actually fits in Cortex-A72 L1d (32 KB).
# However, with 96 channels the total data is 384 KB, so cross-channel
# cache pressure still matters.
#
# Using Welford single-pass to avoid reading spatial data twice.
# Division constant: 1024.0 (32*32)
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_variance1_add3_tir_sqrt1(
        lv_input: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(96), T.int64(1), T.int64(1)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})

        welford_mean = T.alloc_buffer(
            (T.int64(1), T.int64(96), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        welford_M2 = T.alloc_buffer(
            (T.int64(1), T.int64(96), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        delta_old = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        delta_new = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        # Single-pass Welford reduction over 32x32 spatial dims
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(96), T.int64(1), T.int64(1), T.int64(32), T.int64(32)
        ):
            with T.sblock("welford_update"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(lv_input[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3],
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3],
                    delta_old[0],
                    delta_new[0],
                )
                with T.init():
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)

                delta_old[0] = (
                    lv_input[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0]
                    / (T.Cast("float32", v_k2 * T.int64(32) + v_k3 + T.int64(1)))
                )
                delta_new[0] = (
                    lv_input[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0] * delta_new[0]
                )

        # Final: output = sqrt(M2 / N + eps)
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(96), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(welford_M2[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(
                    welford_M2[v_i0, v_i1, v_i2, v_i3] / T.float32(1024.0)
                    + T.float32(9.9999997473787516e-06)
                )
