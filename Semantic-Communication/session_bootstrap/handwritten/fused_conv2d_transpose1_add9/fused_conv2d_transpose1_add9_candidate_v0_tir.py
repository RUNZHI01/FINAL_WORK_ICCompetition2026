# First-pass handwritten TIR candidate v0 for fused_conv2d_transpose1_add9.
#
# Conservative delta versus the checked-in editable seed:
# - fold the final bias add into the reduction init
# - remove the full-size compute_intermediate buffer and trailing T_add loop
#
# This keeps the same input/output contract and leaves data_dilate, data_pad,
# and kernel_transform unchanged for now.
from tvm.script import ir as I
from tvm.script import tir as T


@I.ir_module
class Module:
    @T.prim_func
    def main(
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
        T.func_attr({"tir.noalias": True})
        data_dilate = T.alloc_buffer(
            (T.int64(1), T.int64(48), T.int64(127), T.int64(127))
        )
        data_pad = T.alloc_buffer((T.int64(1), T.int64(48), T.int64(130), T.int64(130)))
        kernel_transform = T.alloc_buffer(
            (T.int64(24), T.int64(48), T.int64(3), T.int64(3))
        )
        for i0, i1, i2, i3 in T.grid(
            T.int64(1), T.int64(48), T.int64(127), T.int64(127)
        ):
            with T.sblock("data_dilate"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
                T.reads(lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)])
                T.writes(data_dilate[v_i0, v_i1, v_i2, v_i3])
                data_dilate[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                    v_i2 % T.int64(2) == T.int64(0)
                    and v_i3 % T.int64(2) == T.int64(0),
                    lv318[v_i0, v_i1, v_i2 // T.int64(2), v_i3 // T.int64(2)],
                    T.float32(0.0),
                )
        for i0, i1, i2, i3 in T.grid(
            T.int64(1), T.int64(48), T.int64(130), T.int64(130)
        ):
            with T.sblock("data_pad"):
                v_i0, v_i1, v_i2, v_i3 = T.axis.remap("SSSS", [i0, i1, i2, i3])
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
        for o, i, h, w in T.grid(T.int64(24), T.int64(48), T.int64(3), T.int64(3)):
            with T.sblock("kernel_transform"):
                v_o, v_i, v_h, v_w = T.axis.remap("SSSS", [o, i, h, w])
                T.reads(param_0[v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w])
                T.writes(kernel_transform[v_o, v_i, v_h, v_w])
                kernel_transform[v_o, v_i, v_h, v_w] = param_0[
                    v_i, v_o, T.int64(2) - v_h, T.int64(2) - v_w
                ]
        for b, c, h, w, dc, dh, dw in T.grid(
            T.int64(1),
            T.int64(24),
            T.int64(128),
            T.int64(128),
            T.int64(48),
            T.int64(3),
            T.int64(3),
        ):
            with T.sblock("compute"):
                v_b, v_c, v_h, v_w, v_dc, v_dh, v_dw = T.axis.remap(
                    "SSSSRRR", [b, c, h, w, dc, dh, dw]
                )
                T.reads(
                    data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw],
                    kernel_transform[v_c, v_dc, v_dh, v_dw],
                    lv320[v_b, v_c, T.int64(0), T.int64(0)],
                )
                T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
                with T.init():
                    T_add_intermediate[v_b, v_c, v_h, v_w] = lv320[
                        v_b, v_c, T.int64(0), T.int64(0)
                    ]
                T_add_intermediate[v_b, v_c, v_h, v_w] = (
                    T_add_intermediate[v_b, v_c, v_h, v_w]
                    + data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw]
                    * kernel_transform[v_c, v_dc, v_dh, v_dw]
                )
