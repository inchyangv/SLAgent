import React from 'react'
import { RefreshCw } from 'lucide-react'
import { useBalances } from '../../hooks/useBalances'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { formatAmount, relativeTime, shortAddr } from '../../lib/format'

function BalanceRow({
  role,
  address,
  balance,
  symbol,
}: {
  role: string
  address?: string
  balance?: string | number
  symbol?: string
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-mono px-1.5 py-0.5 rounded uppercase"
          style={{ background: 'var(--color-bg-elevated)', color: 'var(--color-text-muted)' }}
        >
          {role}
        </span>
        {address && (
          <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
            {shortAddr(address)}
          </span>
        )}
      </div>
      <span className="text-sm font-mono font-semibold" style={{ color: 'var(--color-text-primary)' }}>
        {formatAmount(balance, symbol)}
      </span>
    </div>
  )
}

export function BalancePanel() {
  const { data, isLoading, error, refetch } = useBalances()
  const symbol = data?.token?.symbol ?? 'USDT'

  return (
    <Card className="min-w-[260px]">
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Balances</CardTitle>
          {!isLoading && !error && (
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: 'var(--color-success)' }}
            />
          )}
        </div>
        <button
          onClick={() => void refetch()}
          className="p-1 rounded transition-colors hover:bg-zinc-800"
          style={{ color: 'var(--color-text-muted)' }}
          title="Refresh balances"
        >
          <RefreshCw size={13} />
        </button>
      </CardHeader>
      <CardBody className="py-2">
        {isLoading ? (
          <div className="flex flex-col gap-2 py-1">
            <Skeleton height={28} className="w-full" />
            <Skeleton height={28} className="w-full" />
            <Skeleton height={28} className="w-full" />
          </div>
        ) : error ? (
          <div className="text-xs py-2" style={{ color: 'var(--color-error)' }}>
            Failed to load balances
          </div>
        ) : (
          <>
            <BalanceRow
              role="buyer"
              address={data?.roles?.buyer?.address}
              balance={data?.roles?.buyer?.balance}
              symbol={symbol}
            />
            <BalanceRow
              role="seller"
              address={data?.roles?.seller?.address}
              balance={data?.roles?.seller?.balance}
              symbol={symbol}
            />
            <BalanceRow
              role="gateway"
              address={data?.roles?.gateway?.address}
              balance={data?.roles?.gateway?.balance}
              symbol={symbol}
            />
            <div
              className="text-xs mt-2 text-right"
              style={{ color: 'var(--color-text-muted)' }}
            >
              updated {relativeTime(data?.updated_at)}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}
