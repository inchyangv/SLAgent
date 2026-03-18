import React, { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge, slaStatusVariant } from '../ui/Badge'
import { Skeleton } from '../ui/Skeleton'
import { ReceiptDetailModal } from './ReceiptDetailModal'
import { formatAmount, formatLatency, shortId, shortHash } from '../../lib/format'
import type { Receipt } from '../../types'

type FilterTab = 'all' | 'pass' | 'fail'

interface ReceiptsTableProps {
  receipts: Receipt[]
  isLoading: boolean
  onRefresh: () => void
}

export function ReceiptsTable({ receipts, isLoading, onRefresh }: ReceiptsTableProps) {
  const [filter, setFilter] = useState<FilterTab>('all')
  const [selected, setSelected] = useState<Receipt | null>(null)

  const filtered = receipts.filter((r) => {
    if (filter === 'pass') return r.sla_status === 'pass'
    if (filter === 'fail') return r.sla_status === 'fail'
    return true
  })

  const tabs: { key: FilterTab; label: string }[] = [
    { key: 'all', label: `All (${receipts.length})` },
    { key: 'pass', label: `Pass (${receipts.filter((r) => r.sla_status === 'pass').length})` },
    { key: 'fail', label: `Fail (${receipts.filter((r) => r.sla_status === 'fail').length})` },
  ]

  const token = receipts[0]?.token_symbol ?? 'USDT'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <CardTitle>Receipts</CardTitle>
          <div className="flex gap-1">
            {tabs.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-2.5 py-0.5 rounded text-xs font-medium transition-colors ${
                  filter === key
                    ? 'bg-blue-900 text-blue-300'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={onRefresh}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
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
                    className="px-3 py-2 text-left font-medium uppercase tracking-wide whitespace-nowrap"
                    style={{ color: 'var(--color-text-muted)' }}
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
                : filtered.slice(0, 50).map((r, i) => {
                    const buyerSigned = r.attestations?.buyer?.signed ?? r.buyer_attested
                    const sellerSigned = r.attestations?.seller?.signed ?? r.seller_attested
                    const gatewaySigned = r.attestations?.gateway?.signed ?? r.gateway_attested
                    const attestCount = [buyerSigned, sellerSigned, gatewaySigned].filter(Boolean).length
                    const breachCount = r.validations?.filter((v) => !v.passed).length ?? 0

                    return (
                      <tr
                        key={r.request_id ?? i}
                        className="border-b cursor-pointer hover:bg-zinc-900 transition-colors"
                        style={{ borderColor: 'var(--color-border-subtle)' }}
                        onClick={() => setSelected(r)}
                      >
                        <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                          {shortId(r.request_id)}
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {formatLatency(r.latency_ms)}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={r.sla_status === 'pass' ? 'pass' : r.sla_status === 'fail' ? 'fail' : 'partial'}>
                            {r.sla_status?.toUpperCase() ?? '—'}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {formatAmount(r.seller_payout, token)}
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {formatAmount(r.buyer_refund, token)}
                        </td>
                        <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-muted)' }}>
                          {r.payout_rule ?? '—'}
                        </td>
                        <td className="px-3 py-2">
                          {r.llm_policy ? (
                            <Badge variant={r.llm_policy.passed ? 'pass' : 'fail'}>
                              {r.llm_policy.passed ? 'PASS' : 'FAIL'}
                            </Badge>
                          ) : '—'}
                        </td>
                        <td className="px-3 py-2">
                          {breachCount > 0 ? (
                            <Badge variant="fail">{breachCount}</Badge>
                          ) : (
                            <span style={{ color: 'var(--color-text-muted)' }}>0</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-0.5">
                            {['B', 'S', 'G'].map((role, idx) => {
                              const signed = [buyerSigned, sellerSigned, gatewaySigned][idx]
                              return (
                                <span
                                  key={role}
                                  className="w-4 h-4 rounded-sm text-xs flex items-center justify-center font-mono"
                                  style={{
                                    background: signed ? 'var(--color-success)' : 'var(--color-border)',
                                    color: signed ? '#fff' : 'var(--color-text-muted)',
                                    fontSize: 9,
                                  }}
                                  title={`${['buyer', 'seller', 'gateway'][idx]}: ${signed ? 'signed' : 'missing'}`}
                                >
                                  {role}
                                </span>
                              )
                            })}
                            <span className="ml-1 font-mono" style={{ color: attestCount === 3 ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                              {attestCount}/3
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-2 font-mono" style={{ color: 'var(--color-text-muted)' }}>
                          {shortHash(r.receipt_hash ?? r.tx_hash)}
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>
          {!isLoading && filtered.length === 0 && (
            <div className="text-xs py-8 text-center" style={{ color: 'var(--color-text-muted)' }}>
              No receipts
            </div>
          )}
        </div>
      </CardBody>

      <ReceiptDetailModal receipt={selected} onClose={() => setSelected(null)} />
    </Card>
  )
}
