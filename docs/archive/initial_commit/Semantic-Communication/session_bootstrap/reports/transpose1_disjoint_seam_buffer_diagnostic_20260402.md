# `fused_conv2d_transpose1_add9` Disjoint Seam-Buffer Diagnostic

Date: `2026-04-02`

## Scope

Local-only follow-up on top of the accepted transpose1 `v7` baseline.

- operator: `fused_conv2d_transpose1_add9`
- kept baseline: checked-in `v7`
- no SSH/scp/remote board work
- no runtime/performance claim
- no checked-in `v9` candidate created
- all existing transpose1 candidate files were left intact

## Local Proof

The scratch proof rebuilt the **second `h_1` stripe** in a **disjoint**
consumer-facing buffer, not by relying on skipped writes or by writing the
carried rows back into the shared `data_pad` buffer.

Construction per `dc_0` slice and width tile:

- seam buffer shape: `4 x 2 x 10`
- second-stripe working buffer shape: `4 x 34 x 10`
- working-buffer rows `0/1`: copied from the explicit seam buffer
- working-buffer rows `2..33`: freshly materialized with current-stripe `v7`
  semantics

Compared against `v7` before `compute_update` across:

- `h_base = 0, 64`
- all `16` staged width tiles
- all `12` `dc_0` slices
- total cases: `384`

## Exact Result

The disjoint current-stripe proof is **bit-exact** versus `v7` before
`compute_update`.

- full second-stripe staged-buffer compare:
  `nonzero_diff_count = 0`, `max_abs_diff = 0.0`
- carried seam rows `0/1` vs `v7` current-stripe rows `0/1`:
  `max_abs_diff = 0.0`
- focused global `data_pad` rows:
  `32, 33, 34, 35, 96, 97, 98, 99`
  all had `nonzero_diff_count = 0` and `max_abs_diff = 0.0`
- each focused row covered `7680` compared elements
  (`16` width tiles × `48` channels × `10` staged columns)

## Contrast With Shared-Writeback Scratch

As a sanity check, the already-present local shared-`data_pad` writeback scratch
file was compared against `v7` and still was **not** exact end-to-end:

- `nonzero_diff_count = 12288`
- `max_abs_diff = 18.116403579711914`

So the clean result came from the **disjoint** second-stripe materialization
proof, not from writing carried rows back into the shared staged buffer.

## Conclusion

Result: **disjoint explicit seam buffer restores exactness and is worth
promoting**

Concrete reading of that result:

- producer-only overlap carry should not be the preferred next branch
- the local evidence now supports an explicit consumer-facing seam path
- the promotion target should be a real local-only candidate that keeps the
  second `h_1` stripe materialization disjoint all the way to the consumer read,
  instead of reintroducing shared-buffer carry semantics

## Recommended Next Step

Build one real local-only follow-up candidate from `v7` that:

1. keeps the `dc_0`-sliced `v7` locality structure intact
2. materializes the second `h_1` stripe into a **disjoint consumer buffer**
3. feeds `compute_update` from that disjoint current-stripe buffer for `h_1 == 1`
4. passes a full local correctness compare against `v7`

Only if that local correctness proof is clean should a checked-in `v9`
candidate be considered.

## Files Changed

- `./session_bootstrap/scripts/diagnose_transpose1_disjoint_seam_buffer.py`
- `./session_bootstrap/reports/transpose1_disjoint_seam_buffer_diagnostic_20260402.md`

## Commands Run

```bash
python3 -m py_compile session_bootstrap/scripts/diagnose_transpose1_disjoint_seam_buffer.py
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/diagnose_transpose1_disjoint_seam_buffer.py \
  --output-json ./session_bootstrap/tmp/transpose1_disjoint_seam_buffer_diagnostic_20260402.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v9_vs_v7_correctness_20260402/check_report.json
```
