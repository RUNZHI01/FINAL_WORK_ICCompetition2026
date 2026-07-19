# Handwritten Hotspot TIR NEON Path

Updated: `2026-03-31`

## Purpose

Prepare the next manual-optimization step from the current best staging candidate without
touching trusted current.

Fixed baselines:

- trusted current mainline stays at `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- current best staging candidate stays at `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- all manual experiments stay staging-only

Primary evidence:

- `session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- `session_bootstrap/reports/runtime_shifted_top3_targeted_search_diagnosis_20260330.md`
- `session_bootstrap/reports/runtime_joint_top5_targeted_staging_search_diagnosis_20260330.md`
- `session_bootstrap/reports/runtime_joint_top6_targeted_staging_search_diagnosis_20260331.md`
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`

## What The Evidence Says

- Blind same-structure retargeting is no longer enough. `runtime-top2` and `runtime-shifted-top3`
  both produced severe integrated regressions, while `joint-top6` is only healthy once the
  hotspot set is protected together.
- `joint-top6` is the current best integrated staging candidate at `159.943 ms`, but it still
  leaves a stable residual hotspot set in the runtime reprobe.
- The repo already warns not to choose `7.1` manual TIR targets from stage-weight hotspot
  extraction alone. The handwritten path must therefore start from the runtime reprobe of
  `5bd14b9f...`, not from `reshape*`-heavy task-stage rankings.

## Current Handwritten Candidate Order

Wave 1: conv and deconv kernels that remain top runtime hotspots after `joint-top6`.

1. `fused_conv2d_transpose1_add9`
2. `fused_conv2d_transpose2_add12`
3. `fused_conv2d_transpose_add6`
4. `fused_conv2d3_add15`

Why this wave:

- these ops still anchor the current curated runtime top list in
  `profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010`
- they remained important across multiple retarget rounds, so the next non-blind lever is
  handwritten TIR plus NEON rather than another large target-set shuffle
- they are regular compute kernels with plausible upside from explicit tiling, vectorization,
  and fused epilogue control

Wave 2: newly exposed norm and reduction kernels once the conv/deconv set is stabilized.

1. `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
2. `fused_variance4_add13_tir_sqrt4`
3. `fused_mean3_subtract3_divide3_multiply3_add11_relu2`
4. `fused_variance3_add10_tir_sqrt3`

Why this wave:

- these ops move into the curated top list only after `joint-top6` compresses the earlier
  conv/deconv hotspots
- this is the right point to try handwritten TIR on reductions and vector math, but only after
  one Wave-1 kernel is understood

Monitor only for now:

- `fused_conv2d_add2`: important in joint-top5 reprobe, but no longer dominant in the best
  `joint-top6` candidate
- `fused_conv2d2_add2`: still visible in raw aggregated calls, but already included in the
  `joint-top6` tuning set and no longer promoted by the diagnosis shortlist
- `fused_variance1_add3_tir_sqrt1` and `fused_mean1_subtract1_divide1_multiply1_add4`:
  still visible in raw aggregated calls, but not yet strong enough to outrank the curated
  runtime shortlist for handwritten work

For the checked-in evidence pack, use:

- `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.json`

## Minimal Workflow

1. Refresh the candidate pack from the existing reprobe evidence.

```bash
python3 ./session_bootstrap/scripts/prepare_handwritten_hotspot_candidates.py
```

2. Keep the auto-tuned control line fixed.

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top6_refine_staging_search.sh
```

3. Work exactly one handwritten candidate at a time, starting at Wave 1 priority 1.

- do not retarget the whole hotspot set again
- do not overwrite trusted current
- do not batch multiple handwritten kernels into one first-pass validation

4. Validate every handwritten attempt in a separate staging archive.

Recommended handwritten staging archive:

```text
/home/user/Downloads/jscc-test/jscc_staging_handwritten
```

Validation template:

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_staging_validate.sh \
  --rebuild-env <manual_overlay.env> \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten \
  --report-id phytium_handwritten_<op>_$(date +%Y%m%d_%H%M%S)
```

5. Re-profile the resulting artifact before keeping it alive.

Use the existing runtime profile wrapper with a staging env derived from the handwritten archive.
As the baseline template, start from:

- `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/trusted_env_snapshot.env`

Then update only the archive path and expected SHA for the handwritten candidate before running:

```bash
python3 ./session_bootstrap/scripts/run_task_5_1_operator_profile.py \
  --run-id profiling_handwritten_candidate_$(date +%Y%m%d_%H%M%S) \
  --hotspot-mode reuse \
  --runtime-mode attempt \
  --trusted-env <handwritten_profile.env> \
  --trusted-variant current \
  --max-inputs 1 \
  --profile-samples 1
```

## Conservative Decision Rules

- Keep trusted current unchanged.
- Use `5bd14b9f...` as the fixed staging comparison point.
- A handwritten candidate only survives if:
  - `artifact_sha256_match = true`
  - the targeted op gets materially better in the reprobe
  - safe runtime payload does not regress versus the current best staging candidate
  - the reprobe does not create a new dominant hotspot snapback
- If any of those checks fail, archive the report and stop. Do not roll the failure into
  trusted current or into the best staging candidate lane.

## Scope Guard

This runbook prepares the manual path only. It does not introduce a new tuning subsystem,
does not start long remote jobs by itself, and does not redefine the current promotion gate.
