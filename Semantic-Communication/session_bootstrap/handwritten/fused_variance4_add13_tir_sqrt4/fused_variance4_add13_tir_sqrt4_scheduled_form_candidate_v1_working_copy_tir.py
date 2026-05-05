# Editable scheduled-form candidate v1 working copy for fused_variance4_add13_tir_sqrt4.
#
# Derived from:
# - checked-in scheduled reference seed: ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py
# - checked-in scheduled reference manifest: ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/post_db_scheduled_reference_seed_manifest.json
#
# Contract:
# - local-only diagnostic working copy
# - start here for variance4 scheduled-form handwritten edits
# - keep the scheduled reference seed frozen so this file can be refreshed
# - do not treat this file as hook-facing or as performance evidence
#
# Current checked-in state:
# - no operator-side handwritten edit has been applied yet
# - this file is an editable scheduled-form clone of the checked-in reference seed
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def fused_variance4_add13_tir_sqrt4(lv335: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32"), compute_intermediate: T.Buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)), "float32")):
        T.func_attr({"tir.noalias": True})
        # with T.sblock("root"):
        lv335_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_divide = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_subtract = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)))
        T_multiply = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)))
        T_multiply_red = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_divide_intermediate = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        T_add_intermediate = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)))
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)):
            with T.sblock("lv335_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(lv335[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] = lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] + lv335[v_ax0, v_ax1, v_k2, v_k3]
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("T_divide"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv335_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_divide[v_ax0, v_ax1, v_ax2, v_ax3])
                T_divide[v_ax0, v_ax1, v_ax2, v_ax3] = lv335_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(256), T.int64(256)):
            with T.sblock("T_subtract"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(lv335[v_ax0, v_ax1, v_ax2, v_ax3], T_divide[v_ax0, v_ax1, T.int64(0), T.int64(0)])
                T.writes(T_subtract[v_ax0, v_ax1, v_ax2, v_ax3])
                T_subtract[v_ax0, v_ax1, v_ax2, v_ax3] = lv335[v_ax0, v_ax1, v_ax2, v_ax3] - T_divide[v_ax0, v_ax1, T.int64(0), T.int64(0)]
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(256), T.int64(256)):
            with T.sblock("T_multiply"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(T_subtract[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_multiply[v_ax0, v_ax1, v_ax2, v_ax3])
                T_multiply[v_ax0, v_ax1, v_ax2, v_ax3] = T_subtract[v_ax0, v_ax1, v_ax2, v_ax3] * T_subtract[v_ax0, v_ax1, v_ax2, v_ax3]
        for ax0, ax1, ax2, ax3, k2, k3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1), T.int64(256), T.int64(256)):
            with T.sblock("T_multiply_red"):
                v_ax0, v_ax1, v_ax2, v_ax3, v_k2, v_k3 = T.axis.remap("SSSSRR", [ax0, ax1, ax2, ax3, k2, k3])
                T.reads(T_multiply[v_ax0, v_ax1, v_k2, v_k3])
                T.writes(T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3])
                with T.init():
                    T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T.float32(0.0)
                T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] = T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] + T_multiply[v_ax0, v_ax1, v_k2, v_k3]
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("T_divide_1"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = T_multiply_red[v_ax0, v_ax1, v_ax2, v_ax3] / T.float32(65536.0)
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("T_add"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                T.writes(T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] + T.float32(9.9999997473787516e-06)
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(12), T.int64(1), T.int64(1)):
            with T.sblock("compute"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(T_add_intermediate[v_i0, v_i1, v_i2, v_i3])
                T.writes(compute_intermediate[v_i0, v_i1, v_i2, v_i3])
                compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(T_add_intermediate[v_i0, v_i1, v_i2, v_i3])
