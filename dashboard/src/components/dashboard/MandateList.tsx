import React, { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useMandates } from '../../hooks/useMandates'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { Skeleton } from '../ui/Skeleton'
import { formatAmount, shortId, relativeTime } from '../../lib/format'
import type { Mandate } from '../../types'

export function MandateList() {
  const { mandates, isLoading, refetch } = useMandates()
  const [selected, setSelected] = useState<Mandate | null>(null)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Active Mandates ({mandates.length})</CardTitle>
        <button
          onClick={() => void refetch()}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </CardHeader>
      <CardBody className="py-2">
        {isLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton height={28} className="w-full" />
            <Skeleton height={28} className="w-full" />
          </div>
        ) : mandates.length === 0 ? (
          <div className="text-xs py-2" style={{ color: 'var(--color-text-muted)' }}>
            No active mandates
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {mandates.map((m) => (
              <button
                key={m.mandate_id}
                onClick={() => setSelected(m)}
                className="w-full flex items-center justify-between py-2 px-2 rounded hover:bg-zinc-800 transition-colors text-left"
                style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
              >
                <span className="text-xs font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                  {shortId(m.mandate_id)}
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono" style={{ color: 'var(--color-text-primary)' }}>
                    {formatAmount(m.max_price, 'USDT')}
                  </span>
                  {m.valid_until && (
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {relativeTime(m.valid_until)}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </CardBody>

      {/* Mandate detail modal */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={`Mandate: ${shortId(selected?.mandate_id)}`}
        maxWidth="max-w-lg"
      >
        <div className="p-4">
          <pre
            className="text-xs p-3 rounded border overflow-x-auto font-mono"
            style={{
              background: 'var(--color-bg-primary)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              maxHeight: 400,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {JSON.stringify(selected, null, 2)}
          </pre>
        </div>
      </Modal>
    </Card>
  )
}
