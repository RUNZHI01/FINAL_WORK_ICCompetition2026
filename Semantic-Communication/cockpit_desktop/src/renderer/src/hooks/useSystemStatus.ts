import { useQuery } from '@tanstack/react-query'
import { getSystemStatus } from '../api/client'
import { getSystemStatusRefetchInterval } from './pollingPolicy'

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: getSystemStatus,
    refetchInterval: (q) => getSystemStatusRefetchInterval(q.state.data),
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
  })
}
