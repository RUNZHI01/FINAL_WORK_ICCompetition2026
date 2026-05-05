import type { BatchStateResponse } from '../api/types/crypto'

export function getBatchStateRefetchInterval(payload: BatchStateResponse | null | undefined): number | false {
  const status = String(payload?.status || '').toLowerCase()
  return status === 'running' || status === 'launching' ? 2000 : false
}
