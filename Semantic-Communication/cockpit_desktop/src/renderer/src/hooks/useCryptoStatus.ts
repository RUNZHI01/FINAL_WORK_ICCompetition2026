import { useQuery } from '@tanstack/react-query'
import { getCryptoStatus } from '../api/client'

/** Poll the ML-KEM crypto channel status every 2 s. */
export function useCryptoStatus() {
  return useQuery({
    queryKey: ['crypto-status'],
    queryFn: getCryptoStatus,
    refetchInterval: 2_000,
    retry: 1,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
  })
}
