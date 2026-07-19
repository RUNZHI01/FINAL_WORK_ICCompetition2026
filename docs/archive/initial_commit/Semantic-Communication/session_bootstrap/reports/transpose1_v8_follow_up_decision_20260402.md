# `fused_conv2d_transpose1_add9` v8 Follow-up Decision

Date: `2026-04-02T18:34:57+08:00`

## Baseline To Beat

- current transpose1 board baseline: `v7`
- remote report:
  `./session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- remote median: `156.785 ms`

## Re-ranked Remaining Follow-ups In The Same Locality Family

1. `h_1` overlap-carry on top of `v7`:
   the most direct remaining stage-side reduction after `v7`, because the two
   `h_1` stripes overlap by two staged rows inside each `dc_0` slice.
   Decision: attempted first, then dropped for now after local correctness
   failure.
2. Producer-only overlap carry (`data_dilate` overlap only, keep full
   `data_pad` rewrite):
   still plausible, but deprioritized until the failed broader overlap-carry
   probe is explained. It is not trustworthy enough to check in blind.
3. `w_1` sub-stripe / rolling-width carry:
   deprioritized because the live width is already only `10` padded columns in
   the winning `v7` lane, so the upside is smaller while the loop pressure
   moves back toward the already-losing consumer-order space.
4. Kernel-side slice staging:
   deprioritized because the only fresh winning evidence in transpose1 came
   from data-staging/reuse changes, not from moving the kernel side.

## Decision

No concrete `v8` candidate is worth checking in yet.

The chosen first follow-up probe was the `h_1` overlap-carry idea on top of
`v7`, but the local proof rejected it:

- scheduled reference vs experimental overlap-carry probe:
  `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.867923736572266`,
  `nonzero_diff_count = 312051`
- `v7` vs experimental overlap-carry probe:
  `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.867923736572266`,
  `nonzero_diff_count = 12288`
- localized mismatch rows from a direct local compare:
  output rows `32`, `33`, `96`, `97` only

That mismatch pattern means the naive reuse of the staged overlap is not
semantically identical for the first two output rows of each second `h_1`
stripe. Until that boundary behavior is explained, it should not become a
checked-in candidate.

## Next Evidence Step

Do one more local-only scratch diagnostic before creating any real `v8` path:

- compare the staged boundary rows around the `h_1` transition (`data_dilate`
  rows `31/32` and `data_pad` rows `32/33`) between `v7` and an overlap-carry
  throwaway variant
- verify whether the reusable portion is only producer-side
  (`data_dilate`), or whether the consumer-facing `data_pad` rows can also be
  carried safely
- only after that local row-level proof should the next checked-in candidate be
  chosen between:
  `producer-only overlap carry` or a different still-open data-locality move

## Files Changed

- `./session_bootstrap/reports/transpose1_v8_follow_up_decision_20260402.md`

Experimental `v8` source/test files were created temporarily for local proof,
then intentionally removed after the correctness failure so no broken candidate
is left behind.

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v8_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v8_vs_v7_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path("session_bootstrap/scripts").resolve()))
import check_transpose1_scheduled_reference_vs_working_copy as chk

op = "fused_conv2d_transpose1_add9"
conf = chk.get_operator_config(op)
ref = chk.load_ir_module(
    Path("session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py").resolve(),
    operator_name=op,
)
cand = chk.load_ir_module(
    Path("session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py").resolve(),
    operator_name=op,
)
inputs = chk.make_inputs(20260331, input_specs=conf["input_specs"])
ref_out = chk.run_module(
    chk.build_runtime(ref, "llvm"),
    function_name=op,
    input_specs=conf["input_specs"],
    output_shape=conf["output_shape"],
    inputs=inputs,
)
cand_out = chk.run_module(
    chk.build_runtime(cand, "llvm"),
    function_name=op,
    input_specs=conf["input_specs"],
    output_shape=conf["output_shape"],
    inputs=inputs,
)
diff = np.abs(cand_out - ref_out)
rows = np.nonzero(diff.max(axis=(0, 1, 3)))[0]
print(rows.tolist())
PY
```

## Local Status

- temporary experimental unit smoke: `4 tests`, `OK`
- no kept `v8` local build/export was run, because the overlap-carry probe
  failed local correctness first
- temporary correctness JSON outputs:
  `./session_bootstrap/tmp/transpose1_v8_correctness_20260402/check_report.json`
  and
  `./session_bootstrap/tmp/transpose1_v8_vs_v7_correctness_20260402/check_report.json`
- no SSH, scp, or remote board commands were used

## Board-side Next Step

None yet.

Do not run a board benchmark for transpose1 until the row-level local overlap
diagnostic above proves a new candidate is semantically exact enough to keep.

## Operator Control

Commit was intentionally left for manual operator control.
