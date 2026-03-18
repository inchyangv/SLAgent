import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { SimPreset } from '../types'

interface SettingsState {
  gatewayUrl: string
  sellerUrl: string
  setGatewayUrl: (url: string) => void
  setSellerUrl: (url: string) => void
  autopilotInterval: number
  setAutopilotInterval: (n: number) => void
  currentPreset: SimPreset
  setPreset: (p: SimPreset) => void
  // Polling intervals (seconds)
  balancePollInterval: number
  receiptPollInterval: number
  eventPollInterval: number
  setBalancePollInterval: (n: number) => void
  setReceiptPollInterval: (n: number) => void
  setEventPollInterval: (n: number) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      gatewayUrl: 'http://localhost:8000',
      sellerUrl: 'http://localhost:8001',
      setGatewayUrl: (url) => set({ gatewayUrl: url }),
      setSellerUrl: (url) => set({ sellerUrl: url }),
      autopilotInterval: 1,
      setAutopilotInterval: (n) => set({ autopilotInterval: n }),
      currentPreset: 'happy',
      setPreset: (p) => set({ currentPreset: p }),
      // Polling defaults
      balancePollInterval: 10,
      receiptPollInterval: 5,
      eventPollInterval: 3,
      setBalancePollInterval: (n) => set({ balancePollInterval: n }),
      setReceiptPollInterval: (n) => set({ receiptPollInterval: n }),
      setEventPollInterval: (n) => set({ eventPollInterval: n }),
    }),
    {
      name: 'slagent-402-settings',
    },
  ),
)
