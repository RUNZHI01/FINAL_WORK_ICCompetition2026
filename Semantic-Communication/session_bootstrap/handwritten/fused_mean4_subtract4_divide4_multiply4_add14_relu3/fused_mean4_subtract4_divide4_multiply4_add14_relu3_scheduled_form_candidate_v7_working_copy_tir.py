# Editable scheduled-form candidate v7 working copy for fused_mean4_subtract4_divide4_multiply4_add14_relu3.
#
# Derived from the checked-in scheduled-form v5 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4/v5/v6 candidates intact; iterate here for a
#   new operator-specific follow-up beyond the current handwritten final
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the v5 affine epilogue exactly as-is
# - keep the same two-phase structure as v5 for clean attribution
# - change only the reduction side into a 4-lane local partial-sum form
# - split the width reduction as `64 x 4` and mark the inner 4-lane loop as
#   vectorized so lowering can break the long scalar accumulation chain
# - the intent is to target the remaining scalar reduction dependency that is
#   still visible in the current AArch64 codegen, while not reopening the
#   already-accepted epilogue design
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
        partial_sum = T.alloc_buffer((T.int64(4),), "float32", scope="local")
        mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        scale_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        shift_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")

        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            for v_init in T.vectorized(T.int64(4)):
                with T.sblock("partial_init"):
                    v_lane = T.axis.spatial(T.int64(4), v_init)
                    T.writes(partial_sum[v_lane])
                    partial_sum[v_lane] = T.float32(0.0)
            for k2 in T.serial(T.int64(256)):
                for k3_outer in T.serial(T.int64(64)):
                    for k3_inner in T.vectorized(T.int64(4)):
                        with T.sblock("vec_reduce"):
                            v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap(
                                "SSSS", [ax0, ax1, ax2, ax3]
                            )
                            v_k2 = T.axis.spatial(T.int64(256), k2)
                            v_k3_outer = T.axis.spatial(T.int64(64), k3_outer)
                            v_lane = T.axis.spatial(T.int64(4), k3_inner)
                            T.reads(
                                partial_sum[v_lane],
                                lv335[
                                    v_ax0,
                                    v_ax1,
                                    v_k2,
                                    v_k3_outer * T.int64(4) + v_lane,
                                ],
                            )
                            T.writes(partial_sum[v_lane])
                            partial_sum[v_lane] = (
                                partial_sum[v_lane]
                                + lv335[
                                    v_ax0,
                                    v_ax1,
                                    v_k2,
                                    v_k3_outer * T.int64(4) + v_lane,
                                ]
                            )
            with T.sblock("h_reduce"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(
                    partial_sum[T.int64(0)],
                    partial_sum[T.int64(1)],
                    partial_sum[T.int64(2)],
                    partial_sum[T.int64(3)],
                )
                T.writes(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    partial_sum[T.int64(0)]
                    + partial_sum[T.int64(1)]
                    + partial_sum[T.int64(2)]
                    + partial_sum[T.int64(3)]
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
