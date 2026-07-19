# Handwritten Mean4 v4 Line Integration Identity

- date: `2026-04-06`
- scope: only the `handwritten` route
- goal: verify whether the current `mean4 v4` working copy actually produces a
  **new handwritten-line artifact**, or whether it already collapses to the
  repo's existing handwritten final artifact

## Why This Check Was Necessary

The repo has two different integration stories that are easy to mix up:

1. a legacy three-op Opus probe path that replaces:
   - `variance3`
   - `variance1`
   - `mean4`
2. the real handwritten final route recorded in the Opus report, which keeps:
   - `variance3`
   - `mean4`
   and explicitly drops `variance1`

The new task boundary was also explicit:

- only update the handwritten line
- do not treat a mean4 change as an update to pure MetaSchedule or ACL lines

So the first thing to answer was not "is payload faster?",
but "am I rebuilding the **right handwritten line** at all?"

## What Was Done

### 1. Added an explicit preset switch to `integrate_opus_candidates.py`

The script now has two named bundles:

- `legacy_three_op`
  - `variance3 + variance1 + mean4`
- `opus_final_v3_mean4`
  - `variance3 + mean4`

This makes the historical handwritten final route explicit instead of relying
on the older default bundle that still carried the dropped `variance1` branch.

### 2. Rebuilt the real handwritten final preset with the current `mean4 v4`

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_20260406
```

Observed result:

- rebuilt artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_20260406/optimized_model.so`
- rebuilt SHA-256:
  `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- rebuilt size:
  `1674120`

### 3. Compared it against the repo's existing handwritten final artifact

Reference artifact already recorded in the repo:

- `./session_bootstrap/tmp/opus_final_v3_scope_fix_plus_mean4_fused/optimized_model.so`
- SHA-256:
  `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- size:
  `1674120`

Byte-identity check:

```bash
cmp -s \
  ./session_bootstrap/tmp/opus_final_v3_scope_fix_plus_mean4_fused/optimized_model.so \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_20260406/optimized_model.so
```

Result:

- exit code `0`
- the two files are byte-identical

## Narrow Conclusion

The current `mean4 v4` working copy does **not** produce a new handwritten-line
artifact when integrated through the correct handwritten final preset.

It reproduces the repo's existing handwritten final artifact exactly:

- same operator bundle: `variance3 + mean4`
- same output SHA: `2aa25d2b...e216`
- same size: `1674120`
- same bytes

That means:

1. the current `mean4 v4` state is already baked into the repo's handwritten
   final line
2. there is no new handwritten-line artifact to benchmark from this exact
   `mean4 v4` state alone
3. any future handwritten-line improvement now requires a **new mean4 branch
   beyond the current v4**, not just re-integrating the existing file

## Important Non-Conclusion

This check does **not** say that mean4 is unimportant.

It says something narrower and more actionable:

- the mean4 direction was correct
- but the repo's current handwritten final route had already integrated this
  exact `mean4 v4` branch
- so simply "pushing v4 into handwritten" does not create a new route-level
  result

## Additional Caution

During this session, a legacy three-op rebuild path
(`variance3 + variance1 + mean4`) was also replayed and reproduced the older
`4a5b5dba...b4fa` artifact. That path is **not** the handwritten final route
and should not be used as the handwritten mainline reference.

## Files

- `./session_bootstrap/scripts/integrate_opus_candidates.py`
- `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_20260406/integration_report.json`
- `./session_bootstrap/tmp/opus_final_v3_scope_fix_plus_mean4_fused/optimized_model.so`
- `./session_bootstrap/reports/handwritten_mean4_v4_line_integration_identity_20260406.md`
