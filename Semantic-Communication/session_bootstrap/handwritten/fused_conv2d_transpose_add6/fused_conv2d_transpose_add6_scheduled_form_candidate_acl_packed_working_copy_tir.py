from tvm.script import ir as I
from tvm.script import tir as T

@I.ir_module
class Module:
    @T.prim_func
    def fused_conv2d_transpose_add6(
        lv304: T.Buffer((T.int64(1), T.int64(96), T.int64(32), T.int64(32)), "float32"),
        param_0: T.Buffer((T.int64(96), T.int64(48), T.int64(3), T.int64(3)), "float32"),
        lv306: T.Buffer((T.int64(1), T.int64(48), T.int64(1), T.int64(1)), "float32"),
        T_add_intermediate: T.Buffer((T.int64(1), T.int64(48), T.int64(64), T.int64(64)), "float32"),
    ):
        T.func_attr({"tir.noalias": True, "tir.is_scheduled": True})
        T.evaluate(
            T.call_packed(
                "jscc.acl.transpose_add6",
                lv304,
                param_0,
                lv306,
                T_add_intermediate,
            )
        )
