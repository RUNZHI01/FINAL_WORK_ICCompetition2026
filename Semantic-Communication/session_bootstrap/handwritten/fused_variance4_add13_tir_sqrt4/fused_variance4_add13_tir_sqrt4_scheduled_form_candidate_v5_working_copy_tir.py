# Editable scheduled-form candidate v5 working copy for fused_variance4_add13_tir_sqrt4.
#
# Derived from the checked-in scheduled-form v4 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1/v2/v3/v4 candidates intact; iterate here for the next
#   narrow handwritten variance4 simplification
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - remove the standalone full-size T_subtract stage
# - fold the subtraction directly into the T_multiply consumer
# - keep the v4 mean divide folded into the subtract expression
# - keep the v3 variance-normalization divide and v2 epsilon-add-into-sqrt
#   simplifications intact
# - preserve both reductions, the T_multiply materialization, and the output
#   signature
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
        T_multiply = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)))
        T_multiply_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
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
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(256), T.int64(256)):
            with T.sblock("T_multiply"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(
                    lv335[v_ax0, v_ax1, v_ax2, v_ax3],
                    lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)],
                )
                T.writes(T_multiply[v_ax0, v_ax1, v_ax2, v_ax3])
                T_multiply[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    (
                        lv335[v_ax0, v_ax1, v_ax2, v_ax3]
                        - lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)]
                        / T.float32(65536.0)
                    )
                    * (
                        lv335[v_ax0, v_ax1, v_ax2, v_ax3]
                        - lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)]
                        / T.float32(65536.0)
                    )
                )
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(
            T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)
        ):
            with T.sblock("T_multiply_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap(
                    "SSSSRR", [ax0, ax1, ax2, ax3, k2, k3]
                )
                T.reads(T_multiply[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3]
                    + T_multiply[v_ax0, v_ax1, v_k2, v_k3]
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
