import type { RunInferenceResponse } from '../../../api/types'

export type ComparisonMetricRow = {
  key: string
  metric: string
  current?: number | null
  baseline?: number | null
}

export function buildComparisonRows(
  current?: RunInferenceResponse,
  baseline?: RunInferenceResponse,
): ComparisonMetricRow[] {
  return [
    { key: 'payload_ms', metric: 'Payload (ms)', current: current?.timings?.payload_ms, baseline: baseline?.timings?.payload_ms },
    { key: 'total_ms', metric: 'Total (ms)', current: current?.timings?.total_ms, baseline: baseline?.timings?.total_ms },
    { key: 'psnr', metric: 'PSNR (dB)', current: current?.quality?.psnr_db, baseline: baseline?.quality?.psnr_db },
    { key: 'ssim', metric: 'SSIM', current: current?.quality?.ssim, baseline: baseline?.quality?.ssim },
  ]
}
