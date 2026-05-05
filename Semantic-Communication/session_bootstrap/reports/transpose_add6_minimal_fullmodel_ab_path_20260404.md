# `fused_conv2d_transpose_add6` Minimal Full-Model A/B Path — 2026-04-04

- date: `2026-04-04`
- operator: `fused_conv2d_transpose_add6`
- goal: find the smallest executable path that is closer to whole-model payload / reconstruction A/B, without touching Trusted Current
- status: `implemented as repo helpers; remote execution still depends on the board session`

## What Was Read First

This conclusion is based on the exact files requested in the task:

- `session_bootstrap/reports/opus_optimization_breakthrough_plan_20260403.md`
- `session_bootstrap/reports/transpose_add6_acl_vs_tvm_standalone_ab_20260404.md`
- `session_bootstrap/scripts/integrate_opus_candidates.py`
- existing `transpose_add6` build / benchmark helpers under `session_bootstrap/scripts/`

## Narrow Conclusion

The smallest executable path that is genuinely closer to whole-model A/B is:

1. `post-db scheduled PrimFunc swap`
2. `relax.build(swapped_mod)` to rebuild the full model `.so`
3. upload the rebuilt artifact into a dedicated remote staging archive
4. run existing payload A/B compare against baseline
5. run existing real-reconstruction A/B compare against baseline

In repo terms, the right seam is **not** the older raw pre-compile handwritten hook.

The right seam is the existing local schedule-preserving path implemented by:

- `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`
- `session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py`

That path already does the important thing:

- first apply `MetaScheduleApplyDatabase`
- then replace only `fused_conv2d_transpose_add6`
- then rebuild the **full module**

So this is the smallest path that preserves the rest of the model context while changing only this operator.

## Why `integrate_opus_candidates.py` Is Not The Right Path Here

`session_bootstrap/scripts/integrate_opus_candidates.py` is not the minimal trustworthy path for this task because:

- it currently does not target `fused_conv2d_transpose_add6`
- it replaces functions before the final full-model compile path, not through the checked `post_database_scheduled_primfunc_swap` seam
- it is aligned with variance / mean candidates, not the existing transpose_add6 scheduled-form lane

For `transpose_add6`, the checked-in lane that is already closest to whole-model evaluation is the post-db scheduled swap path.

## What Was Implemented

Two repo changes were added to make this path usable as a real A/B lane:

### 1. Upload-only staging for the transpose_add6 payload helper

Updated:

- `session_bootstrap/scripts/run_transpose_add6_remote_payload_benchmark.sh`

New behavior:

- supports `--upload-only`
- uses byte-stable base64 upload instead of raw `cat > remote_path`
- verifies remote `sha256` and file size before continuing

This lets payload A/B and reconstruction A/B share the same staged candidate archive.

### 2. One narrow orchestrator for the full-model A/B path

Added:

- `session_bootstrap/scripts/run_transpose_add6_minimal_fullmodel_ab.py`

This wrapper only wires together existing helpers:

- local full-model rebuild:
  `run_transpose_add6_post_db_local_build.py`
- env generation:
  `prepare_handwritten_fused_conv2d_transpose_add6_env.py`
- dedicated remote upload:
  `run_transpose_add6_remote_payload_benchmark.sh --upload-only`
- payload A/B:
  `run_inference_benchmark.sh`
- reconstruction A/B:
  `run_inference_benchmark.sh`

It does **not** invent a new runtime lane.

## Exact Minimal Commands

### Local prep only

Use this when you want the artifact, env files, and exact next commands without touching the board:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_minimal_fullmodel_ab.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py \
  --report-prefix transpose_add6_v1_fullmodel_ab_$(date +%Y%m%d_%H%M%S) \
  --prepare-only
```

### Full payload + reconstruction A/B

Use this when the board session is available:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_minimal_fullmodel_ab.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py \
  --report-prefix transpose_add6_v1_fullmodel_ab_$(date +%Y%m%d_%H%M%S)
```

### Swap to the v2 candidate instead

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_minimal_fullmodel_ab.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --report-prefix transpose_add6_v2_fullmodel_ab_$(date +%Y%m%d_%H%M%S)
```

## Smallest Current Blocker For A True ACL Injection

The blocker is now precise:

- the repo has a valid **TVM PrimFunc replacement seam**
- the repo does **not** have a checked-in **ACL extern / packed-func bridge** that can replace `fused_conv2d_transpose_add6` inside the rebuilt full model while keeping the rest of the model ABI intact

Said differently:

- current seam can swap `TVM PrimFunc -> TVM PrimFunc`
- current seam cannot yet swap `TVM PrimFunc -> ACL kernel call`

So the next real blocker is **not** “how do we rebuild the full model around transpose_add6?”

That part is now scripted.

The next blocker is:

- define one full-model-safe extern call contract for `fused_conv2d_transpose_add6`
- teach the build path to emit that extern call instead of a normal PrimFunc body
- keep output shape / dtype / parameter ABI identical to the existing full model

## Recommended Next Step

Do the next board-backed run through the new wrapper first.

If that A/B path is stable, then the only justified follow-up for ACL is:

1. keep `transpose_add6` as the only replacement target
2. prototype a single extern-backed replacement just for this operator
3. reuse the same `run_transpose_add6_minimal_fullmodel_ab.py` path to evaluate the resulting full-model artifact

Until that extern bridge exists, the current minimal trustworthy path is the new post-db full-model rebuild + staged A/B route above.
