# Editable scheduled-form candidate v20 working copy for fused_variance4_add13_tir_sqrt4.
#
# Derived from the checked-in scheduled-form v19 working copy and the
# Welford single-pass structure already proven in variance3 v2.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4/v5/v6/v6a/v7/v8/v9/v10/v11/v12/v13/v14/v15/v16/v17/v18/v19
#   candidates intact; iterate here for a single-pass variance4 follow-up
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - replace the two-pass mean + centered-square reduction with Welford's
#   online single-pass variance reduction
# - variance4 reduces [1, 12, 256, 256], so each channel holds 65536 float32
#   elements = 256 KB/channel; that is far larger than the Cortex-A72 32 KB
#   L1d on Phytium Pi
# - a two-pass kernel re-reads each 256 KB channel after it has fallen out of
#   L1, while Welford keeps the same arithmetic intent in one streaming pass
# - keep the variance4 naming convention: input buffer `lv335`, output buffer
#   `compute_intermediate`
#
# Welford update:
#   count     = k2 * 256 + k3 + 1
#   delta_old = x - mean_old
#   mean_new  = mean_old + delta_old / count
#   delta_new = x - mean_new
#   M2_new    = M2_old + delta_old * delta_new
#   variance  = M2 / 65536
#
# All intermediates stay in `scope="local"` so the single-pass update avoids
# materializing extra full-frame buffers while halving hot input traffic
# relative to the old two-pass formulation.
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_variance4_add13_tir_sqrt4(
        lv335: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})

        welford_mean = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        welford_M2 = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        delta_old = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        delta_new = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        # Single-pass Welford reduction over the 256x256 spatial domain.
        # This is preferable on Phytium Pi because each channel is 256 KB, so
        # the old mean pass cannot stay resident in the 32 KB L1d for the
        # variance pass that follows.
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)
        ):
            with T.sblock("welford_update"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(lv335[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3],
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3],
                    delta_old[0],
                    delta_new[0],
                )
                with T.init():
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)

                # count = k2 * 256 + k3 + 1, kept 1-based for the online mean.
                delta_old[0] = (
                    lv335[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                welford_mean[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0]
                    / T.Cast(
                        "float32",
                        v_k2 * T.int64(256) + v_k3 + T.int64(1),
                    )
                )
                delta_new[0] = (
                    lv335[v_ax0, v_ax1, v_k2, v_k3]
                    - welford_mean[v_ax0, v_ax1, v_ax2, v_ax3]
                )
                welford_M2[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    welford_M2[v_ax0, v_ax1, v_ax2, v_ax3]
                    + delta_old[0] * delta_new[0]
                )

        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(welford_M2[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(
                    welford_M2[v_i0, v_i1, v_i2, v_i3] / T.float32(65536.0)
                    + T.float32(9.9999997473787516e-06)
                )
