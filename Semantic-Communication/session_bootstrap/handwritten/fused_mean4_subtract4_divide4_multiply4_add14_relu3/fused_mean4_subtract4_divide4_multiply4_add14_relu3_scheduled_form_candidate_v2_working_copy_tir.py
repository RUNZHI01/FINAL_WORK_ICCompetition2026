# Editable scheduled-form candidate v2 working copy for fused_mean4_subtract4_divide4_multiply4_add14_relu3.
#
# Derived from the checked-in scheduled-form v1 working copy.
#
# Contract:
# - local-only diagnostic working copy
# - keep the checked-in v1 seed-clone baseline intact; iterate here for the
#   first real mean4 handwritten candidate
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the reduction shape and arithmetic intent intact
# - stage the per-channel normalized mean once into a tiny local buffer
# - replace the four full-frame epilogue intermediates with one-element local
#   handoff buffers inside the final elementwise loop
# - preserve the output signature and ReLU semantics of the scheduled seed
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
        lv335_mean_local = T.alloc_buffer(
            (T.int64(1), T.int64(12), T.int64(1), T.int64(1)),
            "float32",
            scope="local",
        )
        T_subtract_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_divide_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_multiply_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
        T_add_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")
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
            with T.sblock("lv335_mean_local"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(lv335_mean_local[v_ax0, v_ax1, v_ax2, v_ax3])
                lv335_mean_local[v_ax0, v_ax1, v_ax2, v_ax3] = (
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
                )
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(12), T.int64(256), T.int64(256)):
            with T.sblock("T_subtract_local"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(
                    lv335[v_i0, v_i1, v_i2, v_i3],
                    lv335_mean_local[v_i0, v_i1, T.int64(0), T.int64(0)],
                )
                T.writes(T_subtract_local[0])
                T_subtract_local[0] = (
                    lv335[v_i0, v_i1, v_i2, v_i3]
                    - lv335_mean_local[v_i0, v_i1, T.int64(0), T.int64(0)]
                )
            with T.sblock("T_divide1_local"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_subtract_local[0], lv340[v_i0, v_i1, T.int64(0), T.int64(0)])
                T.writes(T_divide_local[0])
                T_divide_local[0] = (
                    T_subtract_local[0] / lv340[v_i0, v_i1, T.int64(0), T.int64(0)]
                )
            with T.sblock("T_multiply_local"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_divide_local[0], lv342[v_i1, T.int64(0), T.int64(0)])
                T.writes(T_multiply_local[0])
                T_multiply_local[0] = (
                    T_divide_local[0] * lv342[v_i1, T.int64(0), T.int64(0)]
                )
            with T.sblock("T_add_local"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_multiply_local[0], lv344[v_i1, T.int64(0), T.int64(0)])
                T.writes(T_add_local[0])
                T_add_local[0] = (
                    T_multiply_local[0] + lv344[v_i1, T.int64(0), T.int64(0)]
                )
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_add_local[0])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.max(
                    T_add_local[0], T.float32(0.0)
                )
