import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ExternalLink, RefreshCw } from 'lucide-react'
import { useSettingsStore } from '../store/settings'
import { fetchEvents, fetchReceipt, fetchReceipts } from '../api'

import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { formatAmount, shortId } from '../lib/format'
import type { Event, Receipt } from '../types'

// ── Breach reason pill ──────────────────────────────────────────────────────

const BREACH_META: Record<string, { label: string; color: string }> = {
  BREACH_LATENCY_TIER_DOWN: { label: 'Latency Tier↓', color: 'var(--color-warning)' },
  BREACH_SCHEMA_FAIL: { label: 'Schema Fail', color: 'var(--color-error)' },
  BREACH_UPSTREAM_ERROR: { label: 'Upstream Error', color: 'var(--color-error)' },
  BREACH_TIMEOUT: { label: 'Timeout', color: 'var(--color-error)' },
  BREACH_PAYMENT_INVALID: { label: 'Payment Invalid', color: 'var(--color-error)' },
  BREACH_CHAIN_SETTLE_FAIL: { label: 'Chain Settle Fail', color: 'var(--color-error)' },
}

function BreachPill({ code }: { code: string }) {
  const meta = BREACH_META[code] ?? { label: code, color: 'var(--color-text-muted)' }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border"
      style={{ color: meta.color, borderColor: meta.color, background: `${meta.color}18` }}
    >
      {meta.label}
    </span>
  )
}

// ── Event icon / color mapping ───────────────────────────────────────────────

function getKindMeta(kind: string): { icon: string; variant: 'pass' | 'fail' | 'warning' | 'info' | 'neutral' } {
  if (kind.includes('payment') || kind.includes('settle') || kind.includes('payout'))
    return { icon: '💳', variant: 'pass' }
  if (kind.includes('fail') || kind.includes('error') || kind.includes('violation'))
    return { icon: '✗', variant: 'fail' }
  if (kind.includes('breach'))
    return { icon: '⚠', variant: 'warning' }
  if (kind.includes('negot') || kind.includes('mandate') || kind.includes('offer'))
    return { icon: '🤝', variant: 'info' }
  if (kind.includes('chain') || kind.includes('tx'))
    return { icon: '⛓', variant: 'neutral' }
  if (kind.includes('validation') || kind.includes('schema'))
    return { icon: '✓', variant: 'info' }
  if (kind.includes('receipt'))
    return { icon: '📋', variant: 'neutral' }
  if (kind.includes('pass') || kind.includes('success'))
    return { icon: '●', variant: 'pass' }
  return { icon: '·', variant: 'neutral' }
}

// ── Timeline item ────────────────────────────────────────────────────────────

function TimelineItem({ event, isFirst }: { event: Event; isFirst: boolean }) {
  const meta = getKindMeta(event.kind)
  const ts = event.ts_iso
    ? new Date(event.ts_iso).toLocaleTimeString('en-US', { hour12: false })
    : event.ts
      ? new Date(event.ts * 1000).toLocaleTimeString('en-US', { hour12: false })
      : '—'

  const summary = event.data
    ? Object.entries(event.data)
        .slice(0, 4)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join('  ·  ')
    : null

  return (
    <div className="flex gap-3">
      {/* Timeline column */}
      <div className="flex flex-col items-center">
        <div
          className="w-6 h-6 rounded-full border flex items-center justify-center shrink-0 text-xs"
          style={{
            background: 'var(--color-bg-elevated)',
            borderColor: 'var(--color-border)',
          }}
        >
          {meta.icon}
        </div>
        {!isFirst && (
          <div className="w-px flex-1 mt-1" style={{ background: 'var(--color-border-subtle)', minHeight: 12 }} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-3 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <Badge variant={meta.variant} className="text-xs">{event.kind}</Badge>
          <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>{ts}</span>
        </div>
        {summary && (
          <p className="text-xs truncate" style={{ color: 'var(--color-text-secondary)' }}>
            {summary}
          </p>
        )}
      </div>
    </div>
  )
}

// ── Receipt summary card ──────────────────────────────────────────────────────

const EXPLORER_BASE = 'https://turbulent-unique-scheat.explorer.testnet.skalenodes.com'

function ReceiptSummary({ receipt }: { receipt: Receipt }) {
  const breachReasons: string[] = [
    ...(receipt.breach_reasons ?? []),
    ...(receipt.pricing?.breach_reasons ?? []),
  ]
  const uniqueBreaches = [...new Set(breachReasons)]

  const txHash = receipt.settlement?.tx_hash
  const explorerUrl = txHash ? `${EXPLORER_BASE}/tx/${txHash}` : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Receipt</CardTitle>
        <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
          {shortId(receipt.request_id)}
        </span>
      </CardHeader>
      <CardBody className="space-y-3">
        {/* Outcome + SLA */}
        <div className="flex flex-wrap gap-2">
          <Badge variant={receipt.outcome?.success ? 'pass' : 'fail'}>
            {receipt.outcome?.success ? 'Success' : receipt.outcome?.error_code ?? 'Error'}
          </Badge>
          <Badge variant={receipt.validation?.overall_pass ? 'pass' : 'fail'}>
            {receipt.validation?.overall_pass ? 'Valid' : 'Schema Fail'}
          </Badge>
          {uniqueBreaches.map((b) => <BreachPill key={b} code={b} />)}
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Latency', value: receipt.metrics?.latency_ms != null ? `${receipt.metrics.latency_ms}ms` : '—' },
            { label: 'TTFT', value: receipt.metrics?.ttft_ms != null ? `${receipt.metrics.ttft_ms}ms` : '—' },
            { label: 'Payout', value: receipt.pricing?.computed_payout != null ? formatAmount(receipt.pricing.computed_payout) : '—' },
            { label: 'Refund', value: receipt.pricing?.computed_refund != null ? formatAmount(receipt.pricing.computed_refund) : '—' },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded p-2 border"
              style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border-subtle)' }}
            >
              <div className="text-xs uppercase tracking-wide mb-0.5" style={{ color: 'var(--color-text-muted)' }}>{label}</div>
              <div className="text-sm font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Rule applied */}
        {receipt.pricing?.rule_applied && (
          <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Rule: <span className="font-mono">{receipt.pricing.rule_applied}</span>
          </div>
        )}

        {/* Attestation */}
        {receipt.attestations && (
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            <span>Attestations:</span>
            <Badge variant={receipt.attestations.complete ? 'pass' : 'warning'}>
              {receipt.attestations.count ?? 0}/3
              {receipt.attestations.complete ? ' ✓' : ''}
            </Badge>
            {receipt.attestations.parties_signed?.map((p) => (
              <span key={p} className="font-mono">{p}</span>
            ))}
          </div>
        )}

        {/* TX hash */}
        {txHash && (
          <div className="flex items-center gap-1 text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
            <span className="truncate max-w-xs">{txHash}</span>
            {explorerUrl && (
              <a href={explorerUrl} target="_blank" rel="noopener noreferrer"
                className="shrink-0 hover:text-blue-400 transition-colors">
                <ExternalLink size={11} />
              </a>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

// ── Recent requests selector ──────────────────────────────────────────────────

function RecentPicker({ onSelect }: { onSelect: (id: string) => void }) {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const { data } = useQuery<Receipt[]>({
    queryKey: ['receipts', gatewayUrl, 20],
    queryFn: () => fetchReceipts(gatewayUrl, 20),
    staleTime: 10_000,
  })
  const receipts = data ?? []
  if (receipts.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <span className="text-xs self-center" style={{ color: 'var(--color-text-muted)' }}>Recent:</span>
      {receipts.slice(0, 8).map((r) => (
        <button
          key={r.request_id}
          onClick={() => onSelect(r.request_id)}
          className="px-2 py-0.5 rounded border text-xs font-mono transition-colors hover:border-zinc-500"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
        >
          {shortId(r.request_id)}
        </button>
      ))}
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export function HistoryPage() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const [searchInput, setSearchInput] = useState('')
  const [activeId, setActiveId] = useState('')
  const [slaViolationOnly, setSlaViolationOnly] = useState(false)

  function handleSearch() {
    const id = searchInput.trim()
    if (id) setActiveId(id)
  }

  // Fetch events for selected request
  const {
    data: eventsData,
    isLoading: eventsLoading,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ['history-events', gatewayUrl, activeId],
    queryFn: () => fetchEvents(gatewayUrl, undefined, 200, activeId || undefined),
    enabled: !!activeId,
  })

  // Fetch receipt for selected request
  const { data: receipt } = useQuery<Receipt>({
    queryKey: ['history-receipt', gatewayUrl, activeId],
    queryFn: () => fetchReceipt(gatewayUrl, activeId),
    enabled: !!activeId,
  })

  const events: Event[] = eventsData?.events ?? []

  // Filter: SLA violation only
  const displayed = useMemo(() => {
    if (!slaViolationOnly) return events
    return events.filter((ev) =>
      ev.kind.includes('breach') ||
      ev.kind.includes('fail') ||
      ev.kind.includes('error') ||
      ev.kind.includes('violation') ||
      ev.kind.includes('timeout'),
    )
  }, [events, slaViolationOnly])

  return (
    <div className="max-w-screen-xl mx-auto px-4 py-6 flex flex-col gap-6">

      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
          SLA History
        </h1>
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Search by request_id or mandate_id to replay negotiation → settlement timeline
        </p>
      </div>

      {/* Search */}
      <div className="flex flex-col gap-2">
        <div className="flex gap-2 items-end">
          <Input
            label="Request ID / Mandate ID"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 max-w-md font-mono text-xs"
            placeholder="req_… or 0x…"
          />
          <Button onClick={handleSearch} size="sm" disabled={!searchInput.trim()}>
            <Search size={13} />
            Search
          </Button>
        </div>
        <RecentPicker onSelect={(id) => { setSearchInput(id); setActiveId(id) }} />
      </div>

      {activeId && (
        <>
          {/* Receipt summary */}
          {receipt && <ReceiptSummary receipt={receipt} />}

          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Event Timeline</CardTitle>
              <div className="flex items-center gap-2">
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {displayed.length} events
                  {slaViolationOnly ? ' (violations only)' : ''}
                </span>
                {/* SLA violation filter */}
                <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--color-text-muted)' }}>
                  <input
                    type="checkbox"
                    checked={slaViolationOnly}
                    onChange={(e) => setSlaViolationOnly(e.target.checked)}
                    className="w-3 h-3"
                  />
                  SLA violation only
                </label>
                <button
                  onClick={() => void refetchEvents()}
                  className="p-1 rounded hover:bg-zinc-800 transition-colors"
                  style={{ color: 'var(--color-text-muted)' }}
                  title="Refresh"
                >
                  <RefreshCw size={13} className={eventsLoading ? 'animate-spin' : ''} />
                </button>
              </div>
            </CardHeader>
            <CardBody>
              {eventsLoading ? (
                <div className="flex items-center gap-2 py-6" style={{ color: 'var(--color-text-muted)' }}>
                  <RefreshCw size={14} className="animate-spin" />
                  <span className="text-xs">Loading events…</span>
                </div>
              ) : displayed.length === 0 ? (
                <div className="flex flex-col items-center py-8 gap-2">
                  <span className="text-2xl">📭</span>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {events.length === 0
                      ? 'No events found for this ID'
                      : 'No SLA violations in this request'}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col">
                  {displayed.map((ev, i) => (
                    <TimelineItem
                      key={`${ev.kind}-${ev.ts}-${i}`}
                      event={ev}
                      isFirst={i === displayed.length - 1}
                    />
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}

      {!activeId && (
        <div
          className="flex flex-col items-center py-16 gap-3 rounded-lg border border-dashed"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
        >
          <Search size={32} strokeWidth={1} />
          <p className="text-sm">Enter a request ID to replay its SLA timeline</p>
        </div>
      )}
    </div>
  )
}
