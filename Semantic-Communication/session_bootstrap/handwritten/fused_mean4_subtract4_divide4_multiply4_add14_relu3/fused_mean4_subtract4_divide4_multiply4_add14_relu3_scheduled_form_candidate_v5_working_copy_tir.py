# Editable scheduled-form candidate v5 working copy for fused_mean4_subtract4_divide4_multiply4_add14_relu3.
#
# Derived from the checked-in scheduled-form v4 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4 candidates intact; iterate here for a
#   new operator-specific follow-up beyond the current handwritten final
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the same mean reduction domain and output signature as v4
# - keep the hot path as a single pass over the 256x256 frame
# - precompute an affine epilogue once per channel:
#   `scale = weight / std`, `shift = bias - mean * scale`
# - reduce the hot inner loop from
#   `subtract -> divide -> multiply -> add -> relu`
#   down to
#   `multiply -> add -> relu`
# - this stays operator-specific: mean/std/weight/bias are channel-invariant,
#   so the affine collapse should cut per-element scalar work and live-state
#   pressure on the Cortex-A72 path without reopening full-frame intermediates
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_mean4_subtract4_divide4_multiply4_add14_relu3(
        lv335: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32"),
        lv340: T.Buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)), "float32"),
        lv342: T.Buffer((T.int64(12), T.int64(1), T.int64(1)), "float32"),
        lv344: T.Buffer((T.int64(12), T.int64(1), T.int64(1)), "float32"),
        compute_intermediate: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32"),
    ):
        T.func_attr({"tir.noalias": True})
        # with T.sblock("root"):
        lv335_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        scale_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        shift_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)
        ):
            with T.sblock("lv335_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(lv335[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3]
                    + lv335[v_ax0, v_ax1, v_k2, v_k3]
                )

        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("mean_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(mean_local[0])
                mean_local[0] = lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
            with T.sblock("scale_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(
                    lv340[v_ax0, v_ax1, v_ax2, v_ax3],
                    lv342[v_ax1, v_ax2, v_ax3],
                )
                T.writes(scale_local[0])
                scale_local[0] = lv342[v_ax1, v_ax2, v_ax3] / lv340[v_ax0, v_ax1, v_ax2, v_ax3]
            with T.sblock("shift_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(mean_local[0], scale_local[0], lv344[v_ax1, v_ax2, v_ax3])
                T.writes(shift_local[0])
                shift_local[0] = lv344[v_ax1, v_ax2, v_ax3] - mean_local[0] * scale_local[0]
            for k2, k3 in T.grid(T.int64(256), T.int64(256)):
                with T.sblock("affine_relu_compute"):
                    v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                        "SSSSSS", [ax0, ax1, ax2, ax3, k2, k3]
                    )
                    T.reads(
                        lv335[v_ax0, v_ax1, v_k2, v_k3],
                        scale_local[0],
                        shift_local[0],
                    )
                    T.writes(compute_intermediate[v_ax0, v_ax1, v_k2, v_k3])
                    compute_intermediate[v_ax0, v_ax1, v_k2, v_k3] = T.max(
                        lv335[v_ax0, v_ax1, v_k2, v_k3] * scale_local[0] + shift_local[0],
                        T.float32(0.0),
                    )
