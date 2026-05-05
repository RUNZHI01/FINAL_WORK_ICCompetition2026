import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  postProbeBoard,
  postRunInference,
  postRunBaseline,
  postInjectFault,
  postRecover,
  postLinkDirectorProfile,
  postBoardAccess,
  postJobManifestGatePreview,
  postRunInferenceBatch,
  postRunMnnBatch,
} from '../api/client'
import { useAppStore } from '../stores/appStore'
import { isCompletedInferenceResult, shouldTrackInferenceJob } from './inferenceStateMachine'
import { recordComparisonResult } from './useInferenceProgress'

function useInvalidateOnSuccess() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: ['system-status'] })
    void qc.invalidateQueries({ queryKey: ['snapshot'] })
    void qc.invalidateQueries({ queryKey: ['aircraft-position'] })
    void qc.invalidateQueries({ queryKey: ['crypto-status'] })
  }
}

export function useProbeBoard() {
  const inv = useInvalidateOnSuccess()
  return useMutation({ mutationFn: postProbeBoard, onSuccess: inv })
}

export function useRunInference() {
  const inv = useInvalidateOnSuccess()
  const setActiveJobId = useAppStore((s) => s.setActiveJobId)
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const setComparisonResult = useAppStore((s) => s.setComparisonResult)
  return useMutation({
    mutationFn: ({ imageIndex, variant }: { imageIndex?: number; variant?: string }) =>
      postRunInference(imageIndex, variant),
    onSuccess: (data) => {
      inv()
      // ML-KEM 同步完成时 request_state=completed，直接持久化结果
      if (isCompletedInferenceResult(data)) {
        setLastCompletedInference(data)
        recordComparisonResult(data, setComparisonResult)
        setActiveJobId(null)
        return
      }
      if (shouldTrackInferenceJob(data)) setActiveJobId(data.job_id ?? null)
    },
  })
}

export function useRunBaseline() {
  const inv = useInvalidateOnSuccess()
  const setActiveJobId = useAppStore((s) => s.setActiveJobId)
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const setComparisonResult = useAppStore((s) => s.setComparisonResult)
  return useMutation({
    mutationFn: ({ imageIndex, count }: { imageIndex?: number; count?: number }) =>
      postRunBaseline(imageIndex, count ?? 300),
    onSuccess: (data) => {
      inv()
      if (isCompletedInferenceResult(data)) {
        setLastCompletedInference(data)
        recordComparisonResult(data, setComparisonResult)
        setActiveJobId(null)
        return
      }
      if (shouldTrackInferenceJob(data)) setActiveJobId(data.job_id ?? null)
    },
  })
}

export function useInjectFault() {
  const inv = useInvalidateOnSuccess()
  return useMutation({
    mutationFn: (faultType: string) => postInjectFault(faultType),
    onSuccess: inv,
  })
}

export function useRecover() {
  const inv = useInvalidateOnSuccess()
  return useMutation({ mutationFn: postRecover, onSuccess: inv })
}

export function useSwitchLinkProfile() {
  const inv = useInvalidateOnSuccess()
  return useMutation({
    mutationFn: (profileId: string) => postLinkDirectorProfile(profileId),
    onSuccess: inv,
  })
}

export function useSetBoardAccess() {
  const inv = useInvalidateOnSuccess()
  return useMutation({
    mutationFn: postBoardAccess,
    onSuccess: inv,
  })
}

export function useGatePreview() {
  const inv = useInvalidateOnSuccess()
  return useMutation({
    mutationFn: (variant: string) => postJobManifestGatePreview(variant),
    onSuccess: inv,
  })
}

export function useRunInferenceBatch() {
  const inv = useInvalidateOnSuccess()
  const qc = useQueryClient()
  const setPendingBatchJobId = useAppStore((s) => s.setPendingBatchJobId)
  return useMutation({
    mutationFn: ({ count }: { count?: number } = {}) => postRunInferenceBatch(count ?? 300),
    onSuccess: (data) => {
      inv()
      setPendingBatchJobId(data.batch_job_id ?? null)
      void qc.invalidateQueries({ queryKey: ['batch-state'] })
    },
  })
}

export function useRunMnnBatch() {
  const inv = useInvalidateOnSuccess()
  const qc = useQueryClient()
  const setPendingBatchJobId = useAppStore((s) => s.setPendingBatchJobId)
  return useMutation({
    mutationFn: ({ count }: { count?: number } = {}) => postRunMnnBatch(count ?? 300),
    onSuccess: (data) => {
      inv()
      setPendingBatchJobId(data.batch_job_id ?? null)
      void qc.invalidateQueries({ queryKey: ['batch-state'] })
    },
  })
}
