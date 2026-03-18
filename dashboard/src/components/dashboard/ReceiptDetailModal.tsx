import React, { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Badge, slaStatusVariant } from '../ui/Badge'
import { formatAmount, formatLatency, shortAddr, shortHash, relativeTime } from '../../lib/format'
import type { Receipt } from '../../types'

interface ReceiptDetailModalProps {
  receipt: Receipt | null
  onClose: () => void
}

type Tab = 'summary' | 'attestations' | 'llm' | 'raw'

function KV({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b last:border-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <span className="text-xs shrink-0 w-36" style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span className={`text-xs text-right flex-1 ${mono ? 'font-mono' : ''}`} style={{ color: 'var(--color-text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

function AttestRow({ role, signed, address }: { role: string; signed?: boolean; address?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <div className="flex items-center gap-2">
        <Badge variant="neutral">{role}</Badge>
        {address && (
          <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
            {shortAddr(address)}
          </span>
        )}
      </div>
      <Badge variant={signed ? 'pass' : 'fail'}>{signed ? 'SIGNED' : 'MISSING'}</Badge>
    </div>
  )
}

export function ReceiptDetailModal({ receipt, onClose }: ReceiptDetailModalProps) {
  const [tab, setTab] = useState<Tab>('summary')
  const [copied, setCopied] = useState(false)

  if (!receipt) return null

  const token = receipt.token_symbol ?? 'USDT'

  const buyerSigned = receipt.attestations?.buyer?.signed ?? receipt.buyer_attested
  const sellerSigned = receipt.attestations?.seller?.signed ?? receipt.seller_attested
  const gatewaySigned = receipt.attestations?.gateway?.signed ?? receipt.gateway_attested

  const tabs: { key: Tab; label: string }[] = [
    { key: 'summary', label: 'Summary' },
    { key: 'attestations', label: 'Attestations' },
    { key: 'llm', label: 'LLM Policy' },
    { key: 'raw', label: 'Raw JSON' },
  ]

  const handleCopy = () => {
    void navigator.clipboard.writeText(JSON.stringify(receipt, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Modal open={!!receipt} onClose={onClose} title="Receipt Detail" maxWidth="max-w-2xl">
      {/* Tabs */}
      <div className="flex border-b px-4" style={{ borderColor: 'var(--color-border)' }}>
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3 py-2.5 text-xs font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-[--color-accent] text-[--color-accent]'
                : 'border-transparent text-[--color-text-secondary] hover:text-[--color-text-primary]'
            }`}
            style={tab === key ? { borderColor: 'var(--color-accent)', color: 'var(--color-accent)' } : { borderColor: 'transparent', color: 'var(--color-text-secondary)' }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {tab === 'summary' && (
          <div>
            <KV label="Request ID" value={receipt.request_id} mono />
            <KV label="Mandate ID" value={receipt.mandate_id} mono />
            <KV label="SLA Status" value={<Badge variant={slaStatusVariant(receipt.sla_status)}>{receipt.sla_status?.toUpperCase()}</Badge>} />
            <KV label="Valid" value={<Badge variant={receipt.valid ? 'pass' : 'fail'}>{receipt.valid ? 'YES' : 'NO'}</Badge>} />
            <KV label="Latency" value={formatLatency(receipt.latency_ms)} mono />
            <KV label="Payout Rule" value={receipt.payout_rule ?? '—'} mono />
            <KV label="Gross Amount" value={formatAmount(receipt.gross_amount, token)} mono />
            <KV label="Seller Payout" value={formatAmount(receipt.seller_payout, token)} mono />
            <KV label="Buyer Refund" value={formatAmount(receipt.buyer_refund, token)} mono />
            <KV label="Buyer" value={shortAddr(receipt.buyer_address)} mono />
            <KV label="Seller" value={shortAddr(receipt.seller_address)} mono />
            <KV label="Tx Hash" value={shortHash(receipt.tx_hash)} mono />
            <KV label="Receipt Hash" value={shortHash(receipt.receipt_hash)} mono />
            <KV label="Created" value={relativeTime(receipt.created_at)} />
          </div>
        )}

        {tab === 'attestations' && (
          <div>
            <AttestRow
              role="buyer"
              signed={buyerSigned}
              address={receipt.attestations?.buyer?.signer ?? receipt.buyer_address}
            />
            <AttestRow
              role="seller"
              signed={sellerSigned}
              address={receipt.attestations?.seller?.signer ?? receipt.seller_address}
            />
            <AttestRow
              role="gateway"
              signed={gatewaySigned}
              address={receipt.attestations?.gateway?.signer ?? receipt.gateway_address}
            />
            {receipt.validations && receipt.validations.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
                  Validation Results
                </div>
                {receipt.validations.map((v, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b last:border-0 text-xs" style={{ borderColor: 'var(--color-border-subtle)' }}>
                    <span style={{ color: 'var(--color-text-secondary)' }}>{v.validator}</span>
                    <Badge variant={v.passed ? 'pass' : 'fail'}>{v.passed ? 'PASS' : 'FAIL'}</Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'llm' && (
          <div>
            {receipt.llm_policy ? (
              <>
                <KV label="Judge" value={receipt.llm_policy.judge} />
                <KV label="Model" value={receipt.llm_policy.model} mono />
                <KV label="Passed" value={<Badge variant={receipt.llm_policy.passed ? 'pass' : 'fail'}>{receipt.llm_policy.passed ? 'PASS' : 'FAIL'}</Badge>} />
                <KV label="Confidence" value={`${(receipt.llm_policy.confidence * 100).toFixed(1)}%`} mono />
                <KV label="Payout Ratio" value={`${(receipt.llm_policy.payout_ratio * 100).toFixed(1)}%`} mono />
                <KV label="Recommended Payout" value={formatAmount(receipt.llm_policy.recommended_payout, token)} mono />
                <div className="mt-3">
                  <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Reason</div>
                  <div
                    className="text-xs p-3 rounded border"
                    style={{
                      background: 'var(--color-bg-primary)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-secondary)',
                      lineHeight: 1.6,
                    }}
                  >
                    {receipt.llm_policy.reason}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-xs py-4 text-center" style={{ color: 'var(--color-text-muted)' }}>
                No LLM policy data
              </div>
            )}
          </div>
        )}

        {tab === 'raw' && (
          <div>
            <div className="flex justify-end mb-2">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs border transition-colors"
                style={{
                  background: 'var(--color-bg-elevated)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
              </button>
            </div>
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
              {JSON.stringify(receipt, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </Modal>
  )
}
