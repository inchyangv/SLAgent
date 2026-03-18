import { useState } from 'react'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Badge } from '../ui/Badge'
import { formatCurrency, formatLatency, shortAddr, shortHash } from '../../lib/format'
import { useNetwork, txExplorerUrl } from '../../hooks/useNetwork'
import type { Receipt } from '../../types'

interface ReceiptDetailModalProps {
  receipt: Receipt | null
  onClose: () => void
}

type Tab = 'summary' | 'attestations' | 'llm' | 'raw'

const TOKEN = 'USDT'

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
  const { chainId } = useNetwork()

  if (!receipt) return null

  const txHash = receipt.settlement?.tx_hash
  const explorerUrl = txHash ? txExplorerUrl(chainId, txHash) : null

  const parties = receipt.attestations?.parties_signed ?? []
  const buyerSigned = parties.includes('buyer')
  const sellerSigned = parties.includes('seller')
  const gatewaySigned = parties.includes('gateway')

  const vpass = receipt.validation?.overall_pass
  const llmPolicy = receipt.outcome?.llm_policy

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
            className="px-3 py-2.5 text-xs font-medium border-b-2 -mb-px transition-colors"
            style={
              tab === key
                ? { borderColor: 'var(--color-accent)', color: 'var(--color-accent)' }
                : { borderColor: 'transparent', color: 'var(--color-text-secondary)' }
            }
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4 overflow-y-auto" style={{ maxHeight: 'calc(80vh - 120px)' }}>
        {tab === 'summary' && (
          <div>
            <KV label="Request ID" value={receipt.request_id} mono />
            <KV label="Mandate ID" value={receipt.mandate_id ?? '—'} mono />
            <KV
              label="SLA Status"
              value={
                <Badge variant={vpass ? 'pass' : 'fail'}>
                  {vpass ? 'PASS' : 'FAIL'}
                </Badge>
              }
            />
            <KV
              label="Outcome"
              value={
                <Badge variant={receipt.outcome?.success ? 'pass' : 'fail'}>
                  {receipt.outcome?.success ? 'SUCCESS' : (receipt.outcome?.error_code ?? 'FAIL')}
                </Badge>
              }
            />
            <KV label="Latency" value={formatLatency(receipt.metrics?.latency_ms)} mono />
            <KV label="TTFT" value={formatLatency(receipt.metrics?.ttft_ms)} mono />
            <KV label="Max Price" value={formatCurrency(receipt.pricing?.max_price, TOKEN)} mono />
            <KV label="Seller Payout" value={formatCurrency(receipt.pricing?.computed_payout, TOKEN)} mono />
            <KV label="Buyer Refund" value={formatCurrency(receipt.pricing?.computed_refund, TOKEN)} mono />
            <KV label="Rule Applied" value={receipt.pricing?.rule_applied ?? '—'} mono />
            <KV label="Buyer" value={shortAddr(receipt.buyer)} mono />
            <KV label="Seller" value={shortAddr(receipt.seller)} mono />
            <KV label="Gateway" value={shortAddr(receipt.gateway)} mono />
            <KV label="Receipt Hash" value={shortHash(receipt.hashes?.receipt_hash)} mono />
            <KV
              label="Tx Hash"
              value={
                txHash && explorerUrl ? (
                  <a
                    href={explorerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 font-mono transition-colors hover:underline"
                    style={{ color: 'var(--color-accent)' }}
                  >
                    {shortHash(txHash)}
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  shortHash(txHash)
                )
              }
            />
            {(receipt.breach_reasons ?? receipt.pricing?.breach_reasons ?? []).length > 0 && (
              <div className="mt-3">
                <div className="text-xs mb-2 uppercase tracking-wide" style={{ color: 'var(--color-error)' }}>
                  SLA Breaches
                </div>
                <div className="flex flex-wrap gap-1">
                  {(receipt.breach_reasons ?? receipt.pricing?.breach_reasons ?? []).map((b, i) => (
                    <Badge key={i} variant="fail">{String(b).replace('BREACH_', '')}</Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'attestations' && (
          <div>
            <AttestRow role="buyer" signed={buyerSigned} address={receipt.buyer} />
            <AttestRow role="seller" signed={sellerSigned} address={receipt.seller} />
            <AttestRow role="gateway" signed={gatewaySigned} address={receipt.gateway} />

            <div className="mt-3">
              <KV
                label="All Verified"
                value={
                  <Badge variant={receipt.attestations?.all_verified ? 'pass' : 'fail'}>
                    {receipt.attestations?.all_verified ? 'YES' : 'NO'}
                  </Badge>
                }
              />
            </div>

            {receipt.validation?.results && receipt.validation.results.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
                  Validation Results
                </div>
                {receipt.validation.results.map((v, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-1.5 border-b last:border-0 text-xs"
                    style={{ borderColor: 'var(--color-border-subtle)' }}
                  >
                    <span style={{ color: 'var(--color-text-secondary)' }}>
                      {v.type ?? '—'}{v.schema_id ? `:${v.schema_id}` : ''}
                    </span>
                    <Badge variant={v.pass ? 'pass' : 'fail'}>{v.pass ? 'PASS' : 'FAIL'}</Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'llm' && (
          <div>
            {llmPolicy?.mode === 'llm' ? (
              <>
                <KV label="Mode" value={llmPolicy.mode} mono />
                <KV label="Model" value={llmPolicy.model ?? '—'} mono />
                <KV
                  label="Judgment"
                  value={
                    <Badge variant={llmPolicy.sla_pass ? 'pass' : 'fail'}>
                      {llmPolicy.sla_pass ? 'PASS' : 'FAIL'}
                    </Badge>
                  }
                />
                <KV
                  label="Confidence"
                  value={
                    llmPolicy.confidence !== undefined
                      ? `${(llmPolicy.confidence * 100).toFixed(1)}%`
                      : '—'
                  }
                  mono
                />
                <KV
                  label="Recommended Payout"
                  value={formatCurrency(llmPolicy.recommended_payout, TOKEN)}
                  mono
                />
                {llmPolicy.reason && (
                  <div className="mt-3">
                    <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
                      Reason
                    </div>
                    <div
                      className="text-xs p-3 rounded border"
                      style={{
                        background: 'var(--color-bg-primary)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.6,
                      }}
                    >
                      {llmPolicy.reason}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-xs py-4 text-center" style={{ color: 'var(--color-text-muted)' }}>
                <div className="text-lg mb-2">⚖️</div>
                LLM Policy not active for this receipt
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
