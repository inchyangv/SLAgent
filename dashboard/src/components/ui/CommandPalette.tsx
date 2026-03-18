import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useAutopilotStore } from '../../store/autopilot'

interface Command {
  id: string
  label: string
  description?: string
  icon: string
  action: () => void
  group: 'navigation' | 'actions'
}

function fuzzyMatch(query: string, text: string): boolean {
  if (!query) return true
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  // Simple: all chars of query appear in order in text
  let qi = 0
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) qi++
  }
  return qi === q.length
}

function highlightMatch(label: string, query: string): React.ReactNode {
  if (!query) return label
  const q = query.toLowerCase()
  const l = label.toLowerCase()
  const result: React.ReactNode[] = []
  let qi = 0
  let lastMatch = 0
  for (let i = 0; i < l.length && qi < q.length; i++) {
    if (l[i] === q[qi]) {
      if (i > lastMatch) result.push(label.slice(lastMatch, i))
      result.push(
        <span key={i} style={{ color: 'var(--color-accent)', fontWeight: 600 }}>
          {label[i]}
        </span>,
      )
      lastMatch = i + 1
      qi++
    }
  }
  if (lastMatch < label.length) result.push(label.slice(lastMatch))
  return result
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const toggle = useAutopilotStore((s) => s.toggle)
  const isRunning = useAutopilotStore((s) => s.isRunning)

  const commands: Command[] = [
    { id: 'nav-dashboard', label: 'Go to Dashboard', icon: '🏠', group: 'navigation', action: () => { navigate('/'); onClose() } },
    { id: 'nav-receipts', label: 'Go to Receipts', icon: '📋', group: 'navigation', action: () => { navigate('/receipts'); onClose() } },
    { id: 'nav-disputes', label: 'Go to Disputes', icon: '⚖️', group: 'navigation', action: () => { navigate('/disputes'); onClose() } },
    { id: 'nav-settings', label: 'Go to Settings', icon: '⚙️', group: 'navigation', action: () => { navigate('/settings'); onClose() } },
    { id: 'action-autopilot', label: isRunning ? 'Stop Autopilot' : 'Start Autopilot', icon: isRunning ? '⏹' : '▶', group: 'actions', action: () => { toggle(); onClose() } },
  ]

  const filtered = commands.filter(
    (c) => fuzzyMatch(query, c.label) || (c.description && fuzzyMatch(query, c.description)),
  )

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])

  // Reset selection when filtered changes
  useEffect(() => {
    setSelectedIdx(0)
  }, [query])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && filtered[selectedIdx]) {
        filtered[selectedIdx].action()
      } else if (e.key === 'Escape') {
        onClose()
      }
    },
    [filtered, selectedIdx, onClose],
  )

  if (!open) return null

  const groups = ['navigation', 'actions'] as const
  const grouped = groups.map((g) => ({
    group: g,
    items: filtered.filter((c) => c.group === g),
  })).filter((g) => g.items.length > 0)

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[20vh] px-4 fade-in"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-lg rounded-xl border shadow-2xl overflow-hidden"
        style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-strong)' }}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-3 px-4 py-3 border-b"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <Search size={16} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search pages, actions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--color-text-primary)' }}
          />
          <kbd
            className="px-1.5 py-0.5 rounded text-xs border"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)', background: 'var(--color-bg-secondary)' }}
          >
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="py-2" style={{ maxHeight: 360, overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
              No results for "{query}"
            </div>
          ) : (
            grouped.map(({ group, items }) => {
              return (
                <div key={group}>
                  <div
                    className="px-4 py-1 text-xs uppercase tracking-widest"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {group}
                  </div>
                  {items.map((cmd) => {
                    const globalIdx = filtered.indexOf(cmd)
                    const isSelected = globalIdx === selectedIdx
                    return (
                      <button
                        key={cmd.id}
                        onClick={cmd.action}
                        onMouseEnter={() => setSelectedIdx(globalIdx)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                        style={{
                          background: isSelected ? 'rgba(74,158,255,0.1)' : 'transparent',
                          borderLeft: isSelected ? '2px solid var(--color-accent)' : '2px solid transparent',
                        }}
                      >
                        <span className="text-base w-5 text-center shrink-0">{cmd.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                            {highlightMatch(cmd.label, query)}
                          </div>
                          {cmd.description && (
                            <div className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
                              {cmd.description}
                            </div>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )
            })
          )}
        </div>

        {/* Footer hint */}
        <div
          className="flex items-center gap-4 px-4 py-2 border-t text-xs"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
        >
          <span><kbd className="font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono">↵</kbd> select</span>
          <span><kbd className="font-mono">Esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}
