# Schedule-preserving reference/edit seed for fused_conv2d3_add15.
#
# Source:
# - recovered from the post-database full-module path via MetaScheduleApplyDatabase
# - source operator global: fused_conv2d3_add15
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
    def fused_conv2d3_add15(lv347: T.Buffer((T.int64(1), T.int64(12), T.int64(262), T.int64(262)), "float32"), param_0: T.Buffer((T.int64(3), T.int64(12), T.int64(7), T.int64(7)), "float32"), lv349: T.Buffer((T.int64(1), T.int64(3), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(3), T.int64(256), T.int64(256)), "float32")):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        conv2d_nchw_intermediate = T.alloc_buffer((T.int64(1), T.int64(3), T.int64(256), T.int64(256)))
        for nn_0_ff_0_yy_0_xx_0_fused in T.parallel(T.int64(64), annotations={"pragma_auto_unroll_max_step": 256, "pragma_unroll_explicit": 1}):
            for nn_1, ff_1, yy_1, xx_1 in T.grid(T.int64(1), T.int64(1), T.int64(1), T.int64(1)):
                for nn_2_init, ff_2_init, yy_2_init, xx_2_init, nn_3_init, ff_3_init, yy_3_init in T.grid(T.int64(1), T.int64(1), T.int64(16), T.int64(4), T.int64(1), T.int64(3), T.int64(1)):
                    for xx_3_fused_init in T.vectorized(T.int64(16)):
                        with T.sblock("conv2d_nchw_init"):
                            v_nn = T.axis.spatial(T.int64(1), nn_1 + nn_2_init + nn_3_init)
                            v_ff = T.axis.spatial(T.int64(3), ff_1 * T.int64(3) + ff_2_init * T.int64(3) + ff_3_init)
                            v_yy = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused // T.int64(4) * T.int64(16) + yy_1 * T.int64(16) + yy_2_init + yy_3_init)
                            v_xx = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused % T.int64(4) * T.int64(64) + xx_1 * T.int64(64) + xx_2_init * T.int64(16) + xx_3_fused_init)
                            T.reads()
                            T.writes(conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx])
                            T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                            conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx] = T.float32(0.0)
                for rc_0, ry_0, rx_0, nn_2, ff_2, yy_2, xx_2, rc_1, ry_1, rx_1, nn_3, ff_3, yy_3 in T.grid(T.int64(6), T.int64(1), T.int64(1), T.int64(1), T.int64(1), T.int64(16), T.int64(4), T.int64(2), T.int64(7), T.int64(7), T.int64(1), T.int64(3), T.int64(1)):
                    for xx_3_fused in T.vectorized(T.int64(16)):
                        with T.sblock("conv2d_nchw_update"):
                            v_nn = T.axis.spatial(T.int64(1), nn_1 + nn_2 + nn_3)
                            v_ff = T.axis.spatial(T.int64(3), ff_1 * T.int64(3) + ff_2 * T.int64(3) + ff_3)
                            v_yy = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused // T.int64(4) * T.int64(16) + yy_1 * T.int64(16) + yy_2 + yy_3)
                            v_xx = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused % T.int64(4) * T.int64(64) + xx_1 * T.int64(64) + xx_2 * T.int64(16) + xx_3_fused)
                            v_rc = T.axis.reduce(T.int64(12), rc_0 * T.int64(2) + rc_1)
                            v_ry = T.axis.reduce(T.int64(7), ry_0 * T.int64(7) + ry_1)
                            v_rx = T.axis.reduce(T.int64(7), rx_0 * T.int64(7) + rx_1)
                            T.reads(conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx], lv347[v_nn, v_rc, v_yy + v_ry, v_xx + v_rx], param_0[v_ff, v_rc, v_ry, v_rx])
                            T.writes(conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx])
                            T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                            conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx] = conv2d_nchw_intermediate[v_nn, v_ff, v_yy, v_xx] + lv347[v_nn, v_rc, v_yy + v_ry, v_xx + v_rx] * param_0[v_ff, v_rc, v_ry, v_rx]
            for ax0, ax1, ax2, ax3 in T.grid(T.int64(1), T.int64(3), T.int64(16), T.int64(64)):
                with T.sblock("T_add"):
                    v_ax0, v_ax1 = T.axis.remap("SS", [ax0, ax1])
                    v_ax2 = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused // T.int64(4) * T.int64(16) + ax2)
                    v_ax3 = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused % T.int64(4) * T.int64(64) + ax3)
                    T.reads(conv2d_nchw_intermediate[v_ax0, v_ax1, v_ax2, v_ax3], lv349[v_ax0, v_ax1, T.int64(0), T.int64(0)])
                    T.writes(T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3])
                    T_add_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] = conv2d_nchw_intermediate[v_ax0, v_ax1, v_ax2, v_ax3] + lv349[v_ax0, v_ax1, T.int64(0), T.int64(0)]
