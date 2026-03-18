import { useQuery } from '@tanstack/react-query'
import { fetchMandates } from '../api'
import { useSettingsStore } from '../store/settings'
import type { Mandate } from '../types'

export function useMandates() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)

  const { data, isLoading, error, refetch } = useQuery<{ mandates: Mandate[] }>({
    queryKey: ['mandates', gatewayUrl],
    queryFn: () => fetchMandates(gatewayUrl),
    refetchInterval: 10000,
    staleTime: 8000,
  })

  return {
    mandates: data?.mandates ?? [],
    isLoading,
    error,
    refetch,
  }
}
