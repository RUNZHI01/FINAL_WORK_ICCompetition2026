# Checked-in seed: `fused_conv2d_transpose1_add9`

This directory is the first repo-native handoff after the local-only
manual seed capture. It keeps the operator-specific editing surface in
the repo without touching trusted current or launching any remote work.

## Files

- `fused_conv2d_transpose1_add9_manual_candidate.py`: repo-native handwritten-hook entrypoint for this operator; it exposes the checked-in candidate v0 through the local/staging pre-compile override contract.
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`: repo-native local-only post-db scheduled-swap entrypoint for the checked-in scheduled-form v1 working copy.
- `fused_conv2d_transpose1_add9_editable_seed_tir.py`: editable operator TIR extracted from the local MetaSchedule task log.
- `fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py`: schedule-preserving reference/edit seed recovered from the post-db full-module path.
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`: editable scheduled-form v1 working copy cloned from the checked-in post-db scheduled reference seed, now carrying the first narrow local operator-side v1 edit.
- `seed_manifest.json`: trimmed seed context copied from the captured seed JSON.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for the scheduled-form reference/edit seed.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: small manifest for the editable scheduled-form v1 working copy.
- `README.md`: short editing runbook.

## Why this exists

- the captured pre-compile seed JSON at `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed.json` is real, but its paired seed snapshot only shows the Relax callsite under `main`
- the local task log at `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_seed_capture/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_0_fused_conv2d_transpose1_add9.log` contains the actual `fused_conv2d_transpose1_add9` TIR workload
- this package checks that workload into the repo so the first manual edits are not trapped under `tmp/`

## Refresh from the latest local capture

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_checked_in_seed.py
```

The helper reads:
- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed.json`
- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed_tir.py`
- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_seed_capture/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_0_fused_conv2d_transpose1_add9.log`

It refuses to overwrite this directory unless `--allow-overwrite` is passed.

## Refresh the scheduled-form reference seed

When the next operator-side iteration needs a schedule-preserving starting
point, refresh the checked-in post-db scheduled reference seed instead of the
older raw pre-compile seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_post_db_scheduled_seed.py \
  --allow-overwrite
```

The helper reuses the local post-db schedule-preserving seam and writes:
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json`

This handoff is still local-only and diagnostic-only. It gives a more honest
reference/edit seed for the next handwritten pass, but it does not by itself
justify runtime or performance claims.

## Refresh the scheduled-form v1 working copy

Once the checked-in scheduled reference seed is current, derive the editable
scheduled-form v1 working copy from it with this narrow local-only helper:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py \
  --allow-overwrite
```

The helper reads the checked-in scheduled reference seed and writes:
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`

Keep the scheduled reference seed frozen for backtracking and re-refresh, and
make operator-side v1 edits in the working copy instead. This working-copy
handoff is still local-only, diagnostic-only, and not hook-facing.

## Current checked-in v1 edit

As of `2026-03-31`, the checked-in scheduled-form v1 working copy applies one
small operator-side change while keeping the post-db scheduled reference seed
frozen:

- bias is written directly into `T_add_intermediate` inside the scheduled
  `compute_init` block
- the scheduled `compute_update` block now accumulates into that final output
  buffer
- the full-size `compute_intermediate` allocation and the trailing `T_add` pass
  are removed

This is still a local-only, diagnostic-only edit surface. It is not hook-facing
and it is not performance evidence by itself.

## Current follow-up candidates

Later checked-in follow-ups keep the same post-db scheduled swap seam and only
change the working-copy TIR they point at:

- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py`:
  current board-proven transpose1 baseline, remote median `156.785 ms`
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py`:
  failed local proof branch that tried to carry the seam by rewriting shared
  `data_pad` rows in place
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v10.py`:
  current local-proof follow-up that keeps the winning `v7` locality family but
  routes the second `h_1` stripe through a disjoint consumer-facing current
  buffer instead of shared `data_pad` writeback; the first full local proof on
  `2026-04-06` still failed exactness against `v7`, so this branch is not ready
  for board benchmarking

The corresponding checked-in working-copy files are:

- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py`
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy_tir.py`
- `fused_conv2d_transpose1_add9_scheduled_form_candidate_v10_working_copy_tir.py`

## Hook-facing candidate path

The existing `rpc_tune.py` handwritten hook can point at `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py`
today. That module is deliberately honest:

- it keeps the checked-in editable seed and checked-in candidate v0 side by side in this directory
- it returns a local/staging-only override descriptor for candidate v0
- `rpc_tune.py` now consumes that descriptor before `compile_relax()`, so the handwritten hook can replace the selected PrimFunc without touching trusted current
- the current contract is explicitly diagnostic-only: it is a raw pre-compile replacement path with `schedule_context_guarantee=not_guaranteed`
- runtime or reprobe numbers from this seam are `non_comparable_diagnostic_only`, not candidate-performance evidence
- a future `schedule_context_preserving_evaluation` path is still required before another handwritten candidate can be judged on performance

## Edit toward candidate v0

1. Start from `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_editable_seed_tir.py`.
2. Keep `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py` as the hook-facing module path.
3. Keep the buffer contract stable:
   input `(1, 48, 64, 64)`, weight `(48, 24, 3, 3)`, bias `(1, 24, 1, 1)`, output `(1, 24, 128, 128)`.
4. Treat `data_dilate`, `data_pad`, `kernel_transform`, `compute`, and `T_add` as the honest baseline stages from the captured workload.
5. First manual edits should stay narrow: reduce intermediate traffic, fuse cheap transforms when possible, and only then try tiling/vectorization around `compute`.

## Hook wiring diagnostic through the existing manual hook

Regenerate the overlay so it points at the checked-in candidate module:

```bash
python3 ./session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold \
  --manual-impl-path ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py \
  --allow-overwrite
```

Then exercise the existing hook with no remote work:

```bash
bash ./session_bootstrap/scripts/capture_fused_conv2d_transpose1_add9_manual_seed.sh \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold \
  --allow-existing-output
```

That proves the hook is loading the checked-in candidate path. It does not
yet prove a performance change. It proves the local handwritten path reaches
the checked-in candidate v0 and applies it at the pre-compile integration point.
Treat any payload/runtime number from this path as diagnostic-only until a
schedule-context-preserving evaluation contract exists.

## Preferred local schedule-preserving build path

Once hook wiring is confirmed and the scaffold pack exists, prefer this
one-shot local-only path before any future remote/staging validation:

```bash
python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

This wrapper drives the checked-in best-staging task-summary / DB defaults,
performs the post-DB scheduled `fused_conv2d_transpose1_add9` swap, syncs the
result back into the scaffold bookkeeping pack, and prints a concise final JSON
summary with the local artifact/report/SHA plus scaffold bookkeeping/template
paths. By default this path now consumes
`./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`,
which in turn points at the checked-in scheduled-form v1 working copy. The
underlying `run_transpose1_post_db_local_build.py` and
`sync_transpose1_post_db_local_build_result.py` commands remain available if you
need to split those diagnostics.

Default build outputs still land under:

```text
./session_bootstrap/tmp/transpose1_post_db_swap_local_build
```

This is still build-level diagnostic evidence only, but it preserves the best
staging schedule context much more honestly than the older raw pre-compile hook
lane.

For continued `v1` work, keep the scheduled reference seed as the frozen source
of truth, refresh the scheduled-form v1 working copy from it when needed, and
re-apply or refine edits only in the working copy. Keep the older raw
pre-compile seed only for backtracking or hook-wiring comparison.

## Staging lane after a real override exists

Reuse the same `manual_hook_overlay.env` with the existing staging-safe
one-shot and profile commands from the transpose1 handwritten runbooks. Do not
overwrite trusted current while this checked-in candidate is still seed-derived.
Until a `schedule_context_preserving_evaluation` path exists, treat those
one-shot / reprobe outputs as contract-side diagnostics rather than
performance-comparable evidence.

## Source reminder

The original captured pre-compile snapshot is still at `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed_tir.py` if you need the full Relax callsite context.
