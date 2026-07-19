# Transpose1 P4 Local Prep

- generated_at: `2026-03-31T19:31:15+08:00`
- stage: `P4`
- operator: `fused_conv2d_transpose1_add9`
- base state: accepted P2 local working copy on top of git baseline `5aa2c2e`
- scope: local-only preparation for later remote benchmark
- remote activity: `not run`

## Exact Micro-Change

- kept the accepted P2 output-channel tiling unchanged: `c_1 x c_3 = 3 x 8`
- kept the fused-bias `compute_init` / `compute_update` path unchanged
- changed only the outer scheduled-region annotation in the working-copy TIR:
  `pragma_auto_unroll_max_step: 32 -> 64`
- rationale: narrow A72/NEON-plausible unroll-pressure increase without changing loop structure, vector width, or buffer semantics

## Local Build Result

- command:
  `/home/tianxing/.venvs/tvm-ms/bin/python session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4`
- result: `success`
- standalone scheduled task build: `built`
- post-db scheduled swap: `swap_succeeded=true`
- swapped module build: `build_status=built`
- artifact export: `export_status=exported`
- artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4/fused_conv2d_transpose1_add9_post_db_swap.so`
- artifact sha256: `e165fb0316981ef408ffe53c07c8aefe02e9937203877ca679cf29ff6c86ce1d`
- artifact size: `1678648 bytes`
- adjacent JSON report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4/fused_conv2d_transpose1_add9_post_db_swap_report.json`

## Correctness Result

- command:
  `/home/tianxing/.venvs/tvm-ms/bin/python session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py --output-json session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4/fused_conv2d_transpose1_add9_p4_correctness_compare.json`
- reference seed: frozen post-db scheduled reference TIR
- fixed RNG seed: `20260331`
- result gate: `allclose(atol=1e-5, rtol=1e-5)=true`
- exact equal: `false`
- `allclose(atol=1e-6, rtol=1e-6)=false`
- max abs diff: `7.62939453125e-06`
- mean abs diff: `3.7612730352520884e-07`
- nonzero diff count: `309445`
- correctness JSON:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4/fused_conv2d_transpose1_add9_p4_correctness_compare.json`

## Conclusion

The P4 candidate is ready for remote benchmarking. It is a single conservative local micro-tune on top of the accepted P2 state, builds cleanly through the existing post-db scheduled swap path, and matches the frozen scheduled reference within the established local correctness tolerance. No SSH, deployment, or remote benchmark was run in this step.
