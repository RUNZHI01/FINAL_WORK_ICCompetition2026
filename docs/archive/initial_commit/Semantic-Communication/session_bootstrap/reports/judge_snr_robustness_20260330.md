# Multi-SNR Robustness Report

- run_id: judge_snr_robustness_20260330
- generated_at: 2026-03-30T15:21:20+08:00
- latency_point_count: 4
- quality_point_count: 0
- coverage_status: latency_only
- report_json: session_bootstrap/reports/judge_snr_robustness_20260330.json
- latency_chart_svg: session_bootstrap/reports/judge_snr_robustness_20260330_latency.svg

## Latency Curve

| SNR | Status | Baseline ms | Current ms | Improvement % | Source |
|---:|---|---:|---:|---:|---|
| 8 | success | 76949.930 | 75667.989 | 1.67 | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_2026-03-01.md |
| 10 | success | 78160.686 | 77640.022 | 0.67 | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_2026-03-01.md |
| 12 | success | 77247.983 | 111505.756 | -44.35 | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_2026-03-01.md |
| 14 | success | 82090.845 | 79369.808 | 3.31 | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_2026-03-01.md |

## Findings

- Historical current latency is best at SNR=8 with 75667.989 ms and worst at SNR=12 with 111505.756 ms.
- The strongest historical regression appears at SNR=12 with improvement_pct=-44.35%.
- Quality-by-SNR points are not yet archived locally; only the historical latency sweep is currently plotted.

## Quality Points

- No per-SNR quality JSON was provided. The report therefore documents the historical latency sweep only.

## Historical Source Reports

- session_bootstrap/reports/full_rpc_armv8_phytium_snr8.md
- session_bootstrap/reports/full_rpc_armv8_phytium_snr10.md
- session_bootstrap/reports/full_rpc_armv8_phytium_snr12.md
- session_bootstrap/reports/full_rpc_armv8_phytium_snr14.md

## Manual Operator Command

```bash
for snr in 1 4 7 10 13; do
  RUN_TAG="judge_snr_${snr}_$(date +%Y%m%d_%H%M%S)"
  ENV_COPY="session_bootstrap/tmp/${RUN_TAG}.env"
  cp session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env "$ENV_COPY"
  sed -i \
    -e "s#^INFERENCE_OUTPUT_PREFIX=.*#INFERENCE_OUTPUT_PREFIX=${RUN_TAG}#" \
    -e "s#^INFERENCE_REAL_OUTPUT_PREFIX=.*#INFERENCE_REAL_OUTPUT_PREFIX=${RUN_TAG}#" \
    -e "s#^REMOTE_SNR_CURRENT=.*#REMOTE_SNR_CURRENT=${snr}#" \
    "$ENV_COPY"

  bash ./session_bootstrap/scripts/run_remote_pytorch_reference_reconstruction.sh \
    --env-file "$ENV_COPY" \
    --output-prefix "${RUN_TAG}_pytorch_ref" \
    --snr "$snr"

  set -a
  source "$ENV_COPY"
  set +a
  bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

  REF_DIR="${REMOTE_OUTPUT_BASE}/${RUN_TAG}_pytorch_ref"
  CUR_DIR="${REMOTE_OUTPUT_BASE}/${RUN_TAG}_current"
  python3 ./session_bootstrap/scripts/compute_image_quality_metrics.py \
    --ref-dir "${REF_DIR}/reconstructions" \
    --test-dir "${CUR_DIR}/reconstructions" \
    --comparison-label "pytorch_vs_tvm_current_snr${snr}" \
    --report-prefix "session_bootstrap/reports/${RUN_TAG}_quality"
done
```

## Limitations

- Existing archived SNR evidence is latency-heavy; quality-vs-SNR still needs the manual board run above.
- The generated SVG is local and dependency-free; it is meant for judge materials and not as a scientific plotting backend.
