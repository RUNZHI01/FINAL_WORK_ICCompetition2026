# Editable scheduled-form candidate v3 working copy for fused_conv2d_transpose1_add9.
#
# Derived from:
# - accepted scheduled-form baseline: ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py
# - accepted local/remote state: P2 output-channel tiling + P4 auto-unroll tuning
#
# Contract:
# - local-only diagnostic working copy
# - do not treat this file as hook-facing or as performance evidence
# - keep the accepted P2+P4 baseline frozen in v1 so this file can be dropped cleanly
#
# New candidate goal:
# - follow the documented transpose1 P3 path A instead of repeating the losing P1
#   dilate+pad fusion move
# - remove the materialized data_dilate/data_pad staging path entirely
# - keep kernel_transform materialized and keep the accepted P2+P4 loop structure
# - read lv318 directly from compute_update through stride/parity guards
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose1_add9(
        lv318: T.Buffer(
            (T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"
        ),
        param_0: T.Buffer(
            (T.int64(48), T.int64(24), T.int64(3), T.int64(3)), "float32"
        ),
        lv320: T.Buffer((T.int64(1), T.int64(24), T.int64(1), T.int64(1)), "float32"),
        T_add_intermediate: T.Buffer(
            (T.int64(1), T.int64(24), T.int64(128), T.int64(128)), "float32"
        ),
    ):
        T.func_attr({"tir.is_scheduled": True, "tir.noalias": True})
        # with T.sblock("root"):
        kernel_transform = T.alloc_buffer(
            (T.int64(24), T.int64(48), T.int64(3), T.int64(3))
        )
        for o_i_fused in T.parallel(T.int64(1152)):
            for h_w_fused in T.vectorized(T.int64(9)):
                with T.sblock("kernel_transform"):
                    v_o = T.axis.spatial(T.int64(24), o_i_fused // T.int64(48))
                    v_i = T.axis.spatial(T.int64(48), o_i_fused % T.int64(48))
                    v_h = T.axis.spatial(T.int64(3), h_w_fused // T.int64(3))
                    v_w = T.axis.spatial(T.int64(3), h_w_fused % T.int64(3))
                    T.reads(
                        param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w]
                    )
                    T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                    kernel_transform[v_o, v_i, v_h, v_w] = param_0[
                        v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w
                    ]
        for b_0_c_0_h_0_w_0_fused_fused_fused in T.parallel(
            T.int64(32),
            annotations={"pragma_auto_unroll_max_step": 64, "pragma_unroll_explicit": 1},
        ):
            for b_1, c_1 in T.grid(T.int64(1), T.int64(3)):
                for h_1, w_1 in T.grid(T.int64(2), T.int64(2)):
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
                                v_b = T.axis.spatial(
                                    T.int64(1), b_1 + b_2_init + b_3_init
                                )
                                v_c = T.axis.spatial(
                                    T.int64(24),
                                    c_1 * T.int64(8)
                                    + c_2_init * T.int64(8)
                                    + c_3_init,
                                )
                                v_h = T.axis.spatial(
                                    T.int64(128),
                                    b_0_c_0_h_0_w_0_fused_fused_fused
                                    // T.int64(16)
                                    * T.int64(64)
                                    + h_1 * T.int64(32)
                                    + h_2_init * T.int64(2)
                                    + h_3_init,
                                )
                                v_w = T.axis.spatial(
                                    T.int64(128),
                                    b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                    * T.int64(8)
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
                    for (
                        dc_0,
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
                        T.int64(12),
                        T.int64(1),
                        T.int64(1),
                        T.int64(1),
                        T.int64(1),
                        T.int64(16),
                        T.int64(1),
                        T.int64(4),
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
                                    T.int64(24),
                                    c_1 * T.int64(8) + c_2 * T.int64(8) + c_3,
                                )
                                v_h = T.axis.spatial(
                                    T.int64(128),
                                    b_0_c_0_h_0_w_0_fused_fused_fused
                                    // T.int64(16)
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
                                v_dc = T.axis.reduce(T.int64(48), dc_0 * T.int64(4) + dc_1)
                                v_dh = T.axis.reduce(T.int64(3), dh_0 * T.int64(3) + dh_1)
                                v_dw = T.axis.reduce(T.int64(3), dw_0 * T.int64(3) + dw_1)
                                T.reads(
                                    T_add_intermediate[v_b, v_c, v_h, v_w],
                                    lv318[
                                        v_b,
                                        v_dc,
                                        T.min(
                                            T.max(
                                                (v_h + v_dh - T.int64(1))
                                                // T.int64(2),
                                                T.int64(0),
                                            ),
                                            T.int64(63),
                                        ),
                                        T.min(
                                            T.max(
                                                (v_w + v_dw - T.int64(1))
                                                // T.int64(2),
                                                T.int64(0),
                                            ),
                                            T.int64(63),
                                        ),
                                    ],
                                    kernel_transform[v_c, v_dc, v_dh, v_dw],
                                )
                                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                                T.sblock_attr({"meta_schedule.tiling_structure": "SSRSRS"})
                                T_add_intermediate[v_b, v_c, v_h, v_w] = (
                                    T_add_intermediate[v_b, v_c, v_h, v_w]
                                    + T.if_then_else(
                                        T.int64(0) <= v_h + v_dh - T.int64(1)
                                        and v_h + v_dh - T.int64(1) < T.int64(127)
                                        and (v_h + v_dh - T.int64(1)) % T.int64(2)
                                        == T.int64(0)
                                        and T.int64(0) <= v_w + v_dw - T.int64(1)
                                        and v_w + v_dw - T.int64(1) < T.int64(127)
                                        and (v_w + v_dw - T.int64(1)) % T.int64(2)
                                        == T.int64(0),
                                        lv318[
                                            v_b,
                                            v_dc,
                                            (v_h + v_dh - T.int64(1)) // T.int64(2),
                                            (v_w + v_dw - T.int64(1)) // T.int64(2),
                                        ]
                                        * kernel_transform[v_c, v_dc, v_dh, v_dw],
                                        T.float32(0.0),
                                    )
                                )
