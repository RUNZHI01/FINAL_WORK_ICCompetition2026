import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import type { RunInferenceResponse } from '../api/types'
import { getInferenceProgress } from '../api/client'
import { useAppStore } from '../stores/appStore'
import { shouldFinalizeInferenceJob } from './inferenceStateMachine'
import { comparisonResultFromInferencePayload } from './comparisonResult'

export function recordComparisonResult(
  payload: RunInferenceResponse,
  setComparisonResult: ReturnType<typeof useAppStore.getState>['setComparisonResult'],
) {
  const result = comparisonResultFromInferencePayload(payload)
  if (!result) {
    return
  }
  setComparisonResult(result.engine, {
    ...result,
    updatedAt: Date.now(),
  })
}

export function useInferenceProgressPoll() {
  const activeJobId = useAppStore((s) => s.activeJobId)
  const setActiveJobId = useAppStore((s) => s.setActiveJobId)
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const setComparisonResult = useAppStore((s) => s.setComparisonResult)
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: ['inference-progress', activeJobId],
    queryFn: () => (activeJobId ? getInferenceProgress(activeJobId) : Promise.resolve(null)),
    enabled: !!activeJobId,
    refetchInterval: 2000,
  })

  useEffect(() => {
    if (shouldFinalizeInferenceJob(query.data, activeJobId)) {
      const completedResult = query.data
      if (!completedResult) {
        return
      }
      // Save completed data before clearing active job
      setLastCompletedInference(completedResult)
      recordComparisonResult(completedResult, setComparisonResult)
      setActiveJobId(null)
      void qc.invalidateQueries({ queryKey: ['system-status'] })
      void qc.invalidateQueries({ queryKey: ['snapshot'] })
    }
  }, [query.data, activeJobId, setActiveJobId, setLastCompletedInference, setComparisonResult, qc])

  return query
}
