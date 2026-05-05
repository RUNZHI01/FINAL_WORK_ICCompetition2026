# Handoff: current-safe artifact guard after 2026-03-11 inference benchmark

## Final benchmark outcome

- Final successful report: `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_final_20260311_024434.md`
- Baseline median: `1832.1 ms`
- Current-safe median: `2480.189 ms`
- Delta: `+648.089 ms` (`-35.37%` vs baseline)
- The final current-safe pass only succeeded after restoring the remote current archive to the 2026-03-11 hotfix artifact.

## Root cause

- The remote current-safe artifact at `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so` drifted away from the previously validated artifact.
- The failure signature from the broken current-safe payload was `AttributeError: Module has no function 'vm_load_executable'`.
- Verified good hashes from this investigation:
  - `2026-03-10` one-shot remote current-safe SHA: `2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449`
  - `2026-03-11` hotfix current-safe SHA: `d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6`

## Guard added

- `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`
  - computes the SHA-256 of the exact `optimized_model.so` it will load;
  - emits `artifact_path`, `artifact_sha256`, `artifact_sha256_expected`, and `artifact_sha256_match` in the JSON payload;
  - fails fast before inference if `INFERENCE_CURRENT_EXPECTED_SHA256` (or `INFERENCE_EXPECTED_SHA256`) is set and does not match.
- `session_bootstrap/scripts/run_inference_benchmark.sh`
  - logs the configured current expected SHA;
  - surfaces the current artifact path/hash/expected/match fields in the benchmark report.

## Next operator step

- For the next baseline-vs-current-safe inference run, set `INFERENCE_CURRENT_EXPECTED_SHA256=d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6` in the env file or shell unless a new current-safe artifact is intentionally deployed.
- If a new current-safe artifact is intentionally deployed, record its SHA first, then update `INFERENCE_CURRENT_EXPECTED_SHA256` before running the benchmark.
