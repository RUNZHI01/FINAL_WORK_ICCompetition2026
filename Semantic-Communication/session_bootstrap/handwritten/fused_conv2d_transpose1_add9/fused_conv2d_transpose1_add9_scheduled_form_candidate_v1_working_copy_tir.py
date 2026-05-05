# Editable scheduled-form candidate v1 working copy for fused_conv2d_transpose1_add9.
#
# Derived from:
# - checked-in scheduled reference seed: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py
# - checked-in scheduled reference manifest: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json
# - distinct from the older raw pre-compile editable seed: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_editable_seed_tir.py
# - distinct from the checked-in candidate v0: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_candidate_v0_tir.py
#
# Contract:
# - local-only diagnostic working copy
# - edit here for the first scheduled-form v1 handwritten pass
# - keep the scheduled reference seed frozen so this file can be refreshed
# - do not treat this file as hook-facing or as performance evidence
#
# First real scheduled-form v1 edit:
# - fold the final bias add into the scheduled compute init/update path
# - remove the full-size compute_intermediate buffer and trailing T_add pass
#
# P2 local tile-tuning edit on top of the accepted v1 baseline:
# - keep the scheduled-form v1 bias fusion intact
# - retune the output-channel tiling from c_1 x c_3 = 6 x 4 to 3 x 8
# - reuse each materialized data_dilate/data_pad tile across 8 output channels instead of 4
#
# P4 local micro-tuning edit on top of the accepted P2 state:
# - keep the P2 output-channel tiling intact
# - raise pragma_auto_unroll_max_step from 32 to 64 on the outer scheduled region
# - keep the existing 4-lane vectorized inner stores/updates unchanged
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose1_add9(lv318: T.Buffer((T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"), param_0: T.Buffer((T.int64(48), T.int64(24), T.int64(3), T.int64(3)), "float32"), lv320: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32")):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        data_dilate = T.alloc_buffer((T.int64(1), T.int64(48), T.int64(127), T.int64(127)))
        data_pad = T.alloc_buffer((T.int64(1), T.int64(48), T.int64(130), T.int64(130)))
        kernel_transform = T.alloc_buffer((T.int64(24), T.int64(48), T.int64(3), T.int64(3)))
        for o_i_fused in T.parallel(T.int64(1152)):
            for h_w_fused in T.vectorized(T.int64(9)):
                with T.sblock("kernel_transform"):
                    v_o = T.axis.spatial(T.int64(24), o_i_fused // T.int64(48))
                    v_i = T.axis.spatial(T.int64(48), o_i_fused % T.int64(48))
                    v_h = T.axis.spatial(T.int64(3), h_w_fused // T.int64(3))
                    v_w = T.axis.spatial(T.int64(3), h_w_fused % T.int64(3))
                    T.reads(param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w])
                    T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                    kernel_transform[v_o, v_i, v_h, v_w] = param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w]
        for b_0_c_0_h_0_w_0_fused_fused_fused in T.parallel(T.int64(32), annotations={"pragma_auto_unroll_max_step": 64, "pragma_unroll_explicit": 1}):
            for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(48), T.int64(66)):
                    for ax0_1, ax1_1 in T.grid(T.int64(1), T.int64(1)):
                        for ax2_ax3_fused in T.vectorized(T.int64(10)):
                            with T.sblock("data_dilate"):
                                v_i0 = T.axis.spatial(T.int64(1), ax0_1)
                                v_i1 = T.axis.spatial(T.int64(48), ax1 + ax1_1)
                                v_i2 = T.axis.spatial(T.int64(127), b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64) + ax2 + T.int64(-1))
                                v_i3 = T.axis.spatial(T.int64(127), b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + ax2_ax3_fused + T.int64(-1))
                                T.where(T.int64(1) <= b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(32) // T.int64(16) * T.int64(64) + ax2 and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(32) // T.int64(16) * T.int64(64) + ax2 < T.int64(128) and T.int64(1) <= b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + ax2_ax3_fused % T.int64(10) and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + ax2_ax3_fused % T.int64(10) < T.int64(128))
                                T.reads(lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                                T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                                data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(v_i2 % T.int64(2) == T.int64(0) and v_i3 % T.int64(2) == T.int64(0), lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)], T.float32(0.0))
                    for ax3_fused in T.vectorized(T.int64(10)):
                        with T.sblock("data_pad"):
                            v_i0, v_i1 = T.axis.remap("SS", [ax0, ax1])
                            v_i2 = T.axis.spatial(T.int64(130), b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64) + ax2)
                            v_i3 = T.axis.spatial(T.int64(130), b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + ax3_fused)
                            T.reads(data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)])
                            T.writes(data_pad[v_i0, v_i1, v_i2, v_i3])
                            data_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(T.int64(1) <= v_i2 and v_i2 < T.int64(128) and T.int64(1) <= v_i3 and v_i3 < T.int64(128), data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)], T.float32(0.0))
                for h_1, w_1 in T.grid(T.int64(2), T.int64(2)):
                    for b_2_init, c_2_init, h_2_init, w_2_init, b_3_init, c_3_init, h_3_init in T.grid(T.int64(1), T.int64(1), T.int64(16), T.int64(1), T.int64(1), T.int64(8), T.int64(2)):
                        for w_3_fused_init in T.vectorized(T.int64(4)):
                            with T.sblock("compute_init"):
                                v_b = T.axis.spatial(T.int64(1), b_1 + b_2_init + b_3_init)
                                v_c = T.axis.spatial(T.int64(24), c_1 * T.int64(8) + c_2_init * T.int64(8) + c_3_init)
                                v_h = T.axis.spatial(T.int64(128), b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64) + h_1 * T.int64(32) + h_2_init * T.int64(2) + h_3_init)
                                v_w = T.axis.spatial(T.int64(128), b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + w_1 * T.int64(4) + w_2_init * T.int64(4) + w_3_fused_init)
                                T.reads(lv320[v_b, v_c, T.int64(0), T.int64(0)])
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = lv320[v_b, v_c, T.int64(0), T.int64(0)]
                    for dc_0, dh_0, dw_0, b_2, c_2, h_2, w_2, dc_1, dh_1, dw_1, b_3, c_3, h_3 in T.grid(T.int64(12), T.int64(1), T.int64(1), T.int64(1), T.int64(1), T.int64(16), T.int64(1), T.int64(4), T.int64(3), T.int64(3), T.int64(1), T.int64(8), T.int64(2)):
                        for w_3_fused in T.vectorized(T.int64(4)):
                            with T.sblock("compute_update"):
                                v_b = T.axis.spatial(T.int64(1), b_1 + b_2 + b_3)
                                v_c = T.axis.spatial(T.int64(24), c_1 * T.int64(8) + c_2 * T.int64(8) + c_3)
                                v_h = T.axis.spatial(T.int64(128), b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64) + h_1 * T.int64(32) + h_2 * T.int64(2) + h_3)
                                v_w = T.axis.spatial(T.int64(128), b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + w_1 * T.int64(4) + w_2 * T.int64(4) + w_3_fused)
                                v_dc = T.axis.reduce(T.int64(48), dc_0 * T.int64(4) + dc_1)
                                v_dh = T.axis.reduce(T.int64(3), dh_0 * T.int64(3) + dh_1)
                                v_dw = T.axis.reduce(T.int64(3), dw_0 * T.int64(3) + dw_1)
                                T.reads(T_add_intermediate[v_b, v_c, v_h, v_w], data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw], kernel_transform[v_c, v_dc, v_dh, v_dw])
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = T_add_intermediate[v_b, v_c, v_h, v_w] + data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw] * kernel_transform[v_c, v_dc, v_dh, v_dw]
