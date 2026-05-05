# `fused_variance4_add13_tir_sqrt4` v14 Local Status

Date: `2026-04-03`

## Reconstructed Lane Baseline

- the handwritten lane is still anchored to the frozen `joint-top6`
  best-staging task summary + DB through the checked-in post-db scheduled
  reference seed
- `v6` was the first allclose-only multiply-fold candidate; `v6a` restored
  exact equality by inserting the one-element volatile local round-trip that
  blocks backend `fmadd` contraction
- `v8`, `v11`, `v12`, and `v13` all stayed exact-preserving locally; the
  checked diagnostics then showed `v11`/`v12` and `v12`/`v13` were artifact-
  identical under the local post-db swap build path
- `v13` already proved on `2026-04-02` that variance4 is remotely evaluable
  through the repo’s existing full-module handwritten staging path, but that
  exact `v13` candidate did not produce a speedup claim and was artifact-
  identical to `v12`

This `v14` pass therefore follows the last durable recommendation from the
variance4 reports: do not spend more time on pure syntax cleanup unless the
next edit lands a new exact-preserving equivalence class or changes the
exported artifact.

## Chosen Edit

- keep the `v13` unit-axis cleanup intact
- keep the explicit `.data`-level `volatile_scope` marker on the one-element
  local round-trip intact
- replace only the one-element local declaration-level encoding from
  `T.decl_buffer((1,), "float32", scope="local")` to
  `T.alloc_buffer((T.int64(1),), "float32", scope="local")`

Rationale: `variance4_v12_local_status_20260402.md` already recorded a scratch
observation that this alternate handle-free local form was importable,
buildable, and exact-preserving, but it had never been checked in as a real
repo-native candidate. That makes `v14` a new exact-preserving storage-encoding
equivalence class rather than another placeholder or unit-index cleanup clone.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v14_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v14_local_status_20260403.md`

## Commands Run

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# scratch probe: replace only the v13 local declaration
#   T.decl_buffer((1,), "float32", scope="local")
# with
#   T.alloc_buffer((T.int64(1),), "float32", scope="local")
# then compare against the frozen scheduled reference
PY
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v14_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14
python3 - <<'PY'
# compare v13/v14 post-db build reports for artifact sha + size deltas
PY
```

## Local Status

- scratch probe result: `exact_equal = true`
- focused variance4 unit tests: `66 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap build:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is **not** identical to `v13`:
  - `v13` artifact SHA256:
    `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
  - `v14` artifact SHA256:
    `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
  - `v13` artifact size: `1674456`
  - `v14` artifact size: `1674488`
- this is therefore the first post-`v13` variance4 candidate that is both
  exact-preserving locally and exported-artifact-distinct under the repo’s
  full-module handwritten seam
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
- build artifact size bytes:
  `1674488`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v14_correctness_check.json`

## Boundary

The `v14` result is mature enough for the already-established repo-pattern-safe
variance4 remote staging path described in:

- `./session_bootstrap/reports/variance4_evaluability_diagnosis_20260402.md`

However, this session stops at the honest local boundary.

Why:

- the current environment does not permit SSH / remote board execution
- the mission here was completed locally with focused tests, exactness proof,
  structural swap/build proof, and an artifact-distinct export

So the next step, in a remote-capable session, is not more local syntax work.
It is one dedicated board-side payload benchmark of this exact `v14` artifact
through the existing variance4 full-module staging path, while keeping trusted
current untouched.
