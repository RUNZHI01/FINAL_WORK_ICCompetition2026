# Editable scheduled-form candidate v16 working copy for fused_variance4_add13_tir_sqrt4.
#
# Derived from the checked-in scheduled-form v15 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4/v5/v6/v6a/v7/v8/v9/v10/v11/v12/v13/v14/v15
#   candidates intact; iterate here for the next narrow handwritten variance4
#   performance follow-up
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the full v15 exact-preserving storage placement intact, including the
#   local-scoped lv335_red buffer and the handle-free `.data`-volatile local
#   round-trip on T_multiply_local
# - make only the tiny T_multiply_red reduction buffer explicitly
#   `scope="local"` so the hot variance accumulation and final sqrt handoff
#   both stay on explicit local allocations
# - keep the same two reductions, the same folded arithmetic, and the same
#   output signature as v15
# - preserve the v13 unit-axis cleanup, the v6 full-size T_multiply removal,
#   the v5 subtraction fold, the v4 mean divide fold, the v3
#   variance-normalization divide fold, and the v2 epsilon add fused into sqrt
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
        # with T.sblock("root"):
        lv335_red = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        T_multiply_red = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        T_multiply_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T.attr(T_multiply_local.data, "volatile_scope", 1)
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
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)
        ):
            with T.sblock("T_multiply_local"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(
                    lv335[v_ax0, v_ax1, v_k2, v_k3],
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3],
                )
                T.writes(T_multiply_local[0])
                T_multiply_local[0] = (
                    (
                        lv335[v_ax0, v_ax1, v_k2, v_k3]
                        - lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
                    )
                    * (
                        lv335[v_ax0, v_ax1, v_k2, v_k3]
                        - lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
                    )
                )
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
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_multiply_red[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(
                    T_multiply_red[v_i0, v_i1, v_i2, v_i3] / T.float32(65536.0)
                    + T.float32(9.9999997473787516e-06)
                )
