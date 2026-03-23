import { useQuery } from '@tanstack/react-query'
import { useSettingsStore } from '../store/settings'

const CHAIN_ID = 11155111 // Sepolia

const SUPPORTED_CHAINS: Record<number, string> = {
  [CHAIN_ID]: 'Sepolia',
  84532: 'Base Sepolia',
}

const EXPLORERS: Record<number, string> = {
  [CHAIN_ID]: 'https://sepolia.etherscan.io',
  84532: 'https://sepolia.basescan.org',
}

export function txExplorerUrl(chainId: number, txHash: string): string | null {
  const base = EXPLORERS[chainId]
  if (!base || !txHash) return null
  return `${base}/tx/${txHash}`
}

export function addrExplorerUrl(chainId: number, address: string): string | null {
  const base = EXPLORERS[chainId]
  if (!base || !address) return null
  return `${base}/address/${address}`
}

export interface WdkRole {
  address?: string
  balance?: string | number
}

/**
 * Checks WDK sidecar connectivity via the gateway's balances endpoint.
 * Returns all role wallet addresses managed by WDK.
 */
export function useNetwork() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)

  const { data, isError } = useQuery({
    queryKey: ['wdk-status', gatewayUrl],
    queryFn: async () => {
      const res = await fetch(`${gatewayUrl}/v1/balances`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    refetchInterval: 15000,
    staleTime: 12000,
    retry: 1,
  })

  const roles: Record<string, WdkRole> = data?.roles ?? {}
  const buyerAddress: string | undefined = roles.buyer?.address
  const isConnected = !isError && !!buyerAddress

  return {
    isConnected,
    address: buyerAddress,
    roles,
    chainId: CHAIN_ID,
    networkName: SUPPORTED_CHAINS[CHAIN_ID]!,
    isCorrectNetwork: true,
    explorerBase: EXPLORERS[CHAIN_ID] ?? null,
  }
}
