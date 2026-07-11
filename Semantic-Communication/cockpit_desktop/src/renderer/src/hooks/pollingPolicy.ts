import type { BatchStateResponse } from '../api/types/crypto'
import type { SystemStatusResponse } from '../api/types'

type SystemStatusPollingPayload = Partial<Pick<SystemStatusResponse, 'active_inference'>>

export function getSystemStatusRefetchInterval(payload: SystemStatusPollingPayload | null | undefined): number {
  const active = payload?.active_inference
  const requestState = String(active?.request_state || '').toLowerCase()
  return active?.running === true || requestState === 'running' ? 3000 : 6000
}

export function getBatchStateRefetchInterval(payload: BatchStateResponse | null | undefined): number | false {
  const status = String(payload?.status || '').toLowerCase()
  return status === 'running' || status === 'launching' ? 2000 : false
}
