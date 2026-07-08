import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import type { BatchStateResponse } from '../api/types/crypto'
import type { InferenceQuality } from '../api/types'
import { getBatchState, getSystemStatus } from '../api/client'
import { useAppStore } from '../stores/appStore'
import { buildBatchCompletionToken, shouldHydrateRecentCurrentForBatch, shouldRefreshCompletedBatch } from './inferenceStateMachine'
import { getBatchStateRefetchInterval } from './pollingPolicy'
import { recordComparisonResult } from './useInferenceProgress'

function recordCompletedBatchComparison(
  payload: BatchStateResponse,
  setComparisonResult: ReturnType<typeof useAppStore.getState>['setComparisonResult'],
  quality?: InferenceQuality,
) {
  if (payload.status !== 'done') {
    return
  }
  const engine = payload.engine === 'mnn' ? 'mnn' : 'tvm'
  const batchBenchmark = payload.benchmark
  const inferenceBenchmark = payload.inference_benchmark ?? batchBenchmark
  const totalMetric = batchBenchmark?.total_ms
  const inferenceMetric = inferenceBenchmark?.inference_ms ?? batchBenchmark?.inference_ms
  const reconstructionMetric = engine === 'tvm'
    ? (inferenceMetric ?? inferenceBenchmark?.total_ms ?? totalMetric)
    : (totalMetric ?? inferenceMetric)
  const reconstructionMs = reconstructionMetric?.median_ms ?? reconstructionMetric?.mean_ms
  if (reconstructionMs == null) {
    return
  }
  setComparisonResult(engine, {
    engine,
    label: engine === 'mnn' ? 'MNN重建' : 'TVM重建',
    reconstructionMs,
    runMs: inferenceMetric?.median_ms ?? inferenceMetric?.mean_ms,
    sampleCount: reconstructionMetric?.n ?? inferenceMetric?.n ?? totalMetric?.n ?? payload.completed,
    quality,
    updatedAt: Date.now(),
  })
}

export function useBatchStatePoll() {
  const qc = useQueryClient()
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const lastSettledBatchToken = useAppStore((s) => s.lastSettledBatchToken)
  const setLastSettledBatchToken = useAppStore((s) => s.setLastSettledBatchToken)
  const pendingBatchJobId = useAppStore((s) => s.pendingBatchJobId)
  const setComparisonResult = useAppStore((s) => s.setComparisonResult)

  const query = useQuery({
    queryKey: ['batch-state'],
    queryFn: getBatchState,
    refetchInterval: (q) => getBatchStateRefetchInterval(q.state.data),
  })

  useEffect(() => {
    if (shouldRefreshCompletedBatch(lastSettledBatchToken, query.data)) {
      if (!query.data) {
        return
      }
      const completionToken = buildBatchCompletionToken(query.data)
      setLastSettledBatchToken(completionToken)
      const completedBatchJobId = query.data.batch_job_id ?? null
      const isCurrentSessionBatch = Boolean(completedBatchJobId)
      if (isCurrentSessionBatch) {
        recordCompletedBatchComparison(query.data, setComparisonResult, query.data.quality)
        if (shouldHydrateRecentCurrentForBatch(query.data)) {
          void qc.fetchQuery({
            queryKey: ['system-status'],
            queryFn: getSystemStatus,
          }).then((payload) => {
            const current = payload?.recent_results?.current
            if (current?.execution_mode === 'live' && current?.status === 'success') {
              setLastCompletedInference(current)
              recordComparisonResult(current, setComparisonResult)
              const quality = current.quality ?? query.data?.quality
              if (query.data) {
                recordCompletedBatchComparison(query.data, setComparisonResult, quality)
              }
            }
          }).catch(() => undefined)
        }
      }
      void qc.invalidateQueries({ queryKey: ['snapshot'] })
    }
  }, [
    query.data,
    qc,
    setLastCompletedInference,
    lastSettledBatchToken,
    setLastSettledBatchToken,
    pendingBatchJobId,
    setComparisonResult,
  ])

  return query
}
