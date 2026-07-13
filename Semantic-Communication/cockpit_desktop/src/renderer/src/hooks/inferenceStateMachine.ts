import type { RunInferenceResponse } from '../api/types'
import type { BatchStateResponse } from '../api/types/crypto'

export function isCompletedInferenceResult(payload: RunInferenceResponse | null | undefined): boolean {
  return Boolean(payload && payload.request_state === 'completed')
}

export function shouldTrackInferenceJob(payload: RunInferenceResponse | null | undefined): boolean {
  return Boolean(payload?.job_id) && !isCompletedInferenceResult(payload)
}

export function shouldFinalizeInferenceJob(
  payload: RunInferenceResponse | null | undefined,
  activeJobId: string | null,
): boolean {
  return Boolean(activeJobId) && isCompletedInferenceResult(payload)
}

export function buildBatchCompletionToken(payload: BatchStateResponse | null | undefined): string | null {
  if (!payload || payload.status !== 'done') {
    return null
  }

  return [
    payload.batch_job_id ?? '',
    payload.engine ?? '',
    payload.finished_at ?? '',
    payload.total ?? '',
    payload.completed ?? '',
  ].join('|')
}

export function shouldRefreshCompletedBatch(
  lastSettledBatchToken: string | null,
  payload: BatchStateResponse | null | undefined,
): boolean {
  const token = buildBatchCompletionToken(payload)
  return Boolean(token) && token !== lastSettledBatchToken
}

export function shouldHydrateRecentCurrentForBatch(payload: BatchStateResponse | null | undefined): boolean {
  if (!payload || payload.status !== 'done') {
    return false
  }
  return payload.engine === 'tvm' || payload.engine === 'mnn'
}

function hasMetricValue(metric: { median_ms?: number | null; mean_ms?: number | null } | null | undefined): boolean {
  return metric?.median_ms != null || metric?.mean_ms != null
}

export function hasCompletedBatchComparisonMetric(payload: BatchStateResponse | null | undefined): boolean {
  if (!payload || payload.status !== 'done') {
    return false
  }
  const batchBenchmark = payload.benchmark
  const inferenceBenchmark = payload.inference_benchmark ?? batchBenchmark
  return Boolean(
    hasMetricValue(inferenceBenchmark?.inference_ms)
    || hasMetricValue(inferenceBenchmark?.total_ms)
    || hasMetricValue(batchBenchmark?.inference_ms)
    || hasMetricValue(batchBenchmark?.total_ms),
  )
}

export function shouldRecordCompletedBatchComparison(
  pendingBatchJobId: string | null,
  payload: BatchStateResponse | null | undefined,
): boolean {
  if (!payload || payload.status !== 'done') {
    return false
  }
  const completedBatchJobId = payload.batch_job_id ?? null
  const isCurrentSessionBatch = Boolean(
    completedBatchJobId && (!pendingBatchJobId || pendingBatchJobId === completedBatchJobId),
  )
  return isCurrentSessionBatch || hasCompletedBatchComparisonMetric(payload)
}
