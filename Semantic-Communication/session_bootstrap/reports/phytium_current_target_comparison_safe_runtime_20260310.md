# Phytium Pi current-target comparison under safe TVM 0.24.dev0 runtime (2026-03-10)

## Setup

Current artifact candidates were rebuilt locally with:

- local builder TVM: `0.24.dev0`
- mode: rebuild-only (`TUNE_TOTAL_TRIALS=0`)
- existing DB: `./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs`

Remote execution used the importable safe runtime path on the Phytium Pi:

- conda env: `/home/user/anaconda3/envs/tvm310_safe`
- TVM python source: `/home/user/tvm_samegen_20260307/python`
- safe libs: `/home/user/tvm_samegen_safe_20260309/build`
- safe tvm_ffi lib path: `/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib`

Remote benchmark path used real VM execution, not just `load_module` timing:

- script: `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`
- flow: `load_module -> relax.VirtualMachine -> warmup -> repeated main()`
- input shape: `1,32,32,32`
- dtype: `float32`

---

## Short comparison (warmup=1, repeat=5)

| candidate | target | median ms | mean ms | variance ms^2 |
|---|---|---:|---:|---:|
| generic_neon | `generic + neon` | 2502.638 | 2502.728 | 3.385 |
| generic_crypto_crc | `generic + neon + crypto + crc` | 2482.345 | 2482.445 | 0.733 |
| cortex_a72 | `cortex-a72 + neon` | 2481.304 | 2481.349 | 0.151 |

Initial takeaway:
- `generic + neon` is clearly too conservative.
- Both `generic + neon + crypto + crc` and `cortex-a72 + neon` close most of the earlier gap.

---

## Longer comparison (warmup=2, repeat=10)

| candidate | target | median ms | mean ms | min ms | max ms | variance ms^2 |
|---|---|---:|---:|---:|---:|---:|
| generic_crypto_crc | `generic + neon + crypto + crc` | 2493.957 | 2497.641 | 2487.344 | 2543.847 | 243.385 |
| cortex_a72 | `cortex-a72 + neon` | 2489.080 | 2493.248 | 2485.105 | 2511.028 | 70.625 |
| cortex_a72_crypto_crc | `cortex-a72 + neon + crypto + crc` | 2482.095 | 2495.267 | 2471.091 | 2574.413 | 933.920 |

---

## Interpretation

### 1) The old `generic + neon` target was indeed leaving performance on the table

It is materially slower than the more informed candidates, even with the same DB and the same model path.

### 2) Adding more realistic CPU assumptions closes almost all of the previous performance gap

All three better-informed candidates land much closer to the previously observed baseline region (~2477 ms) than the earlier degraded `current` path.

### 3) Best-median vs best-stability tradeoff

- **Best observed median:** `cortex-a72 + neon + crypto + crc` at **2482.095 ms**
- **Best stability / safer default:** `cortex-a72 + neon`
  - lower variance than the other longer-repeat candidates
  - no large outlier like the `2574 ms` seen in the `cortex_a72_crypto_crc` run

### 4) Practical recommendation right now

If we want a **recommended default target for current** that is both strong and relatively stable, use:

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
```

If we want the **best current experimental median** and are willing to investigate stability/jitter further, continue exploring:

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}
```

---

## Bottom line

This round is enough to support the main hypothesis:

> A large part of the earlier `current` performance gap on the Phytium Pi came from target selection being too conservative / not representative enough.

The evidence no longer supports keeping `generic + neon` as the preferred target for the current path.
