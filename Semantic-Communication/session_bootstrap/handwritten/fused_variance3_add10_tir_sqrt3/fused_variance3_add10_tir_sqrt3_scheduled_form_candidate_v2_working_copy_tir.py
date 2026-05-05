# Welford single-pass variance3 v2 working copy.
#
# variance3: input [1, 24, 128, 128] -> output [1, 24, 1, 1]
#   - spatial reduction: 128*128 = 16384 elements per channel
#   - 24 channels
#
# Key improvement over v1 (two-pass):
#   v1 reads the full 128x128 spatial data TWICE (once for mean, once for
#   variance). On Cortex-A72 with 32 KB L1d, each channel's data (64 KB)
#   exceeds L1, so Pass 2 re-reads from L2/main memory.
#
#   v2 uses Welford's online algorithm to compute mean and variance in a
#   SINGLE pass, halving memory traffic. All intermediates are in local scope.
#
# Welford's algorithm:
#   mean_n = mean_{n-1} + (x_n - mean_{n-1}) / n
#   M2_n   = M2_{n-1}   + (x_n - mean_{n-1}) * (x_n - mean_n)
#   variance = M2_N / N
#
# To avoid per-element division by n, we accumulate count as a float and
# use multiplication by reciprocal where possible.
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

        welford_mean = T.alloc_buffer(
            (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        welford_M2 = T.alloc_buffer(
            (T.int64(1), T.int64(24), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        delta_old = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        delta_new = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        # Single-pass Welford reduction over 128x128 spatial dims
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(24), T.int64(1), T.int64(1), T.int64(128), T.int64(128)
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

                # count = k2 * 128 + k3 + 1 (1-based)
                # delta_old = x - mean_old
                delta_old[0] = (
                    lv_input[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                # mean_new = mean_old + delta_old / count
                welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0]
                    / (T.Cast("float32", v_k2 * T.int64(128) + v_k3 + T.int64(1)))
                )
                # delta_new = x - mean_new
                delta_new[0] = (
                    lv_input[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                # M2_new = M2_old + delta_old * delta_new
                welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0] * delta_new[0]
                )

        # Final: output = sqrt(M2 / N + eps)
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(24), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(welford_M2[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(
                    welford_M2[v_i0, v_i1, v_i2, v_i3] / T.float32(16384.0)
                    + T.float32(9.9999997473787516e-06)
                )
