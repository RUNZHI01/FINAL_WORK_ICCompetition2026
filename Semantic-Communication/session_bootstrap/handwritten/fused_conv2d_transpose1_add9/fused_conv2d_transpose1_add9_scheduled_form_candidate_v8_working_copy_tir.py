# Editable scheduled-form candidate v8 working copy for fused_conv2d_transpose1_add9.
#
# Derived from:
# - checked-in scheduled reference seed: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py
# - checked-in scheduled reference manifest: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json
# - distinct from the older raw pre-compile editable seed: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_editable_seed_tir.py
# - distinct from the checked-in candidate v0: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_candidate_v0_tir.py
#
# Contract:
# - local-only diagnostic working copy
# - this file intentionally starts as a clean clone of the winning transpose1
#   v7 staged-reuse state
# - apply the next genuinely different transpose1 edit here
# - keep the scheduled reference seed, the accepted v1/P2/P4 file, and the
#   winning v4/v6/v7 files frozen so this scaffold can be refreshed or
#   discarded safely
# - do not treat this file as hook-facing or as performance evidence
#
# Accepted baseline carried forward into this v8 scaffold:
# - keep the scheduled-form v1 bias fusion intact
# - keep the accepted P2 output-channel tiling c_1 x c_3 = 3 x 8
# - keep the accepted P4 pragma_auto_unroll_max_step = 64
# - keep data_dilate, data_pad, and kernel_transform materialized
# - keep the winning v7 h_1 stripe shape and c_1-before-w_1 consumer order
# - keep the winning v7 staged-reuse family rooted in local data materialization
#
# First real v8 locality/schedule edit:
# - keep the v7 one-h_1-at-a-time 34 x 10 stripe and c_1-before-w_1 reuse
# - narrow the staged reduction slice from one 4-channel dc_0 slice to one
#   input channel at a time
# - reuse each staged single-channel stripe across all three c_1 groups and
#   both w_1 positions before staging the next input channel
# - keep the failed broad and producer-only h_1 overlap-carry ideas closed
# - keep raw pre-compile v0, P1 dilate+pad fusion, P3 direct-stride-read, and
#   the dropped v5 consumer-order branch closed
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose1_add9(
        lv318: T.Buffer((T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"),
        param_0: T.Buffer((T.int64(48), T.int64(24), T.int64(3), T.int64(3)), "float32"),
        lv320: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"),
        T_add_intermediate: T.Buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"),
    ):
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
                    kernel_transform[v_o, v_i, v_h, v_w] = param_0[
                        v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w
                    ]
        for b_0_c_0_h_0_w_0_fused_fused_fused in T.parallel(
            T.int64(32),
            annotations={"pragma_auto_unroll_max_step": 64, "pragma_unroll_explicit": 1},
        ):
            for h_1 in T.serial(T.int64(2)):
                for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                    for w_1 in T.serial(T.int64(2)):
                        for (
                            b_2_init,
                            c_2_init,
                            h_2_init,
                            w_2_init,
                            b_3_init,
                            c_3_init,
                            h_3_init,
                        ) in T.grid(
                            T.int64(1),
                            T.int64(1),
                            T.int64(16),
                            T.int64(1),
                            T.int64(1),
                            T.int64(8),
                            T.int64(2),
                        ):
                            for w_3_fused_init in T.vectorized(T.int64(4)):
                                with T.sblock("compute_init"):
                                    v_b = T.axis.spatial(T.int64(1), b_1 + b_2_init + b_3_init)
                                    v_c = T.axis.spatial(
                                        T.int64(24),
                                        c_1 * T.int64(8) + c_2_init * T.int64(8) + c_3_init,
                                    )
                                    v_h = T.axis.spatial(
                                        T.int64(128),
                                        b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64)
                                        + h_1 * T.int64(32)
                                        + h_2_init * T.int64(2)
                                        + h_3_init,
                                    )
                                    v_w = T.axis.spatial(
                                        T.int64(128),
                                        b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8)
                                        + w_1 * T.int64(4)
                                        + w_2_init * T.int64(4)
                                        + w_3_fused_init,
                                    )
                                    T.reads(lv320[v_b, v_c, T.int64(0), T.int64(0)])
                                    T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                    T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                    T_add_intermediate[v_b, v_c, v_h, v_w] = lv320[
                                        v_b, v_c, T.int64(0), T.int64(0)
                                    ]
                for dc_0 in T.serial(T.int64(48)):
                    for ax0, ax2 in T.grid(T.int64(1), T.int64(34)):
                        for ax2_ax3_fused in T.vectorized(T.int64(10)):
                            with T.sblock("data_dilate"):
                                v_i0 = T.axis.spatial(T.int64(1), ax0)
                                v_i1 = T.axis.spatial(T.int64(48), dc_0)
                                v_i2 = T.axis.spatial(
                                    T.int64(127),
                                    b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64)
                                    + h_1 * T.int64(32)
                                    + ax2
                                    + T.int64(-1),
                                )
                                v_i3 = T.axis.spatial(
                                    T.int64(127),
                                    b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8)
                                    + ax2_ax3_fused
                                    + T.int64(-1),
                                )
                                T.where(
                                    T.int64(1)
                                    <= b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(32)
                                    // T.int64(16)
                                    * T.int64(64)
                                    + h_1 * T.int64(32)
                                    + ax2
                                    and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(32)
                                    // T.int64(16)
                                    * T.int64(64)
                                    + h_1 * T.int64(32)
                                    + ax2
                                    < T.int64(128)
                                    and T.int64(1)
                                    <= b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                    * T.int64(8)
                                    + ax2_ax3_fused % T.int64(10)
                                    and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                    * T.int64(8)
                                    + ax2_ax3_fused % T.int64(10)
                                    < T.int64(128)
                                )
                                T.reads(lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                                T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                                data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                                    v_i2 % T.int64(2) == T.int64(0)
                                    and v_i3 % T.int64(2) == T.int64(0),
                                    lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)],
                                    T.float32(0.0),
                                )
                        for ax3_fused in T.vectorized(T.int64(10)):
                            with T.sblock("data_pad"):
                                v_i0 = T.axis.spatial(T.int64(1), ax0)
                                v_i1 = T.axis.spatial(T.int64(48), dc_0)
                                v_i2 = T.axis.spatial(
                                    T.int64(130),
                                    b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64)
                                    + h_1 * T.int64(32)
                                    + ax2,
                                )
                                v_i3 = T.axis.spatial(
                                    T.int64(130),
                                    b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8)
                                    + ax3_fused,
                                )
                                T.reads(data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)])
                                T.writes(data_pad[v_i0, v_i1, v_i2, v_i3])
                                data_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                                    T.int64(1) <= v_i2
                                    and v_i2 < T.int64(128)
                                    and T.int64(1) <= v_i3
                                    and v_i3 < T.int64(128),
                                    data_dilate[v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)],
                                    T.float32(0.0),
                                )
                    for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                        for w_1 in T.serial(T.int64(2)):
                            for (
                                dh_0,
                                dw_0,
                                b_2,
                                c_2,
                                h_2,
                                w_2,
                                dh_1,
                                dw_1,
                                b_3,
                                c_3,
                                h_3,
                            ) in T.grid(
                                T.int64(1),
                                T.int64(1),
                                T.int64(1),
                                T.int64(1),
                                T.int64(16),
                                T.int64(1),
                                T.int64(3),
                                T.int64(3),
                                T.int64(1),
                                T.int64(8),
                                T.int64(2),
                            ):
                                for w_3_fused in T.vectorized(T.int64(4)):
                                    with T.sblock("compute_update"):
                                        v_b = T.axis.spatial(T.int64(1), b_1 + b_2 + b_3)
                                        v_c = T.axis.spatial(
                                            T.int64(24), c_1 * T.int64(8) + c_2 * T.int64(8) + c_3
                                        )
                                        v_h = T.axis.spatial(
                                            T.int64(128),
                                            b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16)
                                            * T.int64(64)
                                            + h_1 * T.int64(32)
                                            + h_2 * T.int64(2)
                                            + h_3,
                                        )
                                        v_w = T.axis.spatial(
                                            T.int64(128),
                                            b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                            * T.int64(8)
                                            + w_1 * T.int64(4)
                                            + w_2 * T.int64(4)
                                            + w_3_fused,
                                        )
                                        v_dc = T.axis.reduce(T.int64(48), dc_0)
                                        v_dh = T.axis.reduce(T.int64(3), dh_0 * T.int64(3) + dh_1)
                                        v_dw = T.axis.reduce(T.int64(3), dw_0 * T.int64(3) + dw_1)
                                        T.reads(
                                            T_add_intermediate[v_b, v_c, v_h, v_w],
                                            data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw],
                                            kernel_transform[v_c, v_dc, v_dh, v_dw],
                                        )
                                        T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                        T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                        T_add_intermediate[v_b, v_c, v_h, v_w] = (
                                            T_add_intermediate[v_b, v_c, v_h, v_w]
                                            + data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw]
                                            * kernel_transform[v_c, v_dc, v_dh, v_dw]
                                        )
