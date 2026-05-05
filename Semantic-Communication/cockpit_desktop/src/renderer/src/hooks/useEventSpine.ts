import { useQuery } from '@tanstack/react-query'
import { getEventSpine } from '../api/client'
import type { EventSpineEvent, EventSpineResponse } from '../api/types'

type EventSpineQueryShape = EventSpineResponse & {
  recent_events?: EventSpineEvent[]
}

export type EventSpineFeed = {
  events: EventSpineEvent[]
  eventCount: number
}

export function useEventSpine(limit = 20) {
  return useQuery({
    queryKey: ['event-spine', limit],
    queryFn: () => getEventSpine(limit),
    refetchInterval: 2_000,
    retry: 2,
    select: (data): EventSpineFeed => {
      const normalized = data as EventSpineQueryShape
      const events = normalized.recent_events ?? normalized.events ?? []
      const eventCount = normalized.aggregate?.event_count ?? events.length
      return { events, eventCount }
    },
  })
}
