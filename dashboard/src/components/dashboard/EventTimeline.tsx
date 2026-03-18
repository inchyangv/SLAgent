import React, { useState, useRef, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { useEvents } from '../../hooks/useEvents'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { formatDate, shortId } from '../../lib/format'
import type { Event } from '../../types'

type FilterMode = 'all' | 'violations' | 'negotiation' | 'search'

function kindVariant(kind: string): 'pass' | 'fail' | 'warning' | 'info' | 'neutral' {
  if (kind.includes('pass') || kind.includes('success')) return 'pass'
  if (kind.includes('fail') || kind.includes('error') || kind.includes('violation')) return 'fail'
  if (kind.includes('warn') || kind.includes('breach')) return 'warning'
  if (kind.includes('negot') || kind.includes('mandate')) return 'info'
  return 'neutral'
}

function EventRow({ event }: { event: Event }) {
  const payload = event.data ?? event.payload ?? {}
  const entries = Object.entries(payload).slice(0, 6)

  return (
    <div
      className="py-2 border-b last:border-0 text-xs"
      style={{ borderColor: 'var(--color-border-subtle)' }}
    >
      <div className="flex items-center gap-2 mb-1">
        <Badge variant={kindVariant(event.kind)}>{event.kind}</Badge>
        {(event.request_id || event.mandate_id) && (
          <span className="font-mono" style={{ color: 'var(--color-text-secondary)' }}>
            {event.request_id ? shortId(event.request_id) : shortId(event.mandate_id)}
          </span>
        )}
        <span className="ml-auto shrink-0" style={{ color: 'var(--color-text-muted)' }}>
          {formatDate(event.timestamp ?? event.created_at)}
        </span>
      </div>
      {entries.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 pl-1">
          {entries.map(([k, v]) => (
            <span key={k} style={{ color: 'var(--color-text-muted)' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>{k}</span>
              {'='}
              <span className="font-mono">{String(v)}</span>
            </span>
          ))}
        </div>
      )}
      {event.summary && (
        <div className="mt-0.5 pl-1" style={{ color: 'var(--color-text-secondary)' }}>
          {event.summary}
        </div>
      )}
    </div>
  )
}

export function EventTimeline() {
  const [filter, setFilter] = useState<FilterMode>('all')
  const [search, setSearch] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const { events, isLoading, refetch, isLive, setLive } = useEvents({ limit: 80 })
  const listRef = useRef<HTMLDivElement>(null)

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [events, autoScroll])

  const filtered = events.filter((ev) => {
    if (filter === 'violations') {
      return ev.kind.includes('violation') || ev.kind.includes('breach') || ev.kind.includes('fail')
    }
    if (filter === 'negotiation') {
      return ev.kind.includes('negot') || ev.kind.includes('mandate')
    }
    if (filter === 'search' && search) {
      const q = search.toLowerCase()
      return (
        ev.kind.toLowerCase().includes(q) ||
        (ev.request_id ?? '').toLowerCase().includes(q) ||
        (ev.mandate_id ?? '').toLowerCase().includes(q)
      )
    }
    return true
  })

  const filterBtns: { label: string; mode: FilterMode }[] = [
    { label: 'All Events', mode: 'all' },
    { label: 'SLA Violations', mode: 'violations' },
    { label: 'Negotiation', mode: 'negotiation' },
    { label: 'Search', mode: 'search' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Timeline</CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {filtered.length} events
          </span>
          <button
            onClick={() => {
              setLive(!isLive)
            }}
            className={`px-2 py-0.5 rounded text-xs font-medium border transition-colors ${
              isLive
                ? 'bg-green-900 text-green-300 border-green-800'
                : 'text-zinc-500 border-zinc-700 hover:text-zinc-300'
            }`}
          >
            {isLive ? '● LIVE' : 'LIVE'}
          </button>
          <button
            onClick={() => void refetch()}
            className="p-1 rounded hover:bg-zinc-800 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </CardHeader>
      <CardBody className="py-2">
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {filterBtns.map(({ label, mode }) => (
            <Button
              key={mode}
              size="sm"
              variant={filter === mode ? 'primary' : 'ghost'}
              onClick={() => setFilter(mode)}
            >
              {label}
            </Button>
          ))}
          {filter === 'search' && (
            <input
              type="text"
              placeholder="request_id or mandate_id…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-2 py-1 rounded text-xs border flex-1"
              style={{
                background: 'var(--color-bg-elevated)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          )}
          <label className="flex items-center gap-1.5 text-xs cursor-pointer ml-auto" style={{ color: 'var(--color-text-muted)' }}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-3 h-3"
            />
            Auto-scroll
          </label>
        </div>

        {/* Event list */}
        <div
          ref={listRef}
          className="overflow-y-auto"
          style={{ maxHeight: 320 }}
        >
          {filtered.length === 0 ? (
            <div className="text-xs py-4 text-center" style={{ color: 'var(--color-text-muted)' }}>
              No events
            </div>
          ) : (
            filtered.map((ev, i) => <EventRow key={ev.id ?? i} event={ev} />)
          )}
        </div>
      </CardBody>
    </Card>
  )
}
