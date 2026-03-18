import React, { useMemo } from 'react'
import { StatCard } from '../ui/StatCard'
import { formatAmountShort, formatLatency } from '../../lib/format'
import type { Receipt } from '../../types'

interface HeroStatsProps {
  receipts: Receipt[]
}

export function HeroStats({ receipts }: HeroStatsProps) {
  const stats = useMemo(() => {
    const total = receipts.length
    const pass = receipts.filter((r) => r.sla_status === 'pass').length
    const fail = receipts.filter((r) => r.sla_status === 'fail').length

    const latencies = receipts
      .map((r) => r.latency_ms)
      .filter((l): l is number => typeof l === 'number' && !isNaN(l))
    const avgMs = latencies.length
      ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
      : 0

    const threeOfThree = receipts.filter((r) => {
      const a = r.attestations
      if (a) {
        return a.buyer?.signed && a.seller?.signed && a.gateway?.signed
      }
      return r.buyer_attested && r.seller_attested && r.gateway_attested
    }).length

    const grossLocked = receipts.reduce((acc, r) => {
      const v = typeof r.gross_amount === 'string' ? parseFloat(r.gross_amount) : (r.gross_amount ?? 0)
      return acc + (isNaN(v) ? 0 : v)
    }, 0)

    const sellerPaid = receipts.reduce((acc, r) => {
      const v = typeof r.seller_payout === 'string' ? parseFloat(r.seller_payout as string) : (r.seller_payout ?? 0)
      return acc + (isNaN(v as number) ? 0 : (v as number))
    }, 0)

    const buyerRefund = receipts.reduce((acc, r) => {
      const v = typeof r.buyer_refund === 'string' ? parseFloat(r.buyer_refund as string) : (r.buyer_refund ?? 0)
      return acc + (isNaN(v as number) ? 0 : (v as number))
    }, 0)

    const token = receipts[0]?.token_symbol ?? 'USDT'

    return { total, pass, fail, avgMs, threeOfThree, grossLocked, sellerPaid, buyerRefund, token }
  }, [receipts])

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
      <StatCard label="Requests" value={stats.total} />
      <StatCard label="Pass" value={stats.pass} variant="success" />
      <StatCard label="Fail" value={stats.fail} variant="error" />
      <StatCard
        label="Avg ms"
        value={formatLatency(stats.avgMs)}
        variant={stats.avgMs > 3000 ? 'warning' : 'default'}
      />
      <StatCard label="3/3 Attest" value={stats.threeOfThree} variant="accent" />
      <StatCard
        label="Gross Locked"
        value={formatAmountShort(stats.grossLocked, stats.token)}
        variant="accent"
      />
      <StatCard
        label="Seller Paid"
        value={formatAmountShort(stats.sellerPaid, stats.token)}
        variant="success"
      />
      <StatCard
        label="Buyer Refund"
        value={formatAmountShort(stats.buyerRefund, stats.token)}
        variant="warning"
      />
    </div>
  )
}
