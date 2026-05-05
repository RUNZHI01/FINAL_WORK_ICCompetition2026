# Checked-in editable seed for fused_conv2d_transpose1_add9.
#
# Source inputs:
# - captured seed json: ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed.json
# - captured pre-compile seed snapshot: ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed_tir.py
# - extracted operator task log: ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_seed_capture/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_0_fused_conv2d_transpose1_add9.log
#
# Notes:
# - the captured pre-compile seed snapshot only recorded the full Relax callsite
# - this file preserves the actual operator TIR printed by the local MetaSchedule task log
# - edit here when shaping the first handwritten candidate
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def main(lv318: T.Buffer((T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"), param_0: T.Buffer((T.int64(48), T.int64(24), T.int64(3), T.int64(3)), "float32"), lv320: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32")):
        T.func_attr({"tir.noalias": True})
        # with T.sblock("root"):
        data_dilate = T.alloc_buffer((T.int64(1), T.int64(48), T.int64(127), T.int64(127)))
        data_pad = T.alloc_buffer((T.int64(1), T.int64(48), T.int64(130), T.int64(130)))
        kernel_transform = T.alloc_buffer((T.int64(24), T.int64(48), T.int64(3), T.int64(3)))
        compute_intermediate = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)))
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(48), T.int64(127), T.int64(127)):
            with T.sblock("data_dilate"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(v_i2 % T.int64(2) == T.int64(0) and v_i3 % T.int64(2) == T.int64(0), lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)], T.float32(0.0))
        for i0, i1, i2, i3 in T.grid(T.int64(1), T.int64(48), T.int64(130), T.int64(130)):
            with T.sblock("data_pad"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)])
                T.writes(data_pad[v_i0, v_i1, v_i2, v_i3])
                data_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(T.int64(1) <= v_i2 and v_i2 < T.int64(128) and T.int64(1) <= v_i3 and v_i3 < T.int64(128), data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)], T.float32(0.0))
        for o, i, h, w in T.grid(T.int64(24), T.int64(48), T.int64(3), T.int64(3)):
            with T.sblock("kernel_transform"):
                v_o, v_i, v_h, v_w = T.axis.remap("SSSS", [o, i, h, w])
                T.reads(param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w])
                T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                kernel_transform[v_o, v_i, v_h, v_w] = param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w]
        for b, c, h, w, dc, dh, dw in T.grid(T.int64(1), T.int64(24), T.int64(128), T.int64(128), T.int64(48), T.int64(3), T.int64(3)):
            with T.sblock("compute"):
                v_b, v_c, v_h, v_w, v_dc, v_dh, v_dw = T.axis.remap("SSSSRRR", [b, c, h, w, dc, dh, dw])
                T.reads(data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw], kernel_transform[v_c, v_dc, v_dh, v_dw])
                T.writes(compute_intermediate[v_b, v_c, v_h, v_w])
                with T.init():
                    compute_intermediate[v_b, v_c, v_h, v_w] = T.float32(0.0)
                compute_intermediate[v_b, v_c, v_h, v_w] = compute_intermediate[v_b, v_c, v_h, v_w] + data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw] * kernel_transform[v_c, v_dc, v_dh, v_dw]
        for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(24), T.int64(128), T.int64(128)):
            with T.sblock("T_add"):
                v_ax0, v_ax1, v_ax2, v_ax3 = T.axis.remap("SSSS", [ax0, ax1, ax2, ax3])
                T.reads(compute_intermediate[v_ax0, v_ax1, v_ax2, v_ax3], lv320[v_ax0, v_ax1, T.int64(0), T.int64(0)])
                T.writes(T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = compute_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] + lv320[v_ax0, v_ax1, T.int64(0), T.int64(0)]
