import { RefreshCw } from 'lucide-react'
import { useEvents } from '../../hooks/useEvents'
import { useMandates } from '../../hooks/useMandates'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { formatCurrency, shortId } from '../../lib/format'

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 border-b last:border-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <span className="text-xs shrink-0" style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span className="text-xs font-mono text-right" style={{ color: 'var(--color-text-primary)' }}>{value}</span>
    </div>
  )
}

function eventTime(ev: { ts?: number; ts_iso?: string }): string {
  if (ev.ts_iso) return new Date(ev.ts_iso).toLocaleTimeString('en-US', { hour12: false })
  if (ev.ts) return new Date(ev.ts * 1000).toLocaleTimeString('en-US', { hour12: false })
  return '—'
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
                      .map((t) => `≤${t.lte_ms}ms:${formatCurrency(t.payout, 'USDT')}`)
                      .join(' | ')}
                  />
                )}
                {latestMandate.expires_at && (
                  <KVRow label="Expires" value={latestMandate.expires_at} />
                )}
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
                    key={i}
                    className="flex items-start gap-2 py-1 border-b last:border-0 text-xs"
                    style={{ borderColor: 'var(--color-border-subtle)' }}
                  >
                    <Badge variant="info" className="shrink-0">{ev.kind}</Badge>
                    <span className="font-mono truncate flex-1" style={{ color: 'var(--color-text-secondary)' }}>
                      {ev.mandate_id ? shortId(ev.mandate_id) : ev.request_id ? shortId(ev.request_id) : ''}
                      {ev.data && Object.keys(ev.data).length > 0
                        ? ` | ${Object.entries(ev.data).slice(0, 2).map(([k, v]) => `${k}=${String(v)}`).join(' ')}`
                        : ''}
                    </span>
                    <span className="shrink-0 font-mono" style={{ color: 'var(--color-text-muted)' }}>
                      {eventTime(ev)}
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
