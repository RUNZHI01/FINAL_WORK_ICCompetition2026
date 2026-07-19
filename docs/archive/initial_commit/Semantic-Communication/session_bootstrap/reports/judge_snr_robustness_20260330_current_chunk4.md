# Multi-SNR Robustness Report

- run_id: judge_snr_robustness_20260330_current_chunk4
- generated_at: 2026-03-30T15:55:50+08:00
- latency_point_count: 5
- quality_point_count: 5
- coverage_status: latency_and_quality
- report_json: session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.json
- latency_chart_svg: session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_latency.svg
- quality_chart_svg: session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_quality.svg

## Latency Curve

| SNR | Status | Baseline ms | Current ms | Improvement % | Source |
|---:|---|---:|---:|---:|---|
| 1 | success | NA | 228.223 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_current_chunk4_20260330_152054.md |
| 4 | success | NA | 228.595 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_current_chunk4_20260330_152054.md |
| 7 | success | NA | 233.509 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_current_chunk4_20260330_152054.md |
| 10 | success | NA | 231.893 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_current_chunk4_20260330_152054.md |
| 13 | success | NA | 234.018 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_sweep_current_chunk4_20260330_152054.md |

## Findings

- Historical current latency is best at SNR=1 with 228.223 ms and worst at SNR=13 with 234.018 ms.
- Quality coverage exists for 5 SNR points; best mean PSNR currently recorded is 36.8695 dB at SNR=13.

## Quality Points

| SNR | Comparison | PSNR (dB) | SSIM | LPIPS | Source |
|---:|---|---:|---:|---:|---|
| 1 | trusted_current_snr1_vs_pytorch_reference | 29.1452 | 0.900039 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_current_chunk4_snr1_20260330_152054_quality.json |
| 4 | trusted_current_snr4_vs_pytorch_reference | 31.8047 | 0.939559 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_current_chunk4_snr4_20260330_152054_quality.json |
| 7 | trusted_current_snr7_vs_pytorch_reference | 34.0185 | 0.961243 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_current_chunk4_snr7_20260330_152054_quality.json |
| 10 | trusted_current_snr10_vs_pytorch_reference | 35.6644 | 0.972735 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_current_chunk4_snr10_20260330_152054_quality.json |
| 13 | trusted_current_snr13_vs_pytorch_reference | 36.8695 | 0.978757 | NA | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/snr_current_chunk4_snr13_20260330_152054_quality.json |

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

- Quality-vs-SNR points are now archived locally for the current trusted chunk4 line; LPIPS remains environment-gated.
- The generated SVG is local and dependency-free; it is meant for judge materials and not as a scientific plotting backend.
