import type { RunInferenceResponse } from '../api/types'
import type { ComparisonEngineKey, ComparisonResult } from '../stores/appStore'

type ComparisonEngine = ComparisonEngineKey

function numericValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function objectValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' ? value as Record<string, unknown> : undefined
}

function firstNumeric(...values: Array<unknown>): number | undefined {
  for (const value of values) {
    const numeric = numericValue(value)
    if (numeric != null) {
      return numeric
    }
  }
  return undefined
}

function normalizedExecutionMode(payload: RunInferenceResponse): string {
  return String(payload.execution_mode || '').trim().toLowerCase()
}

function comparisonEngine(payload: RunInferenceResponse): ComparisonEngine | null {
  if (payload.variant === 'baseline') return 'pytorch'
  if (payload.variant === 'current') {
    const directEngine = String(payload.inference_engine || '').trim().toLowerCase()
    const wrapperSummary = objectValue(payload.wrapper_summary)
    const wrapperEngine = String(wrapperSummary?.inference_engine || '').trim().toLowerCase()
    const runnerSummary = objectValue(payload.runner_summary)
    const runnerEngine = String(runnerSummary?.inference_engine || '').trim().toLowerCase()
    const engine = directEngine || wrapperEngine || runnerEngine
    return engine === 'mnn' ? 'mnn' : 'tvm'
  }
  return null
}

function allowsComparison(payload: RunInferenceResponse, engine: ComparisonEngine): boolean {
  const executionMode = normalizedExecutionMode(payload)
  if (engine === 'pytorch') {
    return (
      payload.status === 'success'
      || executionMode === 'reference'
      || payload.status === 'fallback'
    ) && (executionMode === 'live' || executionMode === 'reference' || executionMode === 'prerecorded')
  }
  if (payload.status !== 'success') {
    return false
  }
  return executionMode === 'live' || executionMode === 'prerecorded'
}

function totalWallMsPerImage(summary: Record<string, unknown> | undefined): number | undefined {
  if (!summary) {
    return undefined
  }
  const totalWallMs = numericValue(summary.total_wall_ms)
  const sampleCount = firstNumeric(
    summary.processed_count,
    summary.input_count,
    summary.selected_input_count,
    summary.max_inputs,
  )
  if (totalWallMs == null || sampleCount == null || sampleCount <= 0) {
    return undefined
  }
  return totalWallMs / sampleCount
}

function summaryCandidates(payload: RunInferenceResponse): Array<Record<string, unknown> | undefined> {
  const rootSummary = objectValue(payload.runner_summary)
  const wrapperSummary = objectValue(payload.wrapper_summary)
  const wrapperInferenceSummary = objectValue(wrapperSummary?.inference_summary)
  const pipelineSummary = objectValue(rootSummary?.pipeline)
  const pipelineBenchmark = objectValue(pipelineSummary?.benchmark)
  const rootBenchmark = objectValue(rootSummary?.benchmark)
  return [pipelineSummary, rootSummary, wrapperInferenceSummary, pipelineBenchmark, rootBenchmark]
}

function sampleStat(summary: Record<string, unknown> | undefined, key: string): Record<string, unknown> | undefined {
  const sampleStats = objectValue(summary?.sample_stats)
  return objectValue(sampleStats?.[key])
}

function pickReconstructionMs(payload: RunInferenceResponse, engine: ComparisonEngine): number | undefined {
  const wrapperSummary = objectValue(payload.wrapper_summary)
  const candidates = summaryCandidates(payload)
  const controlTransport = String(payload.control_transport || '').trim().toLowerCase()
  if (engine === 'tvm' && normalizedExecutionMode(payload) === 'live' && controlTransport === 'mlkem') {
    return firstNumeric(
      pickRunMs(payload),
      payload.timings?.payload_ms,
      ...candidates.flatMap((summary) => [
        summary?.run_median_ms,
        summary?.run_mean_ms,
        sampleStat(summary, 'run_ms')?.median_ms,
        sampleStat(summary, 'run_ms')?.mean_ms,
      ]),
      payload.timings?.total_ms,
      wrapperSummary?.per_image_ms,
    )
  }
  return firstNumeric(
    payload.timings?.total_ms,
    payload.timings?.payload_ms,
    wrapperSummary?.per_image_ms,
    ...candidates.flatMap((summary) => [
      sampleStat(summary, 'total_ms')?.median_ms,
      sampleStat(summary, 'total_ms')?.mean_ms,
      summary?.ms_per_image,
      summary?.run_median_ms,
      summary?.run_mean_ms,
      totalWallMsPerImage(summary),
    ]),
  )
}

function pickRunMs(payload: RunInferenceResponse): number | undefined {
  const wrapperSummary = objectValue(payload.wrapper_summary)
  const candidates = summaryCandidates(payload)
  return firstNumeric(
    ...candidates.flatMap((summary) => [
      sampleStat(summary, 'run_ms')?.median_ms,
      sampleStat(summary, 'run_ms')?.mean_ms,
      summary?.run_median_ms,
      summary?.run_mean_ms,
      summary?.ms_per_image,
      totalWallMsPerImage(summary),
    ]),
    payload.timings?.payload_ms,
    wrapperSummary?.per_image_ms,
  )
}

function pickSampleCount(payload: RunInferenceResponse): number | undefined {
  const candidates = summaryCandidates(payload)
  return firstNumeric(
    ...candidates.flatMap((summary) => [
      summary?.processed_count,
      summary?.input_count,
      summary?.selected_input_count,
      summary?.max_inputs,
      sampleStat(summary, 'total_ms')?.count,
      sampleStat(summary, 'run_ms')?.count,
    ]),
    payload.live_progress?.completed_count,
    payload.live_progress?.expected_count,
  )
}

export function comparisonResultFromInferencePayload(
  payload: RunInferenceResponse | null | undefined,
): ComparisonResult | undefined {
  if (!payload) {
    return undefined
  }
  const engine = comparisonEngine(payload)
  if (!engine || !allowsComparison(payload, engine)) {
    return undefined
  }

  const reconstructionMs = pickReconstructionMs(payload, engine)
  if (reconstructionMs == null) {
    return undefined
  }
  if (engine === 'pytorch' && reconstructionMs <= 0) {
    return undefined
  }

  const result: ComparisonResult = {
    engine,
    label: engine === 'pytorch' ? 'PyTorch参考' : (engine === 'mnn' ? 'MNN重建' : 'TVM重建'),
    reconstructionMs,
    runMs: pickRunMs(payload),
    sampleCount: pickSampleCount(payload),
    quality: payload.quality,
  }
  if (payload.quality_pairs) {
    result.qualityPairs = payload.quality_pairs
  }
  return result
}
