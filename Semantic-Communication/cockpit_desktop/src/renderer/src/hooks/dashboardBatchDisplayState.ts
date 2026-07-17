import type { BatchStateResponse } from '../api/types/crypto'

type ServiceMode = 'FULL_FRAME' | 'ROI_ONLY' | 'ALERT_ONLY'
type ActiveInferenceLike = {
  running?: unknown
  request_state?: unknown
  status_category?: unknown
} | null | undefined

function normalizeCurrentServiceMode(raw: unknown): ServiceMode | undefined {
  const value = String(raw || '').trim().toUpperCase()
  if (value === 'ROI_ONLY' || value === 'ALERT_ONLY' || value === 'FULL_FRAME') return value
  return undefined
}

function normalizeBatchServiceMode(raw: unknown): ServiceMode {
  const value = String(raw || '').trim().toUpperCase()
  if (value === 'ROI_ONLY' || value === 'ALERT_ONLY') return value
  return 'FULL_FRAME'
}

export function batchMatchesCurrentServiceMode(
  batchServiceMode: unknown,
  currentMode: unknown,
): boolean {
  const normalizedCurrent = normalizeCurrentServiceMode(currentMode)
  if (!normalizedCurrent) return true
  return normalizeBatchServiceMode(batchServiceMode) === normalizedCurrent
}

export function isInferenceLaunchBlocked(currentMode: unknown): boolean {
  return normalizeCurrentServiceMode(currentMode) === 'ALERT_ONLY'
}

export function shouldDisplayDashboardBatch(
  batch: BatchStateResponse | undefined,
  pendingBatchJobId: string | null,
  currentMode: unknown,
): boolean {
  if (!batch) return false
  if (!batchMatchesCurrentServiceMode(batch.service_mode, currentMode)) return false
  const isCurrentSessionBatch = Boolean(
    batch.batch_job_id
    && pendingBatchJobId
    && batch.batch_job_id === pendingBatchJobId,
  )
  return isCurrentSessionBatch || batch.status === 'running' || batch.status === 'done'
}

export function isDashboardBatchRunning(batch: Pick<BatchStateResponse, 'status'> | null | undefined): boolean {
  const status = String(batch?.status || '').trim().toLowerCase()
  return status === 'launching' || status === 'running'
}

export function isDashboardActiveInferenceRunning(activeInference: ActiveInferenceLike): boolean {
  const requestState = String(activeInference?.request_state || '').trim().toLowerCase()
  const statusCategory = String(activeInference?.status_category || '').trim().toLowerCase()
  return Boolean(activeInference?.running) || requestState === 'running' || statusCategory === 'running'
}

export function isDashboardWorkRunning(
  batch: Pick<BatchStateResponse, 'status'> | null | undefined,
  activeInference: ActiveInferenceLike,
): boolean {
  return isDashboardBatchRunning(batch) || isDashboardActiveInferenceRunning(activeInference)
}
