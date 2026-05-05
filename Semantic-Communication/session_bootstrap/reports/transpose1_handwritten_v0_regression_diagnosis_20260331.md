# Transpose1 Handwritten V0 Regression Diagnosis

- operator: `fused_conv2d_transpose1_add9`
- validation report: `session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.md`
- reference staging artifact: `session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`
- chosen next step: `B` (`handwritten replacement contract / targeting semantics`)
- disposition: `v0 = drop / not for reprobe`

## Diagnosis

The most likely cause is not a wrong-target replacement. The handwritten hook hit the intended PrimFunc, but it does so in the current `pre_compile` seam, after the tuning database is prepared and before `compile_relax()` replaces the selected global with the checked-in source TIR.

That matters because v0 is structurally different from the tuned seed:

- v0 removes `compute_intermediate`
- v0 removes the trailing `T_add` block
- v0 keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized

The copied MetaSchedule database still belongs to the best staging artifact, whose tuned traces were learned on the old block graph. Local artifact checks show the mismatch directly:

- reference staging artifact: `sha256=5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`, `size=1678424`, `run_median_ms=159.943`
- handwritten v0 artifact: `sha256=b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28`, `size=1680408`, `run_median_ms=655.693`
- warm-start DB base workloads stayed as the first 9 hashes, but the handwritten build appended 27 new workloads (`9 -> 36`) while tuning records still referenced only workload ids `0..8`

Most likely interpretation: the pre-compile replacement changed the transpose1 workload enough that the current best staging tuning records no longer matched the handwritten candidate, so the candidate was compiled without the history-best schedule context that made the staging artifact fast. Since v0 only removes one output-sized intermediate pass and does not add a new low-level schedule, the integrated result fell onto a much slower path.

## Why This Is Not A

This result does not justify another small TIR-side candidate yet. A v1 that only folds `kernel_transform` or simplifies one more buffer path would still be measured through the same pre-compile seam and would still be confounded by schedule-cache misses. That would not tell us whether the operator change is actually good.

## Recommended Next Step

Choose `B`: fix the handwritten replacement contract / targeting semantics first.

Concrete direction:

- keep the handwritten path scoped to `fused_conv2d_transpose1_add9`
- preserve the current best staging schedule context when evaluating a structural handwritten candidate
- only return to operator-side v1 after the evaluation path can distinguish "candidate got slower" from "candidate lost MetaSchedule reuse"

In practice that means moving away from the current pure `pre_compile` raw-PrimFunc replacement for performance evaluation, or adding a contract that can replace against the post-history-best/scheduled form instead of the untuned seed form.
