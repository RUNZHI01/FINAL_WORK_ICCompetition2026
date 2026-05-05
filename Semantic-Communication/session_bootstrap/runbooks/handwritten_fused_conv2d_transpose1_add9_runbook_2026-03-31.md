# Handwritten `fused_conv2d_transpose1_add9` Runbook

Updated: `2026-03-31`

## Purpose

Prepare the first concrete handwritten-candidate lane for `fused_conv2d_transpose1_add9`
without touching trusted current.

Fixed references:

- trusted current mainline stays at `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- current best staging candidate stays at `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- handwritten validation stays in an operator-specific staging archive

Primary evidence:

- `session_bootstrap/runbooks/handwritten_hotspot_tir_neon_path_2026-03-31.md`
- `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`

## Why This Is The Smallest Practical Path

Repo inspection shows:

- `run_phytium_current_safe_staging_validate.sh` ultimately delegates to the incremental wrapper,
  which requires a positive tuning budget.
- a handwritten kernel candidate is better treated as **rebuild-only** plus staging upload, not
  as another tuning round.
- `run_phytium_current_safe_one_shot.sh` already supports that rebuild-only path and can stay
  staging-safe when the remote archive is overridden.
- `run_task_5_1_operator_profile.py` already handles the reprobe side once its trusted env is
  patched to the handwritten staging archive.

So the narrow path is:

1. generate an op-specific scaffold pack
2. patch only the generated env overlays
3. validate through `run_phytium_current_safe_one_shot.sh`
4. reprobe through `run_task_5_1_operator_profile.py`

## Operator Snapshot

From `handwritten_hotspot_candidates_20260331`:

- wave: `Wave 1`
- priority: `1`
- family: `deconv`
- current mean duration: `24275.26 us`
- current runtime share: `14.60%`
- current shapes:
  - `float32[1, 48, 64, 64]`
  - `float32[48, 24, 3, 3]`
  - `float32[1, 24, 1, 1]`
  - `float32[1, 24, 128, 128]`

## Generate The Scaffold Pack

Default output:

```text
./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

Command:

```bash
python3 ./session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_handwritten_scaffold.py
```

Generated pack contents:

- `manual_rebuild.env`
- `manual_validate_inference.env`
- `manual_profile.env`
- `bookkeeping.json`
- `README.md`

## Preferred local schedule-preserving build path

Before any remote/staging step, prefer the new local-only post-DB scheduled swap path:

```bash
python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

Default outputs land under:

```text
./session_bootstrap/tmp/transpose1_post_db_swap_local_build
```

This path now gives first-class local build evidence for:

- best-staging DB recovery
- post-database scheduled `fused_conv2d_transpose1_add9` swap
- swapped full-module local build/export
- artifact SHA / size / adjacent JSON report
- scaffold bookkeeping/template path refresh through the existing sync helper

The wrapper stays local-only and diagnostic-only. Use the underlying
`run_transpose1_post_db_local_build.py` plus
`sync_transpose1_post_db_local_build_result.py` commands separately only when
you need to debug those steps in isolation.

Use the older raw pre-compile hook lane only when you need hook-wiring diagnostics.

## What To Patch

Patch only the generated scaffold files:

1. In `manual_rebuild.env`, add the env toggle or path that enables the handwritten
   implementation for `fused_conv2d_transpose1_add9`.
2. After local rebuild produces `optimized_model.so`, fill
   `INFERENCE_CURRENT_EXPECTED_SHA256` in both generated inference envs.

Do not patch trusted-current env files in place.

## Staging Validation

Recommended remote archive:

```text
/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9
```

Use the generated env files:

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh \
  --rebuild-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_rebuild.env \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_validate_inference.env \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9 \
  --report-id phytium_handwritten_fused_conv2d_transpose1_add9_$(date +%Y%m%d_%H%M%S)
```

This keeps:

- trusted current untouched
- best staging candidate untouched
- handwritten candidate isolated in its own staging lane

Under the current handwritten contract, this one-shot lane is still a
`diagnostic_raw_pre_compile_replacement` path. The best-staging schedule
context is not guaranteed to survive, so payload numbers from this command are
diagnostic only and not performance-comparable evidence.

## Runtime Reprobe

Use the generated profile env:

```bash
python3 ./session_bootstrap/scripts/run_task_5_1_operator_profile.py \
  --run-id profiling_handwritten_fused_conv2d_transpose1_add9_$(date +%Y%m%d_%H%M%S) \
  --hotspot-mode reuse \
  --runtime-mode attempt \
  --trusted-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_profile.env \
  --trusted-variant current \
  --max-inputs 1 \
  --profile-samples 1
```

## Keep / Drop Rules

Under the current raw pre-compile replacement contract, the honest keep / drop
rules are narrower:

- `artifact_sha256_match = true` must still hold
- hook targeting, artifact identity, and basic runtime/profile wiring must still hold
- catastrophic regressions can still justify dropping the candidate as a contract-side diagnostic
- do not use safe-runtime payload or reprobe deltas from this seam as promotion evidence versus `5bd14b9f...`

Promotion-grade performance claims are deferred until a
`schedule_context_preserving_evaluation` path exists.
