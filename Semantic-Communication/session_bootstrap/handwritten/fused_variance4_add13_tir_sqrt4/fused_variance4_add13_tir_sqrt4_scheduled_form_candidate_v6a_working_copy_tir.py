# Editable scheduled-form candidate v6a working copy for fused_variance4_add13_tir_sqrt4.
#
# Derived from the checked-in scheduled-form v6 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4/v5/v6 candidates intact; iterate here for
#   the next narrow handwritten variance4 simplification follow-up
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the v6 removal of the standalone full-size T_multiply stage
# - add a one-element volatile local round-trip between the squared subtract
#   expression and T_multiply_red accumulation
# - preserve the v5 subtraction fold, v4 mean divide fold, v3
#   variance-normalization divide fold, and v2 epsilon add fused into sqrt
# - preserve both reductions and the output signature
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
        lv335_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_multiply_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_multiply_local_data = T.allocate([1], "float32", "local")
        T.attr(T_multiply_local_data, "volatile_scope", 1)
        T_multiply_local = T.decl_buffer(
            (1,), "float32", data=T_multiply_local_data, scope="local"
        )
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
                    lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)],
                )
                T.writes(T_multiply_local[0])
                T_multiply_local[0] = T.Cast(
                    "float32",
                    (
                        lv335[v_ax0, v_ax1, v_k2, v_k3]
                        - lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)]
                        / T.float32(65536.0)
                    )
                    * (
                        lv335[v_ax0, v_ax1, v_k2, v_k3]
                        - lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)]
                        / T.float32(65536.0)
                    ),
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
