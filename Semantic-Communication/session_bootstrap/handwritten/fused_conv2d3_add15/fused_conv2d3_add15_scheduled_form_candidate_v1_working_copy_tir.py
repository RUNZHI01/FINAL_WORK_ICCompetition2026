# Editable scheduled-form candidate v1 working copy for fused_conv2d3_add15.
#
# Derived from:
# - checked-in scheduled reference seed: ./session_bootstrap/handwritten/fused_conv2d3_add15/fused_conv2d3_add15_post_db_scheduled_reference_seed_tir.py
# - checked-in scheduled reference manifest: ./session_bootstrap/handwritten/fused_conv2d3_add15/post_db_scheduled_reference_seed_manifest.json
#
# Contract:
# - local-only diagnostic working copy
# - start here for fused_conv2d3_add15 scheduled-form handwritten edits
# - keep the scheduled reference seed frozen so this file can be refreshed
# - do not treat this file as hook-facing or as performance evidence
#
# First real scheduled-form v1 edit:
# - fold the final bias add into the scheduled conv2d init/update path
# - remove the full-size conv2d_nchw_intermediate buffer and trailing T_add pass
from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d3_add15(lv347: T.Buffer((T.int64(1), T.int64(12), T.int64(262), T.int64(262)), "float32"), param_0: T.Buffer((T.int64(3), T.int64(12), T.int64(7), T.int64(7)), "float32"), lv349: T.Buffer((T.int64(1), T.int64(3), T.int64(1), T.int64(1)), "float32"), T_add_intermediate: T.Buffer((T.int64(1), T.int64(3), T.int64(256), T.int64(256)), "float32")):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        for nn_0_ff_0_yy_0_xx_0_fused in T.parallel(T.int64(64), annotations={"pragma_auto_unroll_max_step": 256, "pragma_unroll_explicit": 1}):
            for nn_1, ff_1, yy_1, xx_1 in T.grid(T.int64(1), T.int64(1), T.int64(1), T.int64(1)):
                for nn_2_init, ff_2_init, yy_2_init, xx_2_init, nn_3_init, ff_3_init, yy_3_init in T.grid(T.int64(1), T.int64(1), T.int64(16), T.int64(4), T.int64(1), T.int64(3), T.int64(1)):
                    for xx_3_fused_init in T.vectorized(T.int64(16)):
                        with T.sblock("conv2d_nchw_init"):
                            v_nn = T.axis.spatial(T.int64(1), nn_1 + nn_2_init + nn_3_init)
                            v_ff = T.axis.spatial(T.int64(3), ff_1 * T.int64(3) + ff_2_init * T.int64(3) + ff_3_init)
                            v_yy = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused // T.int64(4) * T.int64(16) + yy_1 * T.int64(16) + yy_2_init + yy_3_init)
                            v_xx = T.axis.spatial(T.int64(256), nn_0_ff_0_yy_0_xx_0_fused % T.int64(4) * T.int64(64) + xx_1 * T.int64(64) + xx_2_init * T.int64(16) + xx_3_fused_init)
                            T.reads(lv349[v_nn, v_ff, T.int64(0), T.int64(0)])
                            T.writes(T_add_intermediate[v_nn, v_ff, v_yy, v_xx])
                            T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                            T_add_intermediate[v_nn, v_ff, v_yy, v_xx] = lv349[v_nn, v_ff, T.int64(0), T.int64(0)]
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
                            T.reads(T_add_intermediate[v_nn, v_ff, v_yy, v_xx], lv347[v_nn, v_rc, v_yy + v_ry, v_xx + v_rx], param_0[v_ff, v_rc, v_ry, v_rx])
                            T.writes(T_add_intermediate[v_nn, v_ff, v_yy, v_xx])
                            T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                            T_add_intermediate[v_nn, v_ff, v_yy, v_xx] = T_add_intermediate[v_nn, v_ff, v_yy, v_xx] + lv347[v_nn, v_rc, v_yy + v_ry, v_xx + v_rx] * param_0[v_ff, v_rc, v_ry, v_rx]
