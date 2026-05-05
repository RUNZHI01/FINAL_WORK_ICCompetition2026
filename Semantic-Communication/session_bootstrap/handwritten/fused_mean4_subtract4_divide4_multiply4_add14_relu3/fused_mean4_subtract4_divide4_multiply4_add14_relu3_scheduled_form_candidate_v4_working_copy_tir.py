# Editable scheduled-form candidate v4 working copy for fused_mean4_subtract4_divide4_multiply4_add14_relu3.
#
# Derived from the checked-in scheduled-form v3 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3 candidates intact; iterate here for a
#   tighter fused mean4 epilogue follow-up
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the same mean reduction shape and arithmetic as v3:
#   `lv335_red -> T_divide_intermediate`
# - fuse subtract + divide + multiply + add + relu into one pass over the
#   256x256 frame
# - stage per-channel mean/std/weight/bias into local buffers loaded once per
#   channel and reused across the full inner loop
# - v3 materializes five separate full-frame elementwise stages, which drives
#   roughly 31 MB of traffic for a 3 MB tensor. This version keeps the hot
#   path close to one input read plus one output write, around 6 MB, which is
#   far more suitable for the Cortex-A72 32 KB L1d.
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
        T_divide_intermediate = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        std_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        weight_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        bias_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")

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
            with T.sblock("T_divide"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
                )
            with T.sblock("param_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(
                    T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3],
                    lv340[v_ax0, v_ax1, v_ax2, v_ax3],
                    lv342[v_ax1, v_ax2, v_ax3],
                    lv344[v_ax1, v_ax2, v_ax3],
                )
                T.writes(mean_local[0], std_local[0], weight_local[0], bias_local[0])
                mean_local[0] = T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3]
                std_local[0] = lv340[v_ax0, v_ax1, v_ax2, v_ax3]
                weight_local[0] = lv342[v_ax1, v_ax2, v_ax3]
                bias_local[0] = lv344[v_ax1, v_ax2, v_ax3]
            for k2, k3 in T.grid(T.int64(256), T.int64(256)):
                with T.sblock("fused_compute"):
                    v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                        "SSSSSS", [ax0, ax1, ax2, ax3, k2, k3]
                    )
                    T.reads(
                        lv335[v_ax0, v_ax1, v_k2, v_k3],
                        mean_local[0],
                        std_local[0],
                        weight_local[0],
                        bias_local[0],
                    )
                    T.writes(compute_intermediate[v_ax0, v_ax1, v_k2, v_k3])
                    compute_intermediate[v_ax0, v_ax1, v_k2, v_k3] = T.max(
                        (
                            (lv335[v_ax0, v_ax1, v_k2, v_k3] - mean_local[0])
                            / std_local[0]
                        )
                        * weight_local[0]
                        + bias_local[0],
                        T.float32(0.0),
                    )
