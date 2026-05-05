# Editable scheduled-form candidate v2 working copy for fused_conv2d_transpose2_add12.
#
# Derived from the accepted checked-in scheduled-form v1 bias-fused baseline.
#
# Contract:
# - local-only diagnostic working copy
# - keep the accepted v1 candidate intact; iterate here for the next step
# - do not treat this file as hook-facing or as performance evidence
#
# New candidate goal:
# - keep the accepted v1 bias-fused compute path intact
# - fuse the materialized data_dilate + data_pad path into one materialized
#   data_dilate_pad buffer so the separate 255x255 intermediate is removed
# - preserve kernel_transform, the scheduled h/w tiling, reduction split,
#   outer w_0 sweep, and pragma_auto_unroll_max_step=32
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose2_add12(lv332: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"), param_0: T.Buffer((T.int64(24), T.int64(12), T.int64(3), T.int64(3)), "float32"), lv334: T.Buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32")):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        data_dilate_pad = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(258), T.int64(258)))
        kernel_transform = T.alloc_buffer((T.int64(12), T.int64(24), T.int64(3), T.int64(3)))
        for o_i_fused in T.parallel(T.int64(288)):
            for h_w_fused in T.vectorized(T.int64(9)):
                with T.sblock("kernel_transform"):
                    v_o = T.axis.spatial(T.int64(12), o_i_fused // T.int64(24))
                    v_i = T.axis.spatial(T.int64(24), o_i_fused % T.int64(24))
                    v_h = T.axis.spatial(T.int64(3), h_w_fused // T.int64(3))
                    v_w = T.axis.spatial(T.int64(3), h_w_fused % T.int64(3))
                    T.reads(param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w])
                    T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                    kernel_transform[v_o, v_i, v_h, v_w] = param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w]
        for b_0_c_0_h_0_fused_fused_fused in T.parallel(T.int64(32), annotations={"pragma_auto_unroll_max_step": 32, "pragma_unroll_explicit": 1}):
            for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(24), T.int64(10)):
                for ax3 in range(T.int64(258)):
                    with T.sblock("data_dilate_pad"):
                        v_i0, v_i1 = T.axis.remap("SS", [ax0, ax1])
                        v_i2 = T.axis.spatial(T.int64(258), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + ax2)
                        v_i3 = T.axis.spatial(T.int64(258), ax3)
                        T.reads(lv332[v_i0, v_i1, (v_i2 - T.int64(1)) // T.int64(2), (v_i3 - T.int64(1)) // T.int64(2)])
                        T.writes(data_dilate_pad[v_i0, v_i1, v_i2, v_i3])
                        data_dilate_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                            T.int64(1) <= v_i2 and v_i2 < T.int64(256) and T.int64(1) <= v_i3 and v_i3 < T.int64(256) and (v_i2 - T.int64(1)) % T.int64(2) == T.int64(0) and (v_i3 - T.int64(1)) % T.int64(2) == T.int64(0),
                            lv332[v_i0, v_i1, (v_i2 - T.int64(1)) // T.int64(2), (v_i3 - T.int64(1)) // T.int64(2)],
                            T.float32(0.0),
                        )
            for w_0 in range(T.int64(8)):
                for b_1, c_1, h_1, w_1 in T.grid(T.int64(1), T.int64(1), T.int64(4), T.int64(1)):
                    for b_2_init, c_2_init, h_2_init, w_2_init, b_3_init, c_3_init, h_3_init in T.grid(T.int64(1), T.int64(1), T.int64(2), T.int64(4), T.int64(1), T.int64(12), T.int64(1)):
                        for w_3_fused_init in T.vectorized(T.int64(8)):
                            with T.sblock("compute_init"):
                                v_b = T.axis.spatial(T.int64(1), b_1 + b_2_init + b_3_init)
                                v_c = T.axis.spatial(T.int64(12), c_1 * T.int64(12) + c_2_init * T.int64(12) + c_3_init)
                                v_h = T.axis.spatial(T.int64(256), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + h_1 * T.int64(2) + h_2_init + h_3_init)
                                v_w = T.axis.spatial(T.int64(256), w_0 * T.int64(32) + w_1 * T.int64(32) + w_2_init * T.int64(8) + w_3_fused_init)
                                T.reads(lv334[v_b, v_c, T.int64(0), T.int64(0)])
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = lv334[v_b, v_c, T.int64(0), T.int64(0)]
                    for dc_0, dh_0, dw_0, b_2, c_2, h_2, w_2, dc_1, dh_1, dw_1, b_3, c_3, h_3 in T.grid(T.int64(4), T.int64(1), T.int64(1), T.int64(1), T.int64(1), T.int64(2), T.int64(4), T.int64(6), T.int64(3), T.int64(3), T.int64(1), T.int64(12), T.int64(1)):
                        for w_3_fused in T.vectorized(T.int64(8)):
                            with T.sblock("compute_update"):
                                v_b = T.axis.spatial(T.int64(1), b_1 + b_2 + b_3)
                                v_c = T.axis.spatial(T.int64(12), c_1 * T.int64(12) + c_2 * T.int64(12) + c_3)
                                v_h = T.axis.spatial(T.int64(256), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + h_1 * T.int64(2) + h_2 + h_3)
                                v_w = T.axis.spatial(T.int64(256), w_0 * T.int64(32) + w_1 * T.int64(32) + w_2 * T.int64(8) + w_3_fused)
                                v_dc = T.axis.reduce(T.int64(24), dc_0 * T.int64(6) + dc_1)
                                v_dh = T.axis.reduce(T.int64(3), dh_0 * T.int64(3) + dh_1)
                                v_dw = T.axis.reduce(T.int64(3), dw_0 * T.int64(3) + dw_1)
                                T.reads(T_add_intermediate[v_b, v_c, v_h, v_w], data_dilate_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw], kernel_transform[v_c, v_dc, v_dh, v_dw])
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = T_add_intermediate[v_b, v_c, v_h, v_w] + data_dilate_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw] * kernel_transform[v_c, v_dc, v_dh, v_dw]
