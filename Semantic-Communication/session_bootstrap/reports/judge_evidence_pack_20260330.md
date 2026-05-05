# Judge Technical Evidence Pack

- run_id: judge_evidence_pack_20260330
- generated_at: 2026-03-30T15:25:15+08:00
- report_json: session_bootstrap/reports/judge_evidence_pack_20260330.json

## Executive Summary

- Trusted payload benchmark holds at 1846.9 -> 130.219 ms (92.95% improvement).
- Trusted real reconstruction holds at 1850.0 -> 230.339 ms/image (87.55% improvement).
- Current stays closer to the PyTorch reference than baseline by 1.2147 dB mean PSNR.
- Operator evidence is currently stage_level_hotspot_only; the top stage-weight hotspot set starts with reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4.
- Trusted current resource profile shows avg CPU user/system/idle/wait 67.266 / 11.830 / 20.160 / 0.830 %.
- Trusted local artifact size is 1651136 bytes (1.575 MiB).
- Multi-SNR evidence currently covers 4 latency points and 0 quality points.

## Evidence Tracks

### 1. Trusted Performance Baseline

- payload_report: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md
- payload_median_ms: 1846.9 -> 130.219
- payload_improvement_pct: 92.95
- e2e_report: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md
- e2e_median_ms_per_image: 1850.0 -> 230.339
- e2e_improvement_pct: 87.55

### 2. Formal Quality Report

- quality_report_markdown: session_bootstrap/reports/judge_quality_formal_report_20260330.md
- quality_report_json: session_bootstrap/reports/judge_quality_formal_report_20260330.json
- Against the same PyTorch reference, current is 1.2147 dB higher in mean PSNR and 0.002478 higher in mean SSIM than baseline.
- Direct TVM baseline-vs-current divergence is 34.5299 dB PSNR and 0.970432 SSIM.
- LPIPS is missing for at least one comparison; keep PSNR/SSIM as the formal minimum set and treat LPIPS as environment-gated complementary evidence.
- At least one comparison required spatial normalization; judge-facing tables should footnote the crop policy.

### 3. Operator-Level Profiling / Hotspots

- hotspot_report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323.json
- hotspot_overall_status: stage_level_hotspot_only
- recommended_full_hotspot_tasks: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_status: fallback_only
- runtime_fallback_reason: AttributeError: Module has no function 'profile'

### 4. CPU / Memory / Artifact Size

- resource_profile_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/resource_profile_trusted_current_20260312_001.json
- wall_time_seconds: 98
- avg_cpu_user_system_idle_wait_pct: 67.266 / 11.830 / 20.160 / 0.830
- min_free_kb: 115408
- avg_runnable_max_runnable: 3.755 / 8
- target_run_median_ms: 264.912
- target_artifact_sha256_match: True
- trusted_local_artifact: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so
- trusted_local_artifact_size_bytes: 1651136
- trusted_local_artifact_size_mib: 1.575

### 5. Multi-SNR Robustness

- snr_report_markdown: session_bootstrap/reports/judge_snr_robustness_20260330.md
- snr_latency_points: 4
- snr_quality_points: 0
- snr_coverage_status: latency_only
- latency_chart_svg: session_bootstrap/reports/judge_snr_robustness_20260330_latency.svg
- Historical current latency is best at SNR=8 with 75667.989 ms and worst at SNR=12 with 111505.756 ms.
- The strongest historical regression appears at SNR=12 with improvement_pct=-44.35%.
- Quality-by-SNR points are not yet archived locally; only the historical latency sweep is currently plotted.

## Defense Slide Map

| Slide | Claim | Evidence |
|---|---|---|
| 1. Trusted Performance Headline | Current trusted artifact materially outperforms baseline on both payload and real reconstruction. | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md; /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md |
| 2. Reconstruction Quality | Current keeps reconstruction quality at least comparable to baseline against the PyTorch reference. | session_bootstrap/reports/judge_quality_formal_report_20260330.md |
| 3. Operator and System Bottlenecks | The dominant optimization targets are already localized even though trusted runtime per-op profiling remains limited. | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323.md; /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_trusted_current_20260312_001.log |
| 4. Resource Footprint | CPU load, free-memory floor, and artifact size are bounded and can be cited directly. | /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/resource_profile_trusted_current_20260312_001.json |
| 5. Robustness vs SNR | Historical SNR sweep already exists for latency, and the missing quality-vs-SNR path is fully scripted for manual collection. | session_bootstrap/reports/judge_snr_robustness_20260330.md |

## Manual Operator Command For Missing SNR Quality Points

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

- Runtime per-op profiling on the trusted remote runtime still falls back to stage-weight hotspot evidence because vm.profile support is not validated there.
- LPIPS is not guaranteed in historical data because the archived quality runs skipped it when the environment lacked torch/lpips.
- The current SNR pack is only partially complete until the manual quality-by-SNR loop is executed and archived.
