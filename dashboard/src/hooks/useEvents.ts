import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchEvents } from '../api'
import { useSettingsStore } from '../store/settings'
import type { Event } from '../types'

interface UseEventsOptions {
  kind?: string
  limit?: number
}

export function useEvents(options: UseEventsOptions = {}) {
  const { kind, limit = 80 } = options
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const [isLive, setLive] = useState(false)

  const { data, isLoading, error, refetch } = useQuery<{ events: Event[] }>({
    queryKey: ['events', gatewayUrl, kind, limit],
    queryFn: () => fetchEvents(gatewayUrl, kind, limit),
    refetchInterval: isLive ? 3000 : false,
    staleTime: isLive ? 2000 : 30000,
  })

  return {
    events: data?.events ?? [],
    isLoading,
    error,
    refetch,
    isLive,
    setLive,
  }
}
