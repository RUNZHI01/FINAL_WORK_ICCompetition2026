# Inference Benchmark Baseline Adapter Notes

- generated_at: 2026-03-08T18:04:00+08:00
- scope: session_bootstrap inference benchmark legacy baseline adapter

## What Changed

`run_inference_benchmark.sh` now accepts two structured output styles from `INFERENCE_BASELINE_CMD` / `INFERENCE_CURRENT_CMD`:

1. JSON payloads produced by `run_remote_tvm_inference_payload.sh`
2. Legacy `tvm_002.py`-style log lines such as:
   - `批量推理时间（1 个样本）: 0.1129 秒`

Legacy lines are parsed into the same normalized fields used by the benchmark report/raw csv:

- `run_median_ms`
- `run_mean_ms`
- `run_min_ms`
- `run_max_ms`
- `run_variance_ms2`
- `run_count`

For legacy commands, `load_ms` and `vm_init_ms` remain `NA` because that path does not expose them directly.

## Validation Performed

### 1. Syntax

- `bash -n session_bootstrap/scripts/run_inference_benchmark.sh`
- `bash -n session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`

### 2. End-to-end parser smoke

A synthetic benchmark run mixed:

- baseline = temporary shell script emitting legacy `批量推理时间（1 个样本）: ... 秒` lines
- current = temporary shell script emitting the JSON payload format

Artifacts:

- report: `session_bootstrap/reports/inference_legacy_parse_ok_20260308_1807.md`
- raw: `session_bootstrap/reports/inference_legacy_parse_ok_20260308_1807_raw.csv`
- log: `session_bootstrap/logs/inference_legacy_parse_ok_20260308_1807.log`

Result: `status=success`

This confirms the adapter can unify legacy baseline output and JSON current output into one comparable benchmark report.

## Current Remote Reality

The current env file in active use:

- `session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env`

already supports the current VM benchmark path, but it does **not** define the old realcmd variables required to invoke the historical baseline `tvm_002.py` flow directly, including:

- `REMOTE_JSCC_DIR`
- `REMOTE_INPUT_DIR`
- `REMOTE_OUTPUT_BASE`
- `REMOTE_SNR_BASELINE`
- `REMOTE_BATCH_BASELINE`

So the code-side adapter is ready, but a true remote baseline-vs-current inference benchmark still needs either:

1. those legacy vars populated in a benchmark env, or
2. a new baseline command that emits structured timing on the current host layout.

## Recommended Next Step

Create a dedicated benchmark env that keeps the current VM path for `INFERENCE_CURRENT_CMD` and defines a valid legacy `INFERENCE_BASELINE_CMD` against the present remote directory layout. Then run:

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh --env <that-env>
```
