import { useAccount, useChainId } from 'wagmi'
import { sepolia } from 'wagmi/chains'

const SUPPORTED_CHAINS: Record<number, string> = {
  [sepolia.id]: 'Sepolia',
  84532: 'Base Sepolia',
}

const EXPLORERS: Record<number, string> = {
  [sepolia.id]: 'https://sepolia.etherscan.io',
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

export function useNetwork() {
  const { isConnected, address } = useAccount()
  const chainId = useChainId()

  const networkName = SUPPORTED_CHAINS[chainId] ?? `Chain ${chainId}`
  const isCorrectNetwork = chainId === sepolia.id || chainId === 84532
  const explorerBase = EXPLORERS[chainId] ?? null

  return {
    isConnected,
    address,
    chainId,
    networkName,
    isCorrectNetwork,
    explorerBase,
  }
}
