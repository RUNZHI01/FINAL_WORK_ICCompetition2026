# `fused_variance4_add13_tir_sqrt4` v13 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v12` exact-preserving `.data`-level volatile one-element local round-trip intact
- replace only the redundant hardcoded unit indices on `lv335_red` accesses inside the folded `T_multiply_local` read region and subtract expression with the already-remapped unit-extent axes `v_ax2` and `v_ax3`

Rationale: this is the next narrow source-level cleanup after `v12`, because those `T.int64(0), T.int64(0)` indices were semantically redundant under the unit-extent axes already present in the same block. This tests whether the exact-preserving local round-trip can survive one more purely syntactic cleanup without revisiting already-answered volatility or handle questions.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v13_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13_working_copy.py`
- `./session_bootstrap/reports/variance4_v13_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v13
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v13_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `62 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v13/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v13/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v13_correctness_check.json`

## Next Step

If this lane continues, the next exactness-aware step should stop targeting already-proven syntactic redundancies and instead run a focused diagnostic to identify whether any remaining source-level differences above `v13` still survive into exported local artifact identity. If not, the variance4 line may already be at its practical local simplification floor under the current seam.
