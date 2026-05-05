import { useQuery } from '@tanstack/react-query'
import { getAircraftPosition } from '../api/client'

export function useAircraftPosition() {
  return useQuery({
    queryKey: ['aircraft-position'],
    queryFn: getAircraftPosition,
    refetchInterval: 3_000,
    retry: 2,
    staleTime: 2_000,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
  })
}
