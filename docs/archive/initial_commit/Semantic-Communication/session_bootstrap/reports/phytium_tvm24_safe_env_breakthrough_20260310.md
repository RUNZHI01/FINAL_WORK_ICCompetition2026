# Phytium Pi TVM 0.24dev safe-env breakthrough (2026-03-10)

## Executive summary

We now have a **working TVM 0.24.dev0 import path on the Phytium Pi**.

This was **not** fixed by rebuilding `libtvm.so` alone.
The actual blocker chain was:

1. original `tvm310` environment crashed on `import tvm`
2. even after conservative rebuild of TVM C++ libs, `import tvm_ffi.core` still crashed
3. `gdb` showed the real SIGILL did **not** originate in TVM first
4. instead, import resolution reached:
   - `torch/_C.cpython-310-aarch64-linux-gnu.so`
   - then `torch/lib/libc10.so`
   - then crashed in `_mi_options_init`
5. root trigger: `tvm_ffi/__init__.py` eagerly does `import torch`

So the real unblocker was:

- rebuild `tvm_ffi.core` for the Pi,
- **and** avoid eager torch import in the safe environment,
- **and** disable optional torch dlpack hook during bootstrap.

---

## What was rebuilt

### 1) Conservative TVM C++ rebuild

Remote build output root:

- `/home/user/tvm_samegen_safe_20260309/build`

Key outputs:

- `/home/user/tvm_samegen_safe_20260309/build/libtvm.so`
- `/home/user/tvm_samegen_safe_20260309/build/libtvm_runtime.so`
- `/home/user/tvm_samegen_safe_20260309/build/lib/libtvm_ffi.so`

Build characteristics:

- `Release`
- `-O2`
- `-j1`
- `USE_LLVM=OFF`

Why `USE_LLVM=OFF`?
- this TVM 0.24dev tree requires LLVM >= 15
- the Phytium Pi currently has LLVM 10 / 14 only
- so the first goal was runtime/import compatibility, not local LLVM codegen

### 2) Separate safe conda env

New isolated env created:

- `/home/user/anaconda3/envs/tvm310_safe`

This avoids polluting the original broken `tvm310`.

### 3) Rebuilt Python FFI extension

Rebuilt into the safe env:

- `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/core.cpython-310-aarch64-linux-gnu.so`
- `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib/libtvm_ffi.so`
- `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib/libtvm_ffi_testing.so`

This required:

- `TVM_FFI_BUILD_PYTHON_MODULE=ON`
- `Cython` installed into `tvm310_safe`
- `-j1`
- `Release`
- `-O2`

---

## Root cause analysis

### What `gdb` showed

`gdb` on:

```bash
python -c "import tvm_ffi.core"
```

showed SIGILL at:

- `_mi_options_init`
- from: `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/torch/lib/libc10.so`

This means the crash path was reaching PyTorch / libc10 before a usable TVM import could complete.

### Why torch was being pulled in

In `3rdparty/tvm-ffi/python/tvm_ffi/__init__.py` there is an eager import block:

```python
try:
    import torch
except ImportError:
    pass
```

There is also an optional torch dlpack helper loaded by default unless disabled:

```python
if os.environ.get("TVM_FFI_DISABLE_TORCH_C_DLPACK", "0") == "0":
    _LIB = load_torch_c_dlpack_extension()
    patch_torch_cuda_stream_protocol()
```

On this Phytium Pi, the installed torch stack is not safe to import in this context.

---

## Safe-env fix that worked

### Safe-env package override

In `tvm310_safe`:

1. copied python sources from:
   - `/home/user/tvm_samegen_20260307/3rdparty/tvm-ffi/python/tvm_ffi`
2. merged them into:
   - `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi`
3. disabled editable hook:
   - `_apache_tvm_ffi_editable.pth` -> `_apache_tvm_ffi_editable.pth.disabled`
4. patched `tvm_ffi/__init__.py` to remove eager `import torch`

### Runtime env that now works

```bash
TVM_FFI_DISABLE_TORCH_C_DLPACK=1 \
LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build \
TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build \
PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages \
/home/user/anaconda3/envs/tvm310_safe/bin/python -c "import tvm; print(tvm.__version__)"
```

Observed result:

- `0.24.dev0`
- `import tvm` succeeds

---

## Important target-format finding in TVM 0.24dev

Old CLI string target form no longer works here:

```text
llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon
```

This now fails with a message saying CLI string form is no longer supported.

### Working form: JSON / dict target objects

These were successfully accepted in the working safe env:

```python
{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "generic", "mattr": ["+neon"]}
{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "generic", "mattr": ["+neon", "+crypto", "+crc"]}
{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "cortex-a72"}
```

These parse successfully under TVM 0.24.dev0.

Note:
- because the current safe rebuild is `USE_LLVM=OFF`, TVM emits warnings about not parsing Arm target features with LLVM support
- but the target objects themselves are accepted

---

## Practical conclusion

We now have the missing foundation needed to continue the real task:

1. a working TVM 0.24.dev0 import path on the Phytium Pi
2. a reproducible explanation for why the original env failed
3. confirmation that future target experiments should use **JSON/dict targets**, not old CLI strings
4. a safe isolated environment (`tvm310_safe`) for further experiments

---

## Recommended next steps

1. switch the real probe / inference scripts to use `tvm310_safe`
2. normalize target config into JSON/dict form
3. test these first:
   - `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"]}`
   - `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon","+crypto","+crc"]}`
   - `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72"}`
4. if needed, later provision LLVM >= 15 on the Pi for local LLVM-backed canonicalization / build experiments
5. keep the original `tvm310` untouched until the safe env proves stable in end-to-end inference
