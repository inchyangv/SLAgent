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
    }),
    {
      name: 'slagent-402-settings',
    },
  ),
)
