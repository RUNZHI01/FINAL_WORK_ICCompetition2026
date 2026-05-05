# Fair Scheme A Pure-Inference Compare Status

- generated_at: 2026-03-11T15:45:00+08:00
- scope: Phytium Pi baseline vs current pure-inference comparison

## Scheme A implementation

- No new runner was required.
- The smallest clean implementation is to drive both variants through `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`, which already measures:
  - `load_module()` once
  - `relax.VirtualMachine(...)` once
  - warmup runs
  - repeated `main()` calls
- Baseline payload compatibility was extended so the runner falls back to `tvm.runtime.ndarray.array(...)` only when `tvm.runtime.tensor` is missing.
- Dedicated remote env for this fair path:
  - `session_bootstrap/config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env`
- Benchmark harness now reports configured baseline/current SHA guards symmetrically.

## Validation

### 1. Local end-to-end Scheme A validation

Local validation was run with both baseline and current on the payload path using the existing local fixture archives.

- report: `session_bootstrap/reports/inference_local_scheme_a_payload_20260311_133729.md`
- baseline median: `701.551 ms`
- current median: `702.862 ms`
- delta (`current - baseline`): `+1.311 ms`
- result: the payload-vs-payload path itself does **not** create a large synthetic speed gap

### 2. Real Phytium Pi fair compare (successful)

Successful report:

- `session_bootstrap/reports/inference_compare_scheme_a_fair_fixed_20260311_154243.md`

Key numbers:

- baseline median: `1829.28 ms`
- current median: `152.846 ms`
- delta (`current - baseline`): `-1676.434 ms`
- improvement: `91.64%`

Artifact identity:

- baseline SHA: `85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849`
- current SHA: `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- both matched their configured expected SHA

## Interpretation

- The large speedup is **not** just a side effect of comparing a legacy baseline script against a payload current script.
- Under the fairer Scheme A design, the new current artifact still shows a very large gain over baseline on the actual Phytium Pi.
- So the earlier `~91.66%` improvement is now materially reinforced rather than weakened.

## Caveat

The pure-inference outputs are not perfectly shape-matched between the two artifacts:

- baseline output shape: `[1, 3, 249, 249]`
- current output shape: `[1, 3, 256, 256]`

This means Scheme A now fairly compares the execution framework (`load + VM init + main()` on both sides), but the two artifacts still represent slightly different compiled output shapes. So the result is much fairer than the earlier mixed-semantics report, yet still should be described as a **payload-symmetric runtime comparison with an output-shape caveat**, not a mathematically perfect like-for-like artifact comparison.

## Conclusion

- Scheme A is now operational on the real Phytium Pi.
- The fairer payload-vs-payload comparison still supports the main conclusion: the new incremental current artifact is dramatically faster than baseline.
- The next refinement, if needed, is not to re-prove the speedup, but to understand and if necessary normalize the `249x249` vs `256x256` output-shape difference before treating this as the final publication-grade apples-to-apples number.
