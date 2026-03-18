import { useMemo } from 'react'
import { StatCard } from '../ui/StatCard'
import { formatAmountShort, formatLatency } from '../../lib/format'
import type { Receipt } from '../../types'

interface HeroStatsProps {
  receipts: Receipt[]
}

export function HeroStats({ receipts }: HeroStatsProps) {
  const stats = useMemo(() => {
    const total = receipts.length
    const pass = receipts.filter((r) => r.validation?.overall_pass).length
    const fail = total - pass

    const latencies = receipts
      .map((r) => r.metrics?.latency_ms)
      .filter((l): l is number => typeof l === 'number' && !isNaN(l))
    const avgMs = latencies.length
      ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
      : 0

    const threeOfThree = receipts.filter((r) => {
      const parties = r.attestations?.parties_signed ?? []
      return parties.includes('buyer') && parties.includes('seller') && parties.includes('gateway')
    }).length

    const grossLocked = receipts.reduce((acc, r) => {
      const v = parseInt(r.pricing?.max_price ?? '0', 10)
      return acc + (isNaN(v) ? 0 : v)
    }, 0)

    const sellerPaid = receipts.reduce((acc, r) => {
      const v = parseInt(r.pricing?.computed_payout ?? '0', 10)
      return acc + (isNaN(v) ? 0 : v)
    }, 0)

    const buyerRefund = receipts.reduce((acc, r) => {
      const v = parseInt(r.pricing?.computed_refund ?? '0', 10)
      return acc + (isNaN(v) ? 0 : v)
    }, 0)

    return { total, pass, fail, avgMs, threeOfThree, grossLocked, sellerPaid, buyerRefund }
  }, [receipts])

  const token = 'USDT'

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
        value={formatAmountShort(stats.grossLocked, token)}
        variant="accent"
      />
      <StatCard
        label="Seller Paid"
        value={formatAmountShort(stats.sellerPaid, token)}
        variant="success"
      />
      <StatCard
        label="Buyer Refund"
        value={formatAmountShort(stats.buyerRefund, token)}
        variant="warning"
      />
    </div>
  )
}
