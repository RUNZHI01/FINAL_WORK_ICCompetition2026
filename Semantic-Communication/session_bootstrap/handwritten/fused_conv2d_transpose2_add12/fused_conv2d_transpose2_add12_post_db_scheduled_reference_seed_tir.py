# Schedule-preserving reference/edit seed for fused_conv2d_transpose2_add12.
#
# Source:
# - recovered from the post-database full-module path via MetaScheduleApplyDatabase
# - source operator global: fused_conv2d_transpose2_add12
# - source task summary: ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json
# - source database dir: ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
#
# Contract:
# - local-only diagnostic reference/edit seed
# - preserve the scheduled form as recovered from the post-db path
# - no runtime or performance claims attach to this file by itself
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose2_add12(lv332: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"), param_0: T.Buffer((T.int64(24), T.int64(12), T.int64(3), T.int64(3)), "float32"), lv334: T.Buffer((T.int64(1), T.int64(12), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)), "float32")):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        data_dilate = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(255), T.int64(255)))
        data_pad = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(258), T.int64(258)))
        kernel_transform = T.alloc_buffer((T.int64(12), T.int64(24), T.int64(3), T.int64(3)))
        compute_intermediate = T.alloc_buffer((T.int64(1), T.int64(12), T.int64(256), T.int64(256)))
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
                for ax0_1, ax1_1, ax2_1, ax3 in T.grid(T.int64(1), T.int64(1), T.int64(1), T.int64(255)):
                    with T.sblock("data_dilate"):
                        v_i0 = T.axis.spatial(T.int64(1), ax0_1)
                        v_i1 = T.axis.spatial(T.int64(24), ax1 + ax1_1)
                        v_i2 = T.axis.spatial(T.int64(255), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + ax2 + T.int64(-1) + ax2_1)
                        v_i3 = T.axis.spatial(T.int64(255), ax3)
                        T.where(T.int64(1) <= b_0_c_0_h_0_fused_fused_fused % T.int64(32) * T.int64(8) + ax2 and b_0_c_0_h_0_fused_fused_fused % T.int64(32) * T.int64(8) + ax2 < T.int64(256))
                        T.reads(lv332[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                        T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                        data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(v_i2 % T.int64(2) == T.int64(0) and v_i3 % T.int64(2) == T.int64(0), lv332[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)], T.float32(0.0))
                for ax3 in range(T.int64(258)):
                    with T.sblock("data_pad"):
                        v_i0, v_i1 = T.axis.remap("SS", [ax0, ax1])
                        v_i2 = T.axis.spatial(T.int64(258), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + ax2)
                        v_i3 = T.axis.spatial(T.int64(258), ax3)
                        T.reads(data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)])
                        T.writes(data_pad[v_i0, v_i1, v_i2, v_i3])
                        data_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(T.int64(1) <= v_i2 and v_i2 < T.int64(256) and T.int64(1) <= v_i3 and v_i3 < T.int64(256), data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)], T.float32(0.0))
            for w_0 in range(T.int64(8)):
                for b_1, c_1, h_1, w_1 in T.grid(T.int64(1), T.int64(1), T.int64(4), T.int64(1)):
                    for b_2_init, c_2_init, h_2_init, w_2_init, b_3_init, c_3_init, h_3_init in T.grid(T.int64(1), T.int64(1), T.int64(2), T.int64(4), T.int64(1), T.int64(12), T.int64(1)):
                        for w_3_fused_init in T.vectorized(T.int64(8)):
                            with T.sblock("compute_init"):
                                v_b = T.axis.spatial(T.int64(1), b_1 + b_2_init + b_3_init)
                                v_c = T.axis.spatial(T.int64(12), c_1 * T.int64(12) + c_2_init * T.int64(12) + c_3_init)
                                v_h = T.axis.spatial(T.int64(256), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + h_1 * T.int64(2) + h_2_init + h_3_init)
                                v_w = T.axis.spatial(T.int64(256), w_0 * T.int64(32) + w_1 * T.int64(32) + w_2_init * T.int64(8) + w_3_fused_init)
                                T.reads()
                                T.writes(compute_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                compute_intermediate[v_b, v_c, v_h, v_w] = T.float32(0.0)
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
                                T.reads(compute_intermediate[v_b, v_c, v_h, v_w], data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw], kernel_transform[v_c, v_dc, v_dh, v_dw])
                                T.writes(compute_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                compute_intermediate[v_b, v_c, v_h, v_w] = compute_intermediate[v_b, v_c, v_h, v_w] + data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw] * kernel_transform[v_c, v_dc, v_dh, v_dw]
                for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(12), T.int64(8)):
                    for ax3_fused in T.vectorized(T.int64(32)):
                        with T.sblock("T_add"):
                            v_ax0, v_ax1 = T.axis.remap("SS", [ax0, ax1])
                            v_ax2 = T.axis.spatial(T.int64(256), b_0_c_0_h_0_fused_fused_fused * T.int64(8) + ax2)
                            v_ax3 = T.axis.spatial(T.int64(256), w_0 * T.int64(32) + ax3_fused)
                            T.reads(compute_intermediate[v_ax0, v_ax1, v_ax2, v_ax3], lv334[v_ax0, v_ax1, T.int64(0), T.int64(0)])
                            T.writes(T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                            T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = compute_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] + lv334[v_ax0, v_ax1, T.int64(0), T.int64(0)]
