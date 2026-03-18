import React, { useMemo } from 'react'
import { useReceipts } from '../hooks/useReceipts'
import { StatCard } from '../components/ui/StatCard'
import { ReceiptsTable } from '../components/dashboard/ReceiptsTable'
import { formatAmountShort } from '../lib/format'

export function ReceiptsPage() {
  const { receipts, isLoading, refetch } = useReceipts()

  const stats = useMemo(() => {
    const total = receipts.length
    const pass = receipts.filter((r) => r.sla_status === 'pass').length
    const fail = receipts.filter((r) => r.sla_status === 'fail').length
    const token = receipts[0]?.token_symbol ?? 'USDT'

    const totalPayout = receipts.reduce((acc, r) => {
      const v = typeof r.seller_payout === 'string'
        ? parseFloat(r.seller_payout)
        : (r.seller_payout ?? 0)
      return acc + (isNaN(v as number) ? 0 : (v as number))
    }, 0)

    return { total, pass, fail, totalPayout, token }
  }, [receipts])

  return (
    <div className="max-w-screen-2xl mx-auto px-4 py-4 flex flex-col gap-4">
      <h1
        className="text-xl font-semibold"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Receipts Ledger
      </h1>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Total" value={stats.total} />
        <StatCard label="Pass" value={stats.pass} variant="success" />
        <StatCard label="Fail" value={stats.fail} variant="error" />
        <StatCard
          label="Total Payout"
          value={formatAmountShort(stats.totalPayout, stats.token)}
          variant="accent"
        />
      </div>

      {/* Table */}
      <ReceiptsTable
        receipts={receipts}
        isLoading={isLoading}
        onRefresh={() => void refetch()}
      />
    </div>
  )
}
