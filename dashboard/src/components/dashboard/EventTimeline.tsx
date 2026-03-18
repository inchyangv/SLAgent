import React, { useState, useRef, useEffect } from 'react'
import { RefreshCw, Expand } from 'lucide-react'
import { useEvents } from '../../hooks/useEvents'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { shortId } from '../../lib/format'
import type { Event } from '../../types'

// ── Icon + color mapping per event kind ─────────────────────────────────────

interface KindMeta {
  icon: string
  label: string
  variant: 'pass' | 'fail' | 'warning' | 'info' | 'neutral'
}

function getKindMeta(kind: string): KindMeta {
  if (kind.includes('payment') || kind.includes('settle') || kind.includes('payout'))
    return { icon: '💳', label: 'payment', variant: 'pass' }
  if (kind.includes('validation') || kind.includes('schema') || kind.includes('valid'))
    return { icon: '✓', label: 'validation', variant: 'info' }
  if (kind.includes('fail') || kind.includes('error') || kind.includes('violation'))
    return { icon: '✗', label: 'violation', variant: 'fail' }
  if (kind.includes('breach'))
    return { icon: '⚠', label: 'breach', variant: 'warning' }
  if (kind.includes('negot') || kind.includes('mandate') || kind.includes('offer'))
    return { icon: '🤝', label: 'negotiation', variant: 'info' }
  if (kind.includes('chain') || kind.includes('tx') || kind.includes('block'))
    return { icon: '⛓', label: 'chain', variant: 'neutral' }
  if (kind.includes('pricing') || kind.includes('price'))
    return { icon: '$', label: 'pricing', variant: 'neutral' }
  if (kind.includes('receipt'))
    return { icon: '📋', label: 'receipt', variant: 'neutral' }
  if (kind.includes('pass') || kind.includes('success'))
    return { icon: '●', label: 'success', variant: 'pass' }
  return { icon: '·', label: 'event', variant: 'neutral' }
}

// ── Filter chip types ─────────────────────────────────────────────────────

const FILTER_CHIPS = ['all', 'payment', 'validation', 'violation', 'negotiation', 'chain', 'pricing'] as const
type FilterChip = typeof FILTER_CHIPS[number]

function matchesChip(kind: string, chip: FilterChip): boolean {
  if (chip === 'all') return true
  const meta = getKindMeta(kind)
  return meta.label === chip
}

// ── Legend ────────────────────────────────────────────────────────────────

const LEGEND: { icon: string; label: string; color: string }[] = [
  { icon: '💳', label: 'payment', color: 'var(--color-success)' },
  { icon: '✓', label: 'validation', color: 'var(--color-info)' },
  { icon: '✗', label: 'violation', color: 'var(--color-error)' },
  { icon: '⚠', label: 'breach', color: 'var(--color-warning)' },
  { icon: '🤝', label: 'negotiation', color: 'var(--color-accent)' },
  { icon: '⛓', label: 'chain', color: 'var(--color-text-muted)' },
]

// ── Event card ────────────────────────────────────────────────────────────

function EventCard({ event }: { event: Event }) {
  const meta = getKindMeta(event.kind)
  const tsDisplay = event.ts_iso
    ? new Date(event.ts_iso).toLocaleTimeString('en-US', { hour12: false })
    : event.ts
      ? new Date(event.ts * 1000).toLocaleTimeString('en-US', { hour12: false })
      : '—'

  const refId = event.request_id
    ? shortId(event.request_id)
    : event.mandate_id
      ? shortId(event.mandate_id)
      : null

  // Build summary text from data
  const dataSummary = event.data
    ? Object.entries(event.data)
        .slice(0, 3)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join('  ·  ')
    : null

  return (
    <div
      className="flex items-start gap-3 py-2.5 px-3 rounded-md border transition-colors hover:border-zinc-600"
      style={{
        background: 'var(--color-bg-primary)',
        borderColor: 'var(--color-border-subtle)',
      }}
    >
      {/* Icon */}
      <span className="text-base shrink-0 leading-none mt-0.5">{meta.icon}</span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <Badge variant={meta.variant} className="text-xs">{event.kind}</Badge>
          {refId && (
            <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
              {refId}
            </span>
          )}
        </div>
        {dataSummary && (
          <p className="text-xs truncate" style={{ color: 'var(--color-text-secondary)' }}>
            {dataSummary}
          </p>
        )}
      </div>

      {/* Timestamp */}
      <span className="text-xs font-mono shrink-0" style={{ color: 'var(--color-text-muted)' }}>
        {tsDisplay}
      </span>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function EventTimeline() {
  const [chip, setChip] = useState<FilterChip>('all')
  const [expanded, setExpanded] = useState(false)
  const [showLegend, setShowLegend] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const { events, isLoading, refetch, isLive, setLive } = useEvents({ limit: 80 })
  const listRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [events, autoScroll])

  const filtered = events.filter((ev) => matchesChip(ev.kind, chip))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Timeline</CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {filtered.length} events
          </span>
          <button
            onClick={() => setShowLegend((v) => !v)}
            className="text-xs px-1.5 py-0.5 rounded border transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-muted)',
            }}
          >
            Legend
          </button>
          <button
            onClick={() => {
              setLive(!isLive)
            }}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border transition-colors ${
              isLive
                ? 'bg-green-900 text-green-300 border-green-800'
                : 'text-zinc-500 border-zinc-700 hover:text-zinc-300'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-green-400 animate-pulse' : 'bg-zinc-600'}`}
            />
            Live
          </button>
          <button
            onClick={() => void refetch()}
            className="p-1 rounded hover:bg-zinc-800 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
            title="Refresh"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1 rounded hover:bg-zinc-800 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
            title={expanded ? 'Collapse' : 'Expand'}
          >
            <Expand size={13} />
          </button>
        </div>
      </CardHeader>

      <CardBody className="py-2">
        {/* Legend */}
        {showLegend && (
          <div className="flex flex-wrap gap-3 mb-3 px-1 py-2 rounded border" style={{ borderColor: 'var(--color-border-subtle)', background: 'var(--color-bg-primary)' }}>
            {LEGEND.map((l) => (
              <div key={l.label} className="flex items-center gap-1.5 text-xs">
                <span>{l.icon}</span>
                <span style={{ color: l.color }}>{l.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Filter chips */}
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          {FILTER_CHIPS.map((c) => (
            <button
              key={c}
              onClick={() => setChip(c)}
              className="px-2.5 py-1 rounded-full text-xs font-medium border capitalize transition-colors"
              style={
                chip === c
                  ? {
                      background: 'var(--color-accent)',
                      borderColor: 'var(--color-accent)',
                      color: '#fff',
                    }
                  : {
                      background: 'transparent',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-muted)',
                    }
              }
            >
              {c}
            </button>
          ))}
          <label
            className="flex items-center gap-1.5 text-xs cursor-pointer ml-auto"
            style={{ color: 'var(--color-text-muted)' }}
          >
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
          className="overflow-y-auto flex flex-col gap-1.5"
          style={{ maxHeight: expanded ? 600 : 320 }}
        >
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center py-8 gap-2">
              <span className="text-2xl">📭</span>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                No events recorded
              </p>
            </div>
          ) : (
            filtered.map((ev, i) => <EventCard key={i} event={ev} />)
          )}
        </div>
      </CardBody>
    </Card>
  )
}
