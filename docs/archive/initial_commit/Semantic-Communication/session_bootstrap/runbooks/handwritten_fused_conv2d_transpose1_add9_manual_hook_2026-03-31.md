# Handwritten `fused_conv2d_transpose1_add9` Manual Seed Hook

Updated: `2026-03-31`

## Purpose

Add the smallest real handoff between the existing handwritten transpose1
scaffold and a first engineer-owned manual implementation.

This remains staging-only:

- trusted current stays untouched
- current best staging stays pinned at `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- no new remote job is introduced here

## What This Path Now Covers

The existing scaffold already produces:

- `manual_rebuild.env`
- `manual_validate_inference.env`
- `manual_profile.env`
- `bookkeeping.json`

This path now provides the smallest real local handoff:

1. one editable manual implementation seed file for `fused_conv2d_transpose1_add9`
2. one rebuild overlay env that points at that file
3. one local-only build command that records the selected task/TIR snapshot
4. one local-only pre-compile override seam in `rpc_tune.py` that can replace the selected PrimFunc before `compile_relax()`

That is the narrowest useful next step because the rebuild wrappers already
`source "$REBUILD_ENV"` before they assemble the local compile command. The
override remains staging-only because only the local handwritten env enables it.
It is now also explicitly contract-side diagnostic only: the raw pre-compile
replacement seam does not guarantee best-staging schedule context, so this path
is not honest candidate-performance evidence.

## Why This Capture Point

The cleanest repo-native capture point is already in `rpc_tune.py`:

1. `summarize_task_stages()` has already extracted the legalized/fused task set
2. `maybe_apply_handwritten_hook()` runs before `compile_relax()`
3. the handwritten entrypoint therefore sees:
   - selected operator name
   - task-stage summary
   - pre-compile Relax/TIR module
   - local build output dir

That means the first real seed can be recorded and the first checked-in
candidate can be applied from the local build path without adding a generic
subsystem and without launching any remote work.

## Generate The Hook Overlay

Starting from the existing scaffold directory:

```bash
python3 ./session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

This creates:

- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_impl.py`
- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_hook_overlay.env`

## What The Overlay Means

`manual_hook_overlay.env` sources the existing `manual_rebuild.env` and adds only
these handoff variables:

- `TVM_HANDWRITTEN_OP=fused_conv2d_transpose1_add9`
- `TVM_HANDWRITTEN_IMPL_PATH=<repo-native path to the manual seed file>`
- `TVM_HANDWRITTEN_IMPL_ENTRYPOINT=build_manual_impl`
- `TVM_HANDWRITTEN_IMPL_METADATA_FN=describe_placeholder`
- `TVM_HANDWRITTEN_BOOKKEEPING_JSON=<repo-native path to bookkeeping.json>`

No stock wrapper behavior changes yet. The overlay is the contract that
activates the local handwritten path in `rpc_tune.py` and the manual-seed
capture helper below.

## Capture The Local Manual Seed

Run the local-only helper:

```bash
bash ./session_bootstrap/scripts/capture_fused_conv2d_transpose1_add9_manual_seed.sh \
  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

This uses the same `rpc_tune.py` build path as the real rebuild flow, but it
forces:

- `--runner local`
- `--total-trials 0`
- `--op-names fused_conv2d_transpose1_add9`
- no upload
- no inference

After that run, inspect these files beside the editable manual implementation:

- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed.json`
- `./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/fused_conv2d_transpose1_add9_manual_seed_tir.py`

## Current Rebuild Wiring

Keep the rebuild path narrow:

1. source `manual_hook_overlay.env` instead of `manual_rebuild.env`
2. let `rpc_tune.py` import `TVM_HANDWRITTEN_IMPL_PATH`
3. let `build_manual_impl()` return either placeholder capture output or a structured override descriptor
4. let `rpc_tune.py` apply that descriptor before `compile_relax()`
5. continue the normal rebuild flow to `optimized_model.so`

This keeps the handwritten lane staging-only because the only difference is the
local rebuild overlay and the resulting staging archive upload.
Under the tightened contract, any runtime number from this seam must be read as
`non_comparable_diagnostic_only` until a
`schedule_context_preserving_evaluation` path exists.

## Manual Seed File Contract

The generated manual module is now bookkeeping plus seed capture:

- `describe_placeholder()` returns the fixed operator name, reference staging SHA,
  shapes, bookkeeping path, and expected seed artifact paths
- `build_manual_impl(context)` records the selected task row plus any
  discoverable PrimFunc / IRModule script snapshot, then raises
  `NotImplementedError`

Edit that generated `*_manual_impl.py` file, not the checked-in template and not
the generated `*_manual_seed_tir.py` snapshot.

## First Rebuild Command With Local Wiring

With `rpc_tune.py` already honoring `TVM_HANDWRITTEN_IMPL_PATH`, switch only the
rebuild env argument:

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh \
  --rebuild-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_hook_overlay.env \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_validate_inference.env \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9 \
  --report-id phytium_handwritten_fused_conv2d_transpose1_add9_$(date +%Y%m%d_%H%M%S)
```

Nothing else in the staging flow changes, but the resulting `handwritten_hook`
report must now stay labeled diagnostic-only and non-comparable.
