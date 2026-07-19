# Inference Output-Shape Caveat Investigation (2026-03-11)

## Conclusion

- Most likely root cause: the real baseline archive `/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so` is a different legacy artifact/export line from the current archive, and that baseline artifact is the source of the `249x249` output.
- Low-likelihood root cause: the payload benchmark entrypoint itself. The payload runner only does `load_module -> relax.VirtualMachine -> vm["main"](inp)` and records `last_res.shape`; it does not crop, pad, or post-process outputs.
- Secondary finding: the earlier local Scheme A validation used a different "baseline" fixture than the real Phytium baseline archive. That local fixture already returns `256x256`, so it cannot be used to argue against the remote `249x249` caveat.
- Residual uncertainty: I could not rerun the real baseline archive under the current safe runtime from this environment today because SSH is blocked, so a pure runtime-version effect is not fully eliminated.

## Confidence

- `baseline artifact / export lineage differs from current`: high
- `artifact alone, not runtime version, explains 249x249`: medium

## Evidence chain

1. The fair Scheme A runner is symmetric and reports raw `main()` output shape.

- `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh` selects the archive strictly from `INFERENCE_BASELINE_ARCHIVE` / `INFERENCE_CURRENT_ARCHIVE` and reports `output_shape = list(last_res.shape)` directly from `vm[entry_name](inp)`.
- That makes an entrypoint-side shape rewrite unlikely.

2. The real Phytium fair compare used a distinct baseline artifact from the current artifact.

- `session_bootstrap/logs/inference_compare_scheme_a_fair_fixed_20260311_154243.log` records:
  - baseline: SHA `85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849`, size `1438664`, TVM `0.21.dev0`, output `[1, 3, 249, 249]`
  - current: SHA `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`, size `1653592`, TVM `0.24.dev0`, output `[1, 3, 256, 256]`
- `session_bootstrap/tmp/inference_compare_scheme_a_fair_run_fixed_20260311_154243.env` shows that both sides used the same payload script, while baseline/current pointed at different archive roots and different runtimes.

3. The baseline SHA is longstanding and matches the intended primary baseline archive.

- `session_bootstrap/logs/full_rpc_armv8_phytium_round1.log` already recorded the primary baseline archive SHA as `85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849` on 2026-03-01.
- That makes an accidental last-minute overwrite of the baseline archive less likely.

4. The local Scheme A validation did not use the real baseline artifact.

- `session_bootstrap/reports/inference_local_scheme_a_payload_20260311_133729.md` shows the local "baseline" fixture SHA was `9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8`, not `85d701...`.
- `session_bootstrap/reports/current_runtime_compat_blocker_20260309.md` identifies `9478...` as the 2026-03-09 round1 current artifact lineage, not the longstanding baseline archive.
- Fresh local rerun from this session:

```bash
bash -lc 'set -a; source session_bootstrap/tmp/local_legacy_wrapper_validation_20260311/inference_local_legacy_wrapper.env; set +a; INFERENCE_WARMUP_RUNS=0 INFERENCE_REPEAT=1 bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline'
```

returned:

```json
{"artifact_sha256":"9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8","output_shape":[1,3,256,256]}
```

- So the local fixture baseline is an archive/content mismatch relative to the real fair-compare baseline.

5. Current-line artifacts are consistently `256x256`.

- `session_bootstrap/reports/phytium_current_safe_one_shot_smoke_20260310.md` records current SHA `2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449` with output `[1, 3, 256, 256]`.
- `session_bootstrap/reports/phytium_current_incremental_breakthrough_20260311.md` and the fair compare log record the newer current SHA `1946...` with output `[1, 3, 256, 256]`.
- That makes the baseline line, not the current line, the obvious outlier.

## Smallest attempted validation from this environment

1. Local validation succeeded.

- The local fixture "baseline" (`9478...`) was rerun through the same payload script and still returned `[1, 3, 256, 256]`.

2. Remote cross-runtime validation was attempted but blocked.

- Attempted command:

```bash
bash -lc 'set -a; source ./session_bootstrap/tmp/inference_compare_scheme_a_fair_run_fixed_20260311_154243.env; set +a; INFERENCE_WARMUP_RUNS=0 INFERENCE_REPEAT=1 bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline'
```

- Result:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

## Best judgment

- The strongest explanation is:
  - the real baseline archive is genuinely a different artifact/model-export line,
  - that line returns `249x249`,
  - and the earlier local validation missed the caveat because it used a different local "baseline" fixture (`9478...`) that already returns `256x256`.
- The only unresolved branch is whether the real baseline SHA `85d701...` would still return `249x249` under the newer current-safe runtime. That needs one follow-up SSH probe once remote access is available again.
