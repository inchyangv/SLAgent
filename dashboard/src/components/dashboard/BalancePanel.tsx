import { RefreshCw } from 'lucide-react'
import { useBalances } from '../../hooks/useBalances'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { formatCurrency, shortAddr } from '../../lib/format'

const ROLES = ['buyer', 'seller', 'gateway'] as const

function LiveDot({ isLive }: { isLive: boolean }) {
  return (
    <span
      className="w-2 h-2 rounded-full inline-block shrink-0"
      style={{
        background: isLive ? 'var(--color-success)' : 'var(--color-text-muted)',
        boxShadow: isLive ? '0 0 0 2px rgba(34,197,94,0.2)' : 'none',
        animation: isLive ? 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite' : 'none',
      }}
    />
  )
}

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
  const formatted = formatCurrency(balance, symbol)

  return (
    <div
      className="flex items-center gap-3 px-3 py-2.5 rounded-md border"
      style={{
        background: 'var(--color-bg-primary)',
        borderColor: 'var(--color-border-subtle)',
      }}
    >
      {/* Role badge */}
      <div
        className="w-14 shrink-0 text-center text-xs font-medium tracking-wide uppercase rounded py-0.5"
        style={{
          background: 'var(--color-bg-elevated)',
          color: 'var(--color-text-muted)',
          fontSize: '10px',
        }}
      >
        {role}
      </div>

      {/* Address */}
      <div className="flex-1 min-w-0">
        <span
          className="font-mono text-xs truncate block"
          style={{ color: 'var(--color-text-muted)' }}
          title={address}
        >
          {address ? shortAddr(address) : '—'}
        </span>
      </div>

      {/* Amount */}
      <div
        className="font-mono text-sm font-semibold shrink-0 tabular-nums"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {formatted}
      </div>
    </div>
  )
}

export function BalancePanel() {
  const { data, isLoading, error, refetch, dataUpdatedAt } = useBalances()
  const symbol = data?.token?.symbol ?? 'USDT'
  const isLive = !error

  // Format last-updated time
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('en-US', { hour12: false })
    : null

  return (
    <Card className="min-w-[280px]">
      <CardHeader>
        <div className="flex items-center gap-2">
          <LiveDot isLive={isLive && !isLoading} />
          <CardTitle>Protocol Balances</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
              {lastUpdated}
            </span>
          )}
          <button
            onClick={() => void refetch()}
            className="p-1 rounded transition-colors hover:bg-zinc-800"
            style={{ color: 'var(--color-text-muted)' }}
            title="Refresh balances"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </CardHeader>

      <CardBody className="flex flex-col gap-2 py-2">
        {isLoading ? (
          <>
            <Skeleton height={40} className="w-full" />
            <Skeleton height={40} className="w-full" />
            <Skeleton height={40} className="w-full" />
          </>
        ) : error ? (
          <div
            className="text-xs py-3 text-center rounded-md border"
            style={{
              color: 'var(--color-error)',
              borderColor: 'rgba(239,68,68,0.2)',
              background: 'rgba(239,68,68,0.05)',
            }}
          >
            Balance fetch failed — check gateway URL
          </div>
        ) : (
          <>
            {ROLES.map((role) => (
              <BalanceRow
                key={role}
                role={role}
                address={data?.roles?.[role]?.address}
                balance={data?.roles?.[role]?.balance}
                symbol={symbol}
              />
            ))}
            {data?.error && (
              <div className="text-xs mt-1" style={{ color: 'var(--color-warning)' }}>
                ⚠ {data.error}
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  )
}
