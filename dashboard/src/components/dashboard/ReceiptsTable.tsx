import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Skeleton } from '../ui/Skeleton'
import { ReceiptDetailModal } from './ReceiptDetailModal'
import { formatCurrency, formatLatency, shortId, shortHash } from '../../lib/format'
import type { Receipt } from '../../types'

type FilterTab = 'all' | 'pass' | 'fail'

interface ReceiptsTableProps {
  receipts: Receipt[]
  isLoading: boolean
  onRefresh: () => void
}

const TOKEN = 'USDT'

export function ReceiptsTable({ receipts, isLoading, onRefresh }: ReceiptsTableProps) {
  const [filter, setFilter] = useState<FilterTab>('all')
  const [selected, setSelected] = useState<Receipt | null>(null)
  const [focusIdx, setFocusIdx] = useState<number>(-1)

  const filtered = receipts.filter((r) => {
    if (filter === 'pass') return r.validation?.overall_pass
    if (filter === 'fail') return !r.validation?.overall_pass
    return true
  })

  const passCount = receipts.filter((r) => r.validation?.overall_pass).length
  const failCount = receipts.length - passCount

  const tabs: { key: FilterTab; label: string; count: number }[] = [
    { key: 'all', label: 'All', count: receipts.length },
    { key: 'pass', label: 'Pass', count: passCount },
    { key: 'fail', label: 'Fail', count: failCount },
  ]

  // Keyboard navigation: J/K to move, Enter to open, Esc to close
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (selected) {
        if (e.key === 'Escape') setSelected(null)
        return
      }
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        setFocusIdx((i) => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusIdx((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && focusIdx >= 0 && filtered[focusIdx]) {
        setSelected(filtered[focusIdx])
      }
    },
    [selected, filtered, focusIdx],
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <CardTitle>Receipts</CardTitle>
          <div className="flex gap-1">
            {tabs.map(({ key, label, count }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-2.5 py-0.5 rounded text-xs font-medium transition-colors ${
                  filter === key
                    ? 'bg-blue-900 text-blue-300'
                    : 'hover:text-zinc-300'
                }`}
                style={filter !== key ? { color: 'var(--color-text-muted)' } : undefined}
              >
                {label} ({count})
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={onRefresh}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          title="Refresh"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </CardHeader>

      <CardBody className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {[
                  'Request ID', 'Latency', 'Valid', 'Payout', 'Refund',
                  'Rule', 'LLM Policy', 'Breaches', 'Attest', 'Hash',
                ].map((h) => (
                  <th
                    key={h}
                    className="px-3 py-2 text-left font-semibold uppercase tracking-wide whitespace-nowrap"
                    style={{ color: 'var(--color-text-muted)', fontSize: '10px' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 10 }).map((_, j) => (
                        <td key={j} className="px-3 py-2">
                          <Skeleton height={14} width={j === 0 ? 80 : 40} />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((r, i) => {
                    const isFocused = i === focusIdx
                    const vpass = r.validation?.overall_pass
                    const payout = r.pricing?.computed_payout ?? '0'
                    const refund = r.pricing?.computed_refund ?? '0'
                    const maxP = parseInt(r.pricing?.max_price ?? '0', 10)
                    const payoutInt = parseInt(payout, 10)
                    const latency = r.metrics?.latency_ms
                    const rule = r.pricing?.rule_applied
                    const hash = r.hashes?.receipt_hash ?? r.settlement?.tx_hash
                    const parties = r.attestations?.parties_signed ?? []
                    const attestComplete = r.attestations?.complete
                    const breaches = r.breach_reasons ?? r.pricing?.breach_reasons ?? []
                    const llmPolicy = r.outcome?.llm_policy
                    const llmActive = llmPolicy?.mode === 'llm'

                    // Payout badge variant
                    let payBadge: 'full' | 'partial' | 'fail' = 'fail'
                    if (payoutInt === maxP && maxP > 0) payBadge = 'full'
                    else if (payoutInt > 0) payBadge = 'partial'

                    return (
                      <tr
                        key={r.request_id ?? i}
                        className="border-b cursor-pointer transition-colors"
                        style={{
                          borderColor: 'var(--color-border-subtle)',
                          background: isFocused ? 'rgba(74,158,255,0.07)' : '',
                          outline: isFocused ? '1px solid rgba(74,158,255,0.4)' : 'none',
                          outlineOffset: '-1px',
                        }}
                        onMouseEnter={(e) => {
                          if (!isFocused) e.currentTarget.style.background = 'var(--color-bg-elevated)'
                        }}
                        onMouseLeave={(e) => {
                          if (!isFocused) e.currentTarget.style.background = ''
                        }}
                        onClick={() => { setFocusIdx(i); setSelected(r) }}
                        aria-selected={isFocused}
                        role="row"
                      >
                        <td
                          className="px-3 py-2 font-mono"
                          style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}
                          title={r.request_id}
                        >
                          {shortId(r.request_id)}
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {formatLatency(latency)}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={vpass ? 'pass' : 'fail'}>
                            {vpass ? 'PASS' : 'FAIL'}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          <Badge variant={payBadge}>
                            {formatCurrency(payout, TOKEN)}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap" style={{ color: 'var(--color-text-secondary)' }}>
                          {formatCurrency(refund, TOKEN)}
                        </td>
                        <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-muted)', fontSize: '11px' }}>
                          {rule ?? '—'}
                        </td>
                        <td className="px-3 py-2">
                          {llmActive ? (
                            <div className="flex items-center gap-1">
                              <Badge variant={llmPolicy.sla_pass ? 'pass' : 'fail'}>
                                {llmPolicy.sla_pass ? 'PASS' : 'FAIL'}
                              </Badge>
                              {llmPolicy.confidence !== undefined && (
                                <span className="font-mono" style={{ color: 'var(--color-text-muted)', fontSize: '10px' }}>
                                  {(llmPolicy.confidence * 100).toFixed(0)}%
                                </span>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {breaches.length > 0 ? (
                            <div className="flex flex-wrap gap-0.5">
                              {breaches.map((b, bi) => (
                                <Badge key={bi} variant="fail" className="text-xs">
                                  {String(b).replace('BREACH_', '')}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-0.5">
                            {(['buyer', 'seller', 'gateway'] as const).map((role, idx) => {
                              const signed = parties.includes(role)
                              return (
                                <span
                                  key={role}
                                  className="w-4 h-4 rounded-sm flex items-center justify-center font-mono"
                                  style={{
                                    background: signed ? 'var(--color-success)' : 'var(--color-border)',
                                    color: signed ? '#fff' : 'var(--color-text-muted)',
                                    fontSize: 9,
                                  }}
                                  title={`${role}: ${signed ? 'signed' : 'missing'}`}
                                >
                                  {['B', 'S', 'G'][idx]}
                                </span>
                              )
                            })}
                            <span
                              className="ml-1 font-mono text-xs"
                              style={{
                                color: attestComplete ? 'var(--color-success)' : 'var(--color-text-muted)',
                              }}
                            >
                              {parties.length}/3
                            </span>
                          </div>
                        </td>
                        <td
                          className="px-3 py-2 font-mono"
                          style={{ color: 'var(--color-text-muted)', fontSize: '11px' }}
                          title={hash}
                        >
                          {shortHash(hash)}
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>

          {!isLoading && filtered.length === 0 && (
            <div
              className="py-12 text-center"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <div className="text-2xl mb-2">📋</div>
              <div className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                No receipts yet
              </div>
              <div className="text-xs">
                Run the SLA Evaluator to generate receipts
              </div>
            </div>
          )}
        </div>
      </CardBody>

      <ReceiptDetailModal receipt={selected} onClose={() => setSelected(null)} />
    </Card>
  )
}
