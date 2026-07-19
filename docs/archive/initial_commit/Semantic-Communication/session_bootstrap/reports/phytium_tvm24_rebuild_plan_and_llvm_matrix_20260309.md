# Phytium Pi TVM 0.24dev rebuild plan + LLVM-supported target matrix (2026-03-09)

## Goal

Make the remote `tvm310` / TVM `0.24.dev0` environment on the Phytium Pi:

1. reproducible,
2. importable without `Illegal instruction`,
3. explicit about what target assumptions are and are not supported by the Pi-side LLVM toolchain.

---

## Ground truth from the Phytium Pi

### CPU / ISA evidence

Remote evidence collected from `uname -m`, `lscpu`, and `/proc/cpuinfo`:

- ISA / userspace arch: `aarch64`
- CPU count: `4`
- Mixed CPU parts observed:
  - `CPU part: 0x303`
  - `CPU part: 0x664`
- Reported features:
  - `fp`
  - `asimd`
  - `aes`
  - `pmull`
  - `sha1`
  - `sha2`
  - `crc32`
  - `cpuid`
  - `sha3`
  - `sha512`

Interpretation:
- This is not a clean single-microarchitecture board with a vendor-specific LLVM `mcpu` name.
- Treating the board as generic AArch64 plus confirmed ISA features is safer than guessing a Phytium-specific `mcpu` that LLVM may not support.

---

## Pi-side LLVM reality

### Installed LLVM versions on the Pi

Observed on the Pi:

- `/usr/lib/llvm-10`
- `/usr/lib/llvm-14`
- no LLVM 15+ installation found

### LLVM 14 AArch64 support check

Using Pi-side `llc` from LLVM 14:

- command family used:
  - `/usr/lib/llvm-14/bin/llc -march=aarch64 -mcpu=help`
  - `/usr/lib/llvm-14/bin/llc -march=aarch64 -mattr=help`

#### Supported `mcpu` examples confirmed by LLVM 14

- `generic`
- `cortex-a53`
- `cortex-a55`
- `cortex-a57`
- `cortex-a72`
- `cortex-a76`
- `neoverse-n1`
- `neoverse-n2`
- `tsv110`

#### Not present in LLVM 14 `mcpu` list

- `phytium`
- `ft2000plus`
- `ftc664`
- `ftc310`

Conclusion:
- We should **not** treat Phytium-specific `mcpu` strings as authoritative just because TVM can parse a string.
- For this machine, target experiments should be based on **LLVM-supported** AArch64 `mcpu/mattr` combinations.

#### Relevant LLVM 14 AArch64 feature names observed

- `neon`
- `aes`
- `crypto`
- `crc`
- `sha2`
- `sha3`
- plus many higher-level optional features not yet justified for this board

---

## TVM 0.24dev / tvm310 environment facts

Remote `tvm310` conda env facts already confirmed:

- Python path: `/home/user/anaconda3/envs/tvm310/bin/python`
- Site package points to editable TVM tree via:
  - `/home/user/anaconda3/envs/tvm310/lib/python3.10/site-packages/zzz_tvm_samegen_20260307.pth`
  - content: `/home/user/tvm_samegen_20260307/python`
- Installed package metadata:
  - `apache_tvm_ffi-0.24.dev0.dist-info`

Current blocker before rebuild:

- `import tvm` from `tvm310` crashes with `Illegal instruction`

---

## Conservative rebuild strategy

### Why not use LLVM in the first rebuild?

The remote TVM 0.24dev source currently rejects LLVM 14 during CMake configure with:

> `TVM requires LLVM 15.0 or higher.`

Since the Pi currently only has LLVM 10 and 14, the first safe rebuild branch is:

- `USE_LLVM=OFF`
- `Release`
- `-O2`
- `-j1`
- no `-march=native`
- no `-mcpu=native`
- no aggressive ISA assumptions

This branch is still useful because the immediate blocker is **runtime/import stability**, not on-device model compilation.

### Exact repo-side rebuild entrypoint

Created script:

- `session_bootstrap/scripts/remote_rebuild_tvm310_conservative.sh`

### Current default rebuild config encoded in the script

- remote source: `/home/user/tvm_samegen_20260307`
- remote root: `/home/user/tvm_samegen_safe_20260309`
- remote build dir: `/home/user/tvm_samegen_safe_20260309/build`
- remote install dir: `/home/user/tvm_samegen_safe_20260309/install`
- jobs: `1` only
- CMake build type: `Release`
- C flags: `-O2`
- CXX flags: `-O2`
- feature flags:
  - `USE_LLVM=OFF` fallback when no supported LLVM>=15 is available
  - `USE_RPC=ON`
  - `USE_THREADS=ON`
  - `USE_OPENMP=OFF`
  - `USE_SORT=ON`
  - `USE_RANDOM=ON`
  - `USE_LIBBACKTRACE=OFF`
  - `USE_CCACHE=OFF`
  - `USE_CPP_RPC=OFF`
  - `USE_CPP_RTVM=OFF`
  - `USE_LIBTORCH=OFF`
  - `USE_CUDA=OFF`
  - `USE_METAL=OFF`
  - `USE_VULKAN=OFF`

---

## LLVM-supported target candidates worth testing after runtime/import is fixed

### Candidate A: current conservative control

```text
llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon
```

### Candidate B: generic + confirmed ISA features

```text
llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
```

Rationale:
- board evidence confirms `asimd/aes/pmull/sha1/sha2/crc32/sha3/sha512`
- LLVM feature vocabulary exposes `neon/crypto/crc/sha2/sha3`
- this is still safer than guessing a non-standard Phytium `mcpu`

### Candidate C: surrogate microarchitecture

```text
llvm -mtriple=aarch64-linux-gnu -mcpu=cortex-a72
```

Rationale:
- supported by LLVM 14 on the Pi
- commonly used as a surrogate when vendor-specific ARM cores have no direct `mcpu` name

---

## Current execution status

- LLVM-supported `mcpu/mattr` matrix: **confirmed enough to guide next tests**
- remote conservative rebuild script: **written**
- first rebuild attempt with LLVM 14: **failed by design constraint** (`TVM requires LLVM >= 15`)
- fallback conservative rebuild (`USE_LLVM=OFF`, `Release`, `-O2`, `-j1`): **completed successfully**
- produced libraries include:
  - `/home/user/tvm_samegen_safe_20260309/build/libtvm.so`
  - `/home/user/tvm_samegen_safe_20260309/build/libtvm_runtime.so`
  - `/home/user/tvm_samegen_safe_20260309/build/lib/libtvm_ffi.so`

### Follow-up finding: the remaining SIGILL was not in TVM core

After the conservative rebuild completed, `tvm310` still crashed on import. GDB root-cause showed:

- signal: `SIGILL`
- crashing symbol: `_mi_options_init`
- crashing shared library:
  - `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/torch/lib/libc10.so`

Interpretation:
- the remaining `Illegal instruction` was **not primarily from newly rebuilt TVM core**
- it came from the import chain pulling in a broken/incompatible `torch` binary on the Pi
- this happened early enough to kill `import tvm_ffi.core`

### Safe-env remediation that worked

A new isolated env was created:

- `/home/user/anaconda3/envs/tvm310_safe`

Then:

1. `tvm_ffi` Python extension was rebuilt into the safe env with:
   - `TVM_FFI_BUILD_PYTHON_MODULE=ON`
   - `-O2`
   - `-j1`
2. the incompatible `torch` package tree was moved out of the import path inside `tvm310_safe`
3. import was re-tested with:
   - safe-env `tvm_ffi` package
   - rebuilt safe `libtvm/libtvm_runtime`
   - source-tree `python/tvm`

### Result after safe-env remediation

With `torch` removed from the safe env import path:

- `import tvm` in `tvm310_safe`: **works**
- version: `0.24.dev0`

This is the first confirmed Pi-side importable TVM 0.24dev stack in this investigation.

### Artifact compatibility result under the safe 0.24dev stack

Using:

- `LD_LIBRARY_PATH=<safe-env tvm_ffi lib>:<safe build dir>`
- `TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build`
- `PYTHONPATH=/home/user/tvm_samegen_20260307/python:<safe-env site-packages>`

Results:

- `current` artifact:
  - path: `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
  - `tvm.runtime.load_module(...)`: works
  - `relax.VirtualMachine(mod, tvm.cpu(0))`: **works**
- `baseline` artifact:
  - path: `/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so`
  - still fails with old-style compatibility mismatch (`vm_load_executable` path)

Interpretation:
- old compat runtime matched `baseline` but not `current`
- new safe 0.24dev runtime matches `current`
- the runtime incompatibility split between baseline/current is now directly demonstrated on the Pi

### TVM 0.24 target API note

The old CLI-style target string form is no longer accepted in this environment.
For example, this fails:

```text
llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon
```

The accepted form is JSON/dict, e.g.:

```python
{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "generic", "mattr": ["+neon"], "num-cores": 4}
```

Confirmed accepted candidates in the safe 0.24dev env:

- `{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "generic", "mattr": ["+neon"], "num-cores": 4}`
- `{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "generic", "mattr": ["+neon", "+crypto", "+crc"], "num-cores": 4}`
- `{"kind": "llvm", "mtriple": "aarch64-linux-gnu", "mcpu": "cortex-a72", "mattr": ["+neon"], "num-cores": 4}`

These still emit warnings when canonicalizing Arm features because this safe runtime was built with `USE_LLVM=OFF`, but target objects are created successfully.

---

## Most important practical conclusion right now

There are **three separate truths** we need to respect:

1. **Target-selection truth**:
   - the Pi-side LLVM does **not** advertise `phytium` / `ft2000plus` as standard AArch64 `mcpu` choices.
   - target experiments should therefore start from LLVM-supported candidates such as `generic + attrs` and `cortex-a72`.

2. **Runtime-stability truth**:
   - before target quality can be evaluated fairly, the remote TVM 0.24dev stack had to become importable and runtime-stable on the Pi.
   - that goal is now met via the safe env path.

3. **Dependency-contamination truth**:
   - the fatal Pi-side `SIGILL` was not only about TVM build flags.
   - an incompatible `torch/libc10.so` in the env import path could kill `tvm_ffi` import before TVM proper was even usable.
