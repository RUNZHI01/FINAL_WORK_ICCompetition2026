# `fused_conv2d_transpose1_add9` handwritten candidate v0

## Intent

This is the first real edit derived from
`fused_conv2d_transpose1_add9_editable_seed_tir.py`.

The v0 change is deliberately narrow:

- fuse the final bias add into the `compute` reduction init
- delete the standalone `compute_intermediate` buffer
- delete the trailing `T_add` loop

## Why this is a conservative first step

- The operator signature is unchanged.
- `data_dilate`, `data_pad`, and `kernel_transform` still match the seed.
- The arithmetic order inside the convolution reduction stays straightforward:
  initialize each output element from bias, then accumulate products.

## Expected effect

This should reduce one full output-sized intermediate write/read pair and
remove one extra pass over the `(1, 24, 128, 128)` output tensor.

It is not yet claimed to be faster. The point of v0 is to make one honest,
reviewable memory-traffic reduction before attempting more aggressive
transpose1-specific scheduling work.

As of `2026-03-31`, this candidate is only valid through the raw pre-compile
handwritten override contract. That path is useful for integration/structure
checks, but it is **not** a schedule-context-preserving performance evaluation
path.

## TODO after v0

- Do not use v0 for further reprobe/promotion decisions.
- Fix the handwritten replacement contract so structural candidates can be
  evaluated without discarding best-staging MetaSchedule schedule context.
- Only return to operator-side candidate v1 work after that contract-side path
  exists.

## Lightweight validation used for this commit

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_candidate_v0_tir.py

python3 - <<'PY'
import importlib.util
import sys
import types
from pathlib import Path

class Dummy:
    def __getattr__(self, name):
        if name == "ir_module":
            return lambda obj: obj
        if name == "prim_func":
            return lambda func: func
        return self
    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self

script_mod = types.ModuleType("tvm.script")
script_mod.ir = Dummy()
script_mod.tir = Dummy()
tvm_mod = types.ModuleType("tvm")
tvm_mod.script = script_mod
sys.modules["tvm"] = tvm_mod
sys.modules["tvm.script"] = script_mod

path = Path("session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_candidate_v0_tir.py")
spec = importlib.util.spec_from_file_location("candidate_v0_tir", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(hasattr(module, "Module"))
PY
```
