import { create } from 'zustand'

export interface LogEntry {
  id: string
  ts: string
  msg: string
  type: 'ok' | 'err' | 'info'
}

interface LogState {
  entries: LogEntry[]
  unreadCount: number
  addLog: (msg: string, type?: LogEntry['type']) => void
  markAllRead: () => void
  clear: () => void
}

const MAX_ENTRIES = 200

export const useLogStore = create<LogState>()((set) => ({
  entries: [],
  unreadCount: 0,
  addLog: (msg, type = 'info') =>
    set((state) => {
      const entry: LogEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        ts: new Date().toISOString(),
        msg,
        type,
      }
      const entries = [entry, ...state.entries].slice(0, MAX_ENTRIES)
      return { entries, unreadCount: state.unreadCount + 1 }
    }),
  markAllRead: () => set({ unreadCount: 0 }),
  clear: () => set({ entries: [], unreadCount: 0 }),
}))
