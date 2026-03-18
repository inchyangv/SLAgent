import { useQuery } from '@tanstack/react-query'
import { fetchBalances } from '../api'
import { useSettingsStore } from '../store/settings'
import type { BalancesResponse } from '../types'

export function useBalances() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)

  const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<BalancesResponse>({
    queryKey: ['balances', gatewayUrl],
    queryFn: () => fetchBalances(gatewayUrl),
    refetchInterval: 10000,
    staleTime: 8000,
    retry: 2,
  })

  return { data, isLoading, error, refetch, dataUpdatedAt }
}
