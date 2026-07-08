import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import type { BatchStateResponse } from '../api/types/crypto'
import type { InferenceQuality } from '../api/types'
import { getBatchState, getSystemStatus } from '../api/client'
import type { ComparisonResult } from '../stores/appStore'
import { useAppStore } from '../stores/appStore'
import {
  buildBatchCompletionToken,
  shouldHydrateRecentCurrentForBatch,
  shouldRecordCompletedBatchComparison,
  shouldRefreshCompletedBatch,
} from './inferenceStateMachine'
import { getBatchStateRefetchInterval } from './pollingPolicy'
import { recordComparisonResult } from './useInferenceProgress'

function completedBatchComparison(
  payload: BatchStateResponse,
  quality?: InferenceQuality,
): ComparisonResult | undefined {
  if (payload.status !== 'done') {
    return undefined
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
    return undefined
  }
  return {
    engine,
    label: engine === 'mnn' ? 'MNN重建' : 'TVM重建',
    reconstructionMs,
    runMs: inferenceMetric?.median_ms ?? inferenceMetric?.mean_ms,
    sampleCount: reconstructionMetric?.n ?? inferenceMetric?.n ?? totalMetric?.n ?? payload.completed,
    quality,
    updatedAt: Date.now(),
  }
}

function sameComparisonMetric(left: ComparisonResult | undefined, right: ComparisonResult | undefined): boolean {
  if (!left || !right) {
    return false
  }
  return (
    left.engine === right.engine
    && left.sampleCount === right.sampleCount
    && Math.abs(left.reconstructionMs - right.reconstructionMs) < 0.005
    && Math.abs((left.runMs ?? -1) - (right.runMs ?? -1)) < 0.005
  )
}

export function useBatchStatePoll() {
  const qc = useQueryClient()
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const lastSettledBatchToken = useAppStore((s) => s.lastSettledBatchToken)
  const setLastSettledBatchToken = useAppStore((s) => s.setLastSettledBatchToken)
  const pendingBatchJobId = useAppStore((s) => s.pendingBatchJobId)
  const comparisonResults = useAppStore((s) => s.comparisonResults)
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
      const batchComparison = completedBatchComparison(query.data, query.data.quality)
      const shouldRecordBatch = shouldRecordCompletedBatchComparison(pendingBatchJobId, query.data)
      if (shouldRecordBatch && batchComparison) {
        setComparisonResult(batchComparison.engine, batchComparison)
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
                const hydratedBatchComparison = completedBatchComparison(query.data, quality)
                if (hydratedBatchComparison) {
                  setComparisonResult(hydratedBatchComparison.engine, hydratedBatchComparison)
                }
              }
            }
          }).catch(() => undefined)
        }
      }
      void qc.invalidateQueries({ queryKey: ['snapshot'] })
    } else if (query.data && shouldRecordCompletedBatchComparison(pendingBatchJobId, query.data)) {
      const batchComparison = completedBatchComparison(query.data, query.data?.quality)
      const currentComparison = batchComparison ? comparisonResults[batchComparison.engine] : undefined
      if (batchComparison && !sameComparisonMetric(currentComparison, batchComparison)) {
        setComparisonResult(batchComparison.engine, batchComparison)
      }
    }
  }, [
    query.data,
    qc,
    setLastCompletedInference,
    lastSettledBatchToken,
    setLastSettledBatchToken,
    pendingBatchJobId,
    comparisonResults,
    setComparisonResult,
  ])

  return query
}
