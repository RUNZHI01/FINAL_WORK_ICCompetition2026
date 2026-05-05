import { useQuery } from '@tanstack/react-query'
import { getSystemStatus } from '../api/client'

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: getSystemStatus,
    refetchInterval: 6_000,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
  })
}
