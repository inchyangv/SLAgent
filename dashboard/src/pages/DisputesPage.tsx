import React from 'react'
import { DisputePanel } from '../components/dashboard/DisputePanel'

export function DisputesPage() {
  return (
    <div className="max-w-screen-2xl mx-auto px-4 py-4 flex flex-col gap-4">
      <div>
        <h1
          className="text-xl font-semibold mb-1"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Disputes
        </h1>
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Manage on-chain SLA disputes. Open a dispute to challenge a receipt outcome,
          resolve with a final payout, and finalize to settle funds on-chain.
        </p>
      </div>

      <div
        className="p-4 rounded-md border text-xs"
        style={{
          background: 'var(--color-bg-elevated)',
          borderColor: 'var(--color-border)',
          color: 'var(--color-text-muted)',
        }}
      >
        <div className="font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-secondary)' }}>
          Dispute Flow
        </div>
        <ol className="list-decimal list-inside flex flex-col gap-1">
          <li><strong style={{ color: 'var(--color-text-secondary)' }}>Open:</strong> Provide a request_id and optional bond amount to initiate a dispute.</li>
          <li><strong style={{ color: 'var(--color-text-secondary)' }}>Resolve:</strong> After review, set the final_payout amount to resolve the dispute.</li>
          <li><strong style={{ color: 'var(--color-text-secondary)' }}>Finalize:</strong> Execute on-chain settlement, transferring funds according to the resolution.</li>
        </ol>
      </div>

      <div className="max-w-xl">
        <DisputePanel />
      </div>
    </div>
  )
}
