# Editable scheduled-form candidate v2 working copy for fused_conv2d_transpose_add6.
#
# Derived from:
# - checked-in scheduled reference seed: ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_post_db_scheduled_reference_seed_tir.py
# - accepted v1 working copy: ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py
# - checked-in scheduled reference manifest: ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/post_db_scheduled_reference_seed_manifest.json
#
# Contract:
# - local-only diagnostic working copy
# - start here for the first transpose1-style transpose_add6 data-locality edit
# - keep the scheduled reference seed and accepted v1 baseline frozen
# - do not treat this file as hook-facing or as performance evidence
#
# First real v2 locality edit:
# - keep the accepted v1 bias-fused compute_init/compute_update path intact
# - keep data_dilate materialized once for the whole operator call
# - move the tile-local data_pad staging inside dc_0 so only one 16-channel
#   reduction slice of the 6 x 10 padded patch is prepared at a time
# - immediately reuse that staged dc_0 slice across all three c_1 groups before
#   staging the next slice
# - keep kernel_transform, tiling, reduction order, and unroll settings intact
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose_add6(
        lv304: T.Buffer(
            (T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"
        ),
        param_0: T.Buffer(
            (T.int64(96), T.int64(48), T.int64(3), T.int64(3)), "float32"
        ),
        lv306: T.Buffer(
            (T.int64(1), T.int64(48), T.int64(1), T.int64(1)), "float32"
        ),
        T_add_intermediate: T.Buffer(
            (T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"
        ),
    ):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        data_dilate = T.alloc_buffer(
            (T.int64(1), T.int64(96), T.int64(63), T.int64(63))
        )
        data_pad = T.alloc_buffer(
            (T.int64(1), T.int64(96), T.int64(66), T.int64(66))
        )
        kernel_transform = T.alloc_buffer(
            (T.int64(48), T.int64(96), T.int64(3), T.int64(3))
        )
        for i0_i1_fused in T.parallel(T.int64(96)):
            for i2, i3 in T.grid(T.int64(63), T.int64(63)):
                with T.sblock("data_dilate"):
                    v_i0 = T.axis.spatial(T.int64(1), T.int64(0))
                    v_i1, v_i2, v_i3 = T.axis.remap("SSS", [i0_i1_fused, i2, i3])
                    T.reads(lv304[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                    T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                    data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                        v_i2 % T.int64(2) == T.int64(0)
                        and v_i3 % T.int64(2) == T.int64(0),
                        lv304[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)],
                        T.float32(0.0),
                    )
        for o_fused in T.parallel(T.int64(48)):
            for i in range(T.int64(96)):
                for h_w_fused in T.vectorized(T.int64(9)):
                    with T.sblock("kernel_transform"):
                        v_o, v_i = T.axis.remap("SS", [o_fused, i])
                        v_h = T.axis.spatial(T.int64(3), h_w_fused // T.int64(3))
                        v_w = T.axis.spatial(T.int64(3), h_w_fused % T.int64(3))
                        T.reads(
                            param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w]
                        )
                        T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                        kernel_transform[v_o, v_i, v_h, v_w] = param_0[
                            v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w
                        ]
        for b_0_c_0_h_0_w_0_fused_fused in T.parallel(
            T.int64(128),
            annotations={"pragma_auto_unroll_max_step": 32, "pragma_unroll_explicit": 1},
        ):
            for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                for h_1, w_1 in T.grid(T.int64(1), T.int64(1)):
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
                        T.int64(4),
                        T.int64(2),
                        T.int64(2),
                        T.int64(1),
                        T.int64(4),
                        T.int64(2),
                    ):
                        for w_3_fused_init in T.vectorized(T.int64(4)):
                            with T.sblock("compute_init"):
                                v_b = T.axis.spatial(
                                    T.int64(1), b_1 + b_2_init + b_3_init
                                )
                                v_c = T.axis.spatial(
                                    T.int64(48),
                                    c_1 * T.int64(16)
                                    + c_2_init * T.int64(4)
                                    + c_3_init,
                                )
                                v_h = T.axis.spatial(
                                    T.int64(64),
                                    b_0_c_0_h_0_w_0_fused_fused // T.int64(8)
                                    * T.int64(4)
                                    + h_1 * T.int64(4)
                                    + h_2_init * T.int64(2)
                                    + h_3_init,
                                )
                                v_w = T.axis.spatial(
                                    T.int64(64),
                                    b_0_c_0_h_0_w_0_fused_fused % T.int64(8)
                                    * T.int64(8)
                                    + w_1 * T.int64(8)
                                    + w_2_init * T.int64(4)
                                    + w_3_fused_init,
                                )
                                T.reads(lv306[v_b, v_c, T.int64(0), T.int64(0)])
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = lv306[
                                    v_b, v_c, T.int64(0), T.int64(0)
                                ]
            for dc_0 in T.serial(T.int64(6)):
                for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(16), T.int64(6)):
                    for ax3_fused in T.vectorized(T.int64(10)):
                        with T.sblock("data_pad"):
                            v_i0 = T.axis.spatial(T.int64(1), ax0)
                            v_i1 = T.axis.spatial(
                                T.int64(96), dc_0 * T.int64(16) + ax1
                            )
                            v_i2 = T.axis.spatial(
                                T.int64(66),
                                b_0_c_0_h_0_w_0_fused_fused // T.int64(8)
                                * T.int64(4)
                                + ax2,
                            )
                            v_i3 = T.axis.spatial(
                                T.int64(66),
                                b_0_c_0_h_0_w_0_fused_fused % T.int64(8)
                                * T.int64(8)
                                + ax3_fused,
                            )
                            T.reads(
                                data_dilate[
                                    v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)
                                ]
                            )
                            T.writes(data_pad[v_i0, v_i1, v_i2, v_i3])
                            data_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                                T.int64(1) <= v_i2
                                and v_i2 < T.int64(64)
                                and T.int64(1) <= v_i3
                                and v_i3 < T.int64(64),
                                data_dilate[
                                    v_i0, v_i1, v_i2 - T.int64(1), v_i3 - T.int64(1)
                                ],
                                T.float32(0.0),
                            )
                for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                    for h_1, w_1 in T.grid(T.int64(1), T.int64(1)):
                        for (
                            dh_0,
                            dw_0,
                            b_2,
                            c_2,
                            h_2,
                            w_2,
                            dc_1,
                            dh_1,
                            dw_1,
                            b_3,
                            c_3,
                            h_3,
                        ) in T.grid(
                            T.int64(1),
                            T.int64(1),
                            T.int64(1),
                            T.int64(4),
                            T.int64(2),
                            T.int64(2),
                            T.int64(16),
                            T.int64(3),
                            T.int64(3),
                            T.int64(1),
                            T.int64(4),
                            T.int64(2),
                        ):
                            for w_3_fused in T.vectorized(T.int64(4)):
                                with T.sblock("compute_update"):
                                    v_b = T.axis.spatial(T.int64(1), b_1 + b_2 + b_3)
                                    v_c = T.axis.spatial(
                                        T.int64(48),
                                        c_1 * T.int64(16) + c_2 * T.int64(4) + c_3,
                                    )
                                    v_h = T.axis.spatial(
                                        T.int64(64),
                                        b_0_c_0_h_0_w_0_fused_fused // T.int64(8)
                                        * T.int64(4)
                                        + h_1 * T.int64(4)
                                        + h_2 * T.int64(2)
                                        + h_3,
                                    )
                                    v_w = T.axis.spatial(
                                        T.int64(64),
                                        b_0_c_0_h_0_w_0_fused_fused % T.int64(8)
                                        * T.int64(8)
                                        + w_1 * T.int64(8)
                                        + w_2 * T.int64(4)
                                        + w_3_fused,
                                    )
                                    v_dc = T.axis.reduce(
                                        T.int64(96), dc_0 * T.int64(16) + dc_1
                                    )
                                    v_dh = T.axis.reduce(
                                        T.int64(3), dh_0 * T.int64(3) + dh_1
                                    )
                                    v_dw = T.axis.reduce(
                                        T.int64(3), dw_0 * T.int64(3) + dw_1
                                    )
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
