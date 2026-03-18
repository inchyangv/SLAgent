import { useState } from 'react'
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { useEvents } from '../../hooks/useEvents'
import { useMandates } from '../../hooks/useMandates'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { formatCurrency, shortId } from '../../lib/format'
import type { Event } from '../../types'

function eventTime(ev: { ts?: number; ts_iso?: string }): string {
  if (ev.ts_iso) return new Date(ev.ts_iso).toLocaleTimeString('en-US', { hour12: false })
  if (ev.ts) return new Date(ev.ts * 1000).toLocaleTimeString('en-US', { hour12: false })
  return '—'
}

function getActor(kind: string): { label: string; side: 'left' | 'center' | 'right' } {
  if (kind.includes('buyer')) return { label: 'Buyer', side: 'left' }
  if (kind.includes('seller')) return { label: 'Seller', side: 'right' }
  if (kind.includes('gateway') || kind.includes('mandate')) return { label: 'Gateway', side: 'center' }
  return { label: '·', side: 'center' }
}

function NegBubble({ event }: { event: Event }) {
  const actor = getActor(event.kind)
  const ts = eventTime(event)
  const summary = event.data
    ? Object.entries(event.data)
        .slice(0, 3)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join('  ·  ')
    : null

  const isLeft = actor.side === 'left'
  const isCenter = actor.side === 'center'

  return (
    <div
      className={`flex flex-col gap-0.5 ${isCenter ? 'items-center' : isLeft ? 'items-start' : 'items-end'}`}
    >
      {isCenter ? (
        /* Center event (Gateway / Mandate) */
        <div
          className="px-3 py-1.5 rounded-full border text-xs text-center max-w-[85%]"
          style={{
            background: 'rgba(74,158,255,0.08)',
            borderColor: 'var(--color-accent)',
            color: 'var(--color-accent)',
          }}
        >
          <span className="font-semibold">{actor.label}</span>
          {' · '}
          <span className="font-mono">{event.kind}</span>
          {event.mandate_id && (
            <span className="ml-1 font-mono opacity-60">[{shortId(event.mandate_id)}]</span>
          )}
        </div>
      ) : (
        /* Buyer (left) / Seller (right) bubble */
        <div
          className={`px-3 py-2 rounded-2xl max-w-[85%] ${isLeft ? 'rounded-tl-sm' : 'rounded-tr-sm'}`}
          style={{
            background: isLeft ? 'var(--color-bg-elevated)' : 'rgba(74,158,255,0.10)',
            border: `1px solid ${isLeft ? 'var(--color-border)' : 'rgba(74,158,255,0.25)'}`,
          }}
        >
          <div className="flex items-center gap-1.5 mb-0.5">
            <span
              className="text-xs font-semibold"
              style={{ color: isLeft ? 'var(--color-text-secondary)' : 'var(--color-accent)' }}
            >
              {actor.label}
            </span>
            <Badge variant="neutral" className="text-xs">{event.kind}</Badge>
          </div>
          {summary && (
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {summary}
            </p>
          )}
        </div>
      )}
      <span className="text-xs font-mono px-1" style={{ color: 'var(--color-text-muted)', fontSize: '10px' }}>
        {ts}
      </span>
    </div>
  )
}

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex items-start justify-between gap-4 py-1.5 border-b last:border-0"
      style={{ borderColor: 'var(--color-border-subtle)' }}
    >
      <span className="text-xs shrink-0" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </span>
      <span className="text-xs font-mono text-right" style={{ color: 'var(--color-text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

export function NegotiationHistory() {
  const { events, isLoading, refetch } = useEvents({ kind: 'negotiation', limit: 40 })
  const { mandates } = useMandates()
  const [mandateOpen, setMandateOpen] = useState(false)

  const latestMandate = mandates[0]
  const negEvents = events.filter(
    (e) => e.kind === 'negotiation' || e.kind?.includes('negot') || e.kind?.includes('offer') || e.kind?.includes('mandate'),
  )

  // Check if mandate was agreed (last event has mandate_id and no 'reject' in kind)
  const agreementReached = latestMandate?.mandate_id != null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Negotiation</CardTitle>
        <button
          onClick={() => void refetch()}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </CardHeader>
      <CardBody>
        {/* Chat-style conversation */}
        <div className="overflow-y-auto flex flex-col gap-2.5 mb-3" style={{ maxHeight: 240 }}>
          {negEvents.length === 0 ? (
            <div className="flex flex-col items-center py-6 gap-2">
              <span className="text-2xl">🤝</span>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                No negotiation events
              </p>
            </div>
          ) : (
            negEvents.slice(0, 20).map((ev, i) => <NegBubble key={i} event={ev} />)
          )}
        </div>

        {/* Agreement banner */}
        {agreementReached && (
          <div
            className="flex items-center justify-between px-3 py-2 rounded-md mb-3"
            style={{
              background: 'rgba(34,197,94,0.08)',
              border: '1px solid rgba(34,197,94,0.25)',
            }}
          >
            <div className="flex items-center gap-2">
              <span>✅</span>
              <span className="text-xs font-semibold" style={{ color: 'var(--color-success)' }}>
                Agreement Reached
              </span>
            </div>
            <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
              {shortId(latestMandate?.mandate_id)}
            </span>
          </div>
        )}

        {/* Mandate details accordion */}
        {latestMandate && (
          <div>
            <button
              onClick={() => setMandateOpen((v) => !v)}
              className="w-full flex items-center justify-between text-xs py-1.5 transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <span className="font-medium uppercase tracking-wide">Mandate Details</span>
              {mandateOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {mandateOpen && (
              <div className="mt-1">
                <KVRow label="Mandate ID" value={shortId(latestMandate.mandate_id)} />
                <KVRow label="Buyer" value={shortId(latestMandate.buyer)} />
                <KVRow label="Seller" value={shortId(latestMandate.seller)} />
                <KVRow label="Max Price" value={formatCurrency(latestMandate.max_price, 'USDT')} />
                <KVRow label="Base Pay" value={formatCurrency(latestMandate.base_pay, 'USDT')} />
                <KVRow label="Timeout" value={latestMandate.timeout_ms ? `${latestMandate.timeout_ms}ms` : '—'} />
                {latestMandate.validators && latestMandate.validators.length > 0 && (
                  <KVRow
                    label="Validators"
                    value={latestMandate.validators.map((v) => `${v.type}${v.schema_id ? `:${v.schema_id}` : ''}`).join(', ')}
                  />
                )}
                {latestMandate.bonus_rules?.tiers && latestMandate.bonus_rules.tiers.length > 0 && (
                  <KVRow
                    label="Tiers"
                    value={latestMandate.bonus_rules.tiers
                      .map((t) => `≤${t.lte_ms}ms: ${formatCurrency(t.payout, 'USDT')}`)
                      .join(' | ')}
                  />
                )}
                {latestMandate.expires_at && (
                  <KVRow label="Expires" value={latestMandate.expires_at} />
                )}
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
