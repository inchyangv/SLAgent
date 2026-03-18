import React from 'react'
import { RefreshCw } from 'lucide-react'
import { useEvents } from '../../hooks/useEvents'
import { useMandates } from '../../hooks/useMandates'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { formatAmount, relativeTime, shortId } from '../../lib/format'

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 border-b last:border-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <span className="text-xs shrink-0" style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span className="text-xs font-mono text-right" style={{ color: 'var(--color-text-primary)' }}>{value}</span>
    </div>
  )
}

export function NegotiationHistory() {
  const { events, isLoading, refetch } = useEvents({ kind: 'negotiation', limit: 40 })
  const { mandates } = useMandates()

  const latestMandate = mandates[0]
  const negEvents = events.filter(
    (e) => e.kind === 'negotiation' || e.kind?.includes('negot'),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Negotiation History</CardTitle>
        <button
          onClick={() => void refetch()}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Latest mandate summary */}
          <div>
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
              Latest Mandate
            </div>
            {latestMandate ? (
              <div className="text-xs">
                <KVRow label="Mandate ID" value={shortId(latestMandate.mandate_id)} />
                <KVRow label="Buyer" value={shortId(latestMandate.buyer_address)} />
                <KVRow label="Seller" value={shortId(latestMandate.seller_address)} />
                <KVRow label="Max Price" value={formatAmount(latestMandate.max_price, latestMandate.token_address ? 'USDT' : '')} />
                <KVRow label="Schema" value={latestMandate.schema_id ?? latestMandate.request_schema ?? '—'} />
                <KVRow label="Valid Until" value={relativeTime(latestMandate.valid_until)} />
              </div>
            ) : (
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                No mandates
              </div>
            )}
          </div>

          {/* Negotiation event log */}
          <div>
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
              Event Log ({negEvents.length})
            </div>
            <div className="overflow-y-auto max-h-40 flex flex-col gap-1">
              {negEvents.length === 0 ? (
                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  No negotiation events
                </div>
              ) : (
                negEvents.slice(0, 20).map((ev, i) => (
                  <div
                    key={ev.id ?? i}
                    className="flex items-start gap-2 py-1 border-b last:border-0 text-xs"
                    style={{ borderColor: 'var(--color-border-subtle)' }}
                  >
                    <Badge variant="info" className="shrink-0">{ev.kind}</Badge>
                    <span className="font-mono truncate flex-1" style={{ color: 'var(--color-text-secondary)' }}>
                      {ev.mandate_id ? shortId(ev.mandate_id) : ev.request_id ? shortId(ev.request_id) : ''}
                      {ev.summary ? ` — ${ev.summary}` : ''}
                    </span>
                    <span className="shrink-0" style={{ color: 'var(--color-text-muted)' }}>
                      {relativeTime(ev.timestamp ?? ev.created_at)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
