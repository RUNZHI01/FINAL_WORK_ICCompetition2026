# Inference Current Regression Interim Report

- generated_at: 2026-03-08T19:55:00+08:00
- status: interim_current_regression_observed
- note: baseline statistics are stable and extracted from completed legacy benchmark logs; current statistics below are extracted from locally captured current-only process output before the remote host became unreachable again.

## Stable Baseline Statistics

Source log:
- `session_bootstrap/logs/inference_realcmd_compare_tvm310mix_20260308_1833.log`

Parsed baseline summary:
- sample_count: 300
- median_ms: 2477.300
- mean_ms: 2479.127
- min_ms: 2475.700
- max_ms: 2544.500

Interpretation:
- Baseline real inference is stable at roughly `2.48 s / sample`.

## Current Partial Statistics (captured before remote timeout)

Source:
- locally captured `good-fjord` current-only process output
- observed sample index range: `Places365_val_00000208` .. `Places365_val_00000266`

Parsed current partial summary:
- sample_count: 59
- median_ms: 6957.800
- mean_ms: 7154.273
- min_ms: 3365.700
- max_ms: 21305.000
- p90_ms: 11314.200

Representative observed current times:
- `8.7682 s`
- `4.7675 s`
- `3.5787 s`
- `12.1224 s`
- `14.2412 s`
- `21.3050 s`

## Baseline vs Current (partial but already decisive)

- delta_median_ms_current_minus_baseline: 4480.500
- slowdown_pct_vs_baseline: 180.86

Interpretation:
- Current is not merely slightly slower than baseline.
- On the captured 59-sample slice, current median inference latency is about **2.81x** the baseline median.
- Current also shows extreme instability: the worst observed sample reached `21.305 s`, far above both baseline mean and baseline max.

## Most Credible Current Conclusion

At this stage, the evidence is already strong enough to conclude:

1. baseline is stable and repeatable;
2. current is materially worse on real inference latency;
3. current latency is highly unstable (multi-second jitter well beyond baseline variance);
4. remote stability also degraded again during the current-only run, with SSH timing out afterwards.

## Remaining Dirty Point

There is still a legacy-behavior issue in `tvm_002.py` / legacy runner interaction:
- some logs or output paths still mention `inference_benchmark_baseline` even when the current-only path is being exercised.

This does not invalidate the observed regression, but it should be cleaned up before claiming a fully normalized benchmark pipeline.

## Recommended Next Step

When the remote host is reachable again:

1. capture the exact current-only run into a dedicated, uniquely named output prefix;
2. fix the remaining legacy output-path ambiguity inside `tvm_002.py` or its wrapper;
3. rerun a short current-only batch (small sample subset) to obtain a clean current summary directly comparable to the baseline summary above.
