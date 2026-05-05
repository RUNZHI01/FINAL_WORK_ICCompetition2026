import { useQuery } from '@tanstack/react-query'
import { getSnapshot } from '../api/client'

export function useDemoSnapshot() {
  return useQuery({
    queryKey: ['snapshot'],
    queryFn: getSnapshot,
    refetchInterval: 8_000,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
  })
}
