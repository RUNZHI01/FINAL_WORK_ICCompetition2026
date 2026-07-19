# Variance4 Evaluability Diagnosis

Date: `2026-04-02`

## Conclusion

`fused_variance4_add13_tir_sqrt4` can be promoted from a local-only handwritten
lane into a **remotely benchmarkable / performance-evaluable staging path**
under the current project architecture.

The required path is the same one already used by the checked-in
`transpose1` / `transpose2` / `transpose_add6` handwritten reports:

- build a **post-db swapped full-module VM artifact locally**
- stage that artifact on the board as
  `<archive>/tvm_tune_logs/optimized_model.so`
- run the existing remote payload / reconstruction wrappers against that archive

What remains local-only today is the checked-in variance4 wrapper contract and
runbook wording, not the underlying full-artifact architecture.

## Repo-grounded evidence

1. The variance4 entrypoint is already just a thin wrapper over the generic
   post-db full-module swap seam:
   - `./session_bootstrap/scripts/run_variance4_post_db_local_build.py`

2. The seam does **not** build a standalone operator runtime for remote use.
   It:
   - applies `MetaScheduleApplyDatabase` to the full Relax module
   - replaces the named `fused_variance4_add13_tir_sqrt4` PrimFunc inside that
     full module
   - calls `relax.build(swapped_mod, target=target)`
   - exports the resulting executable when `--output-dir` is provided

   This is implemented in:
   - `./session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`

3. Fresh local rerun in this diagnosis confirmed that variance4 `v13` still
   exports a full VM artifact successfully:
   - command:
     `python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_evaldiag_20260402`
   - artifact:
     `./session_bootstrap/tmp/variance4_post_db_swap_local_build_evaldiag_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
   - report:
     `./session_bootstrap/tmp/variance4_post_db_swap_local_build_evaldiag_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
   - build executable type: `VMExecutable`
   - artifact sha256:
     `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`

4. The existing remote payload runner already accepts any current-style archive
   root and always loads:
   - `<archive>/tvm_tune_logs/optimized_model.so`

   This contract is implemented in:
   - `./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`

5. The existing real reconstruction runner uses the same artifact contract for
   current:
   - explicit artifact path, or
   - `<archive>/tvm_tune_logs/optimized_model.so`

   This contract is implemented in:
   - `./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh`

6. Existing remote handwritten reports already prove this exact staging
   convention is accepted by the project:
   - `./session_bootstrap/reports/transpose1_p2_remote_benchmark_20260331_192521.md`
   - `./session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`
   - `./session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`

   In each report, the local `*_post_db_swap.so` hash matches the remote
   `.../tvm_tune_logs/optimized_model.so` hash exactly.

7. Variance4 is small but not too small to evaluate remotely. The staged
   runtime reprobe for the current best staging artifact records:
   - operator:
     `fused_variance4_add13_tir_sqrt4`
   - duration: `7099.569 us`
   - percent: `4.270070213057382`

   Source:
   - `./session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/runtime_command.log`

   This means the operator is not a dominant bottleneck like transpose1 /
   transpose2, but it is still large enough that a real board run is
   performance-evaluable instead of pure noise.

8. The current `v13` candidate is still a weak promotion target from a
   performance-delta standpoint because the existing local diagnostic already
   shows `v12` and `v13` export the same swapped artifact:
   - artifact sha equal: `true`
   - artifact size equal: `true`
   - exported artifact sha:
     `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`

   Source:
   - `./session_bootstrap/tmp/variance4_v12_v13_lowering_diagnostic_20260402.json`

   So a board run for `v13` is useful as a **path-validation run**, not as
   evidence that `v13` beats `v12`.

## Exact remote path

Recommended dedicated staging archive:

- `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4`

Path A: payload benchmark on the board

1. Build the swapped full artifact locally:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_evaldiag_20260402
```

2. Place the resulting local artifact at:

```text
/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so
```

Use the same SHA in the benchmark env:

```text
0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12
```

3. Source the normal current-safe inference env, override only the archive +
   SHA, then run the existing current payload wrapper:

```bash
set -a
source ./session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
set +a

export INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4
export INFERENCE_CURRENT_EXPECTED_SHA256=0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12
export INFERENCE_REPEAT=10
export INFERENCE_WARMUP_RUNS=2

bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

If you want the normal markdown/CSV benchmark wrapper instead of the raw current
runner, prepare an env snapshot with the same two overrides and run:

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh --env <patched-env-file>
```

Path B: real reconstruction follow-up on the same artifact

After the payload check, the same staged artifact can be exercised through:

```bash
bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
```

or through a patched `run_inference_benchmark.sh` env that points
`INFERENCE_CURRENT_CMD` at that reconstruction wrapper.

## What is not blocking promotion

- `query_tuning_record_hit = false`
- `query_ir_module_hit = false`
- `query_schedule_hit = false`

These facts block a **direct DB-record-based** operator lane, but they do not
block a **post-db full-module swap** lane, because the current architecture
already evaluates that path from the applied full Relax module.

## Recommended next action

Do **one** dedicated board-side payload benchmark for the staged variance4 `v13`
artifact, using the exact path above and a handwritten staging archive that does
not touch trusted current.

Interpret that run narrowly:

- if the SHA matches and the run is stable, the variance4 lane is no longer
  architecture-blocked from remote evaluation
- if the result is flat, that is expected because `v12` and `v13` are already
  artifact-identical locally
- do **not** spend more time on `v14` syntax cleanup unless a new variance4
  edit changes the exported artifact or a board run surfaces a real latency move
