import { useQuery } from '@tanstack/react-query'
import { fetchReceipts } from '../api'
import { useSettingsStore } from '../store/settings'
import type { Receipt } from '../types'

interface UseReceiptsOptions {
  limit?: number
  isAutopilotRunning?: boolean
}

export function useReceipts(options: UseReceiptsOptions = {}) {
  const { limit = 100, isAutopilotRunning = false } = options
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)

  const { data, isLoading, error, refetch } = useQuery<Receipt[]>({
    queryKey: ['receipts', gatewayUrl, limit],
    queryFn: () => fetchReceipts(gatewayUrl, limit),
    refetchInterval: isAutopilotRunning ? 5000 : false,
    staleTime: isAutopilotRunning ? 4000 : 30000,
  })

  return {
    receipts: data ?? [],
    isLoading,
    error,
    refetch,
  }
}
