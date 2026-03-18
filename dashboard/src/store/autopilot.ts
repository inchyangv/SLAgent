import { create } from 'zustand'
import { runDemo } from '../api'
import { useSettingsStore } from './settings'
import { useLogStore } from './log'
import { useToastStore } from './toast'
import { PRESETS } from '../types'
import type { DemoRunResult } from '../types'

interface AutopilotState {
  isRunning: boolean
  lastResult: DemoRunResult | null
  tickCount: number
  _intervalId: ReturnType<typeof setInterval> | null

  start: () => void
  stop: () => void
  toggle: () => void
  _tick: () => Promise<void>
}

export const useAutopilotStore = create<AutopilotState>()((set, get) => ({
  isRunning: false,
  lastResult: null,
  tickCount: 0,
  _intervalId: null,

  _tick: async () => {
    const { gatewayUrl, sellerUrl, currentPreset } =
      useSettingsStore.getState()
    const addLog = useLogStore.getState().addLog
    const addToast = useToastStore.getState().addToast

    if (!get().isRunning) return

    const preset = PRESETS[currentPreset]
    try {
      const res = await runDemo(gatewayUrl, {
        ...preset,
        seller_url: sellerUrl,
        negotiate: true,
      })
      const result = res.results?.[0] ?? null
      set((s) => ({ lastResult: result, tickCount: s.tickCount + 1 }))
      if (result) {
        const status = result.sla_status ?? (result.valid ? 'pass' : 'fail')
        addLog(
          `[tick] ${status.toUpperCase()} | req=${result.request_id?.slice(0, 8) ?? '—'} | latency=${result.latency_ms ?? '—'}ms`,
          status === 'pass' ? 'ok' : status === 'fail' ? 'err' : 'info',
        )
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[tick] ERROR: ${msg}`, 'err')
      addToast(`Autopilot tick failed: ${msg}`, 'error')
    }
  },

  start: () => {
    if (get().isRunning) return
    const addLog = useLogStore.getState().addLog
    const { autopilotInterval } = useSettingsStore.getState()

    set({ isRunning: true })
    addLog('[autopilot] started', 'info')

    // immediate tick
    void get()._tick()

    const intervalMs = Math.max(1, autopilotInterval) * 1000
    const id = setInterval(() => {
      void get()._tick()
    }, intervalMs)

    set({ _intervalId: id })
  },

  stop: () => {
    const { _intervalId } = get()
    if (_intervalId) {
      clearInterval(_intervalId)
    }
    set({ isRunning: false, _intervalId: null })
    useLogStore.getState().addLog('[autopilot] stopped', 'info')
  },

  toggle: () => {
    if (get().isRunning) {
      get().stop()
    } else {
      get().start()
    }
  },
}))
