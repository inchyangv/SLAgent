import { useAccount, useChainId } from 'wagmi'
import { sepolia } from 'wagmi/chains'

const SUPPORTED_CHAINS: Record<number, string> = {
  [sepolia.id]: 'Sepolia',
  84532: 'Base Sepolia',
}

export function useNetwork() {
  const { isConnected, address } = useAccount()
  const chainId = useChainId()

  const networkName = SUPPORTED_CHAINS[chainId] ?? `Chain ${chainId}`
  const isCorrectNetwork = chainId === sepolia.id || chainId === 84532

  return {
    isConnected,
    address,
    chainId,
    networkName,
    isCorrectNetwork,
  }
}
