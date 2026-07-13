import type { BatchStateResponse } from '../api/types/crypto'

type ServiceMode = 'FULL_FRAME' | 'ROI_ONLY' | 'ALERT_ONLY'

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
