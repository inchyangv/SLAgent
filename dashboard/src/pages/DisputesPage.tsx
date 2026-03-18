import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { openDispute, resolveDispute, finalizeDispute, fetchDispute } from '../api'
import { useSettingsStore } from '../store/settings'
import { useLogStore } from '../store/log'
import { useToastStore } from '../store/toast'
import { useReceipts } from '../hooks/useReceipts'
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { formatCurrency, shortId } from '../lib/format'
import type { DisputeState } from '../types'

type Step = 'open' | 'resolve' | 'finalize'

const STEPS: { key: Step; label: string; desc: string }[] = [
  { key: 'open', label: 'Open', desc: 'Challenge a receipt outcome by posting bond' },
  { key: 'resolve', label: 'Resolve', desc: 'Set the final payout after review' },
  { key: 'finalize', label: 'Finalize', desc: 'Settle funds on-chain' },
]

function statusVariant(status?: string) {
  if (status === 'open') return 'warning' as const
  if (status === 'resolved') return 'info' as const
  if (status === 'finalized') return 'pass' as const
  return 'neutral' as const
}

function StepTimeline({ current }: { current: Step }) {
  const currentIdx = STEPS.findIndex((s) => s.key === current)
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, idx) => {
        const isDone = idx < currentIdx
        const isActive = idx === currentIdx
        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors"
                style={{
                  background: isActive
                    ? 'var(--color-accent)'
                    : isDone
                    ? 'var(--color-success)'
                    : 'var(--color-bg-elevated)',
                  borderColor: isActive
                    ? 'var(--color-accent)'
                    : isDone
                    ? 'var(--color-success)'
                    : 'var(--color-border)',
                  color: isActive || isDone ? '#fff' : 'var(--color-text-muted)',
                }}
              >
                {isDone ? '✓' : idx + 1}
              </div>
              <div className="mt-1 text-xs text-center whitespace-nowrap" style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
                {step.label}
              </div>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className="w-16 h-px mx-2 mb-4"
                style={{ background: isDone ? 'var(--color-success)' : 'var(--color-border)' }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function DisputesPage() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const addLog = useLogStore((s) => s.addLog)
  const addToast = useToastStore((s) => s.addToast)
  const { receipts } = useReceipts()

  const [activeStep, setActiveStep] = useState<Step>('open')
  const [requestId, setRequestId] = useState('')
  const [bondAmount, setBondAmount] = useState('')
  const [finalPayout, setFinalPayout] = useState('')
  const [loading, setLoading] = useState(false)
  const [disputeState, setDisputeState] = useState<DisputeState | null>(null)

  // Recent receipt IDs for selection
  const recentReceipts = receipts.slice(0, 10)

  async function handleOpen() {
    if (!requestId) return
    setLoading(true)
    try {
      const bond = bondAmount ? parseFloat(bondAmount) * 1_000_000 : undefined
      const res = await openDispute(gatewayUrl, requestId, bond)
      setDisputeState(res)
      addLog(`[dispute] opened: ${requestId}`, 'ok')
      addToast('Dispute opened successfully', 'success')
      setActiveStep('resolve')
      setFinalPayout('')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] open failed: ${msg}`, 'err')
      addToast(`Open dispute failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleResolve() {
    if (!requestId || !finalPayout) return
    setLoading(true)
    try {
      const payout = parseFloat(finalPayout) * 1_000_000
      const res = await resolveDispute(gatewayUrl, requestId, payout)
      setDisputeState(res)
      addLog(`[dispute] resolved: ${requestId}`, 'ok')
      addToast('Dispute resolved successfully', 'success')
      setActiveStep('finalize')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] resolve failed: ${msg}`, 'err')
      addToast(`Resolve failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleFinalize() {
    if (!requestId) return
    setLoading(true)
    try {
      const res = await finalizeDispute(gatewayUrl, requestId)
      setDisputeState(res)
      addLog(`[dispute] finalized: ${requestId}`, 'ok')
      addToast('Dispute finalized — funds settled on-chain', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] finalize failed: ${msg}`, 'err')
      addToast(`Finalize failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleLookup() {
    if (!requestId) return
    setLoading(true)
    try {
      const res = await fetchDispute(gatewayUrl, requestId)
      setDisputeState(res)
      if (res.status === 'open') setActiveStep('resolve')
      else if (res.status === 'resolved') setActiveStep('finalize')
      addToast(`Dispute status: ${res.status ?? 'unknown'}`, 'info')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addToast(`Lookup failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-4 flex flex-col gap-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
          Disputes
        </h1>
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Challenge a receipt outcome and settle on-chain via bonded dispute resolution.
        </p>
      </div>

      {/* Step timeline */}
      <Card>
        <CardBody className="py-4 flex flex-col items-center gap-1">
          <StepTimeline current={activeStep} />
          <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
            {STEPS.find((s) => s.key === activeStep)?.desc}
          </p>
        </CardBody>
      </Card>

      {/* Request ID + receipt picker */}
      <Card>
        <CardHeader>
          <CardTitle>Request ID</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-3">
            <Input
              label="Request ID"
              placeholder="req_20260312_000001"
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
            />

            {recentReceipts.length > 0 && (
              <div>
                <div className="text-xs mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
                  Select from recent receipts:
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {recentReceipts.map((r) => {
                    const vpass = r.validation?.overall_pass
                    return (
                      <button
                        key={r.request_id}
                        onClick={() => setRequestId(r.request_id)}
                        className="flex items-center gap-1.5 px-2 py-1 rounded border text-xs transition-colors"
                        style={{
                          background: requestId === r.request_id
                            ? 'rgba(74,158,255,0.1)'
                            : 'var(--color-bg-elevated)',
                          borderColor: requestId === r.request_id
                            ? 'var(--color-accent)'
                            : 'var(--color-border)',
                          color: 'var(--color-text-secondary)',
                        }}
                        title={r.request_id}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ background: vpass ? 'var(--color-success)' : 'var(--color-error)' }}
                        />
                        <span className="font-mono">{shortId(r.request_id)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleLookup()}
                loading={loading}
                disabled={!requestId}
              >
                Look up status
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Active step form */}
      {activeStep === 'open' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 1: Open Dispute</CardTitle>
            <Badge variant="warning">STEP 1</Badge>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-3">
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Post a bond to challenge the receipt outcome. If the challenge is upheld, the bond is returned.
                If wrongful, the bond is slashed.
              </p>
              <Input
                label="Bond Amount (USDT, optional)"
                placeholder="0.05"
                type="number"
                value={bondAmount}
                onChange={(e) => setBondAmount(e.target.value)}
              />
              <Button
                variant="danger"
                size="sm"
                onClick={() => void handleOpen()}
                loading={loading}
                disabled={!requestId}
              >
                Open Dispute
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {activeStep === 'resolve' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Resolve Dispute</CardTitle>
            <Badge variant="info">STEP 2</Badge>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-3">
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                After reviewing the dispute, set the final payout amount. This overrides the original settlement.
              </p>
              {disputeState?.bond_amount !== undefined && (
                <div className="flex items-center justify-between px-3 py-2 rounded border text-xs" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Bond locked</span>
                  <span className="font-mono">{formatCurrency(disputeState.bond_amount, 'USDT')}</span>
                </div>
              )}
              <Input
                label="Final Payout (USDT)"
                placeholder="0.06"
                type="number"
                value={finalPayout}
                onChange={(e) => setFinalPayout(e.target.value)}
              />
              <Button
                variant="primary"
                size="sm"
                onClick={() => void handleResolve()}
                loading={loading}
                disabled={!requestId || !finalPayout}
              >
                Resolve Dispute
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {activeStep === 'finalize' && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Finalize Dispute</CardTitle>
            <Badge variant="pass">STEP 3</Badge>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-3">
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Execute the on-chain settlement using the resolved payout. This is irreversible.
              </p>
              {disputeState?.final_payout !== undefined && (
                <div className="flex items-center justify-between px-3 py-2 rounded border text-xs" style={{ borderColor: 'var(--color-success)', background: 'rgba(34,197,94,0.05)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Final payout</span>
                  <span className="font-mono" style={{ color: 'var(--color-success)' }}>
                    {formatCurrency(disputeState.final_payout, 'USDT')}
                  </span>
                </div>
              )}
              <Button
                variant="primary"
                size="sm"
                onClick={() => void handleFinalize()}
                loading={loading}
                disabled={!requestId}
              >
                Finalize (On-chain Settlement)
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Status display */}
      {disputeState && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Dispute Status</CardTitle>
              <Badge variant={statusVariant(disputeState.status)}>
                {(disputeState.status ?? 'unknown').toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardBody>
            <div className="text-xs flex flex-col gap-2">
              {disputeState.request_id && (
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Request ID</span>
                  <span className="font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                    {shortId(disputeState.request_id)}
                  </span>
                </div>
              )}
              {disputeState.bond_amount !== undefined && (
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Bond</span>
                  <span className="font-mono">{formatCurrency(disputeState.bond_amount, 'USDT')}</span>
                </div>
              )}
              {disputeState.final_payout !== undefined && (
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Final Payout</span>
                  <span className="font-mono" style={{ color: 'var(--color-success)' }}>
                    {formatCurrency(disputeState.final_payout, 'USDT')}
                  </span>
                </div>
              )}
              {disputeState.opened_at && (
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Opened</span>
                  <span className="font-mono">{disputeState.opened_at}</span>
                </div>
              )}
              {disputeState.resolved_at && (
                <div className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Resolved</span>
                  <span className="font-mono">{disputeState.resolved_at}</span>
                </div>
              )}
              {disputeState.finalized_at && (
                <div className="flex justify-between py-1" style={{ borderColor: 'var(--color-border-subtle)' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Finalized</span>
                  <span className="font-mono">{disputeState.finalized_at}</span>
                </div>
              )}
            </div>

            {/* Step navigator */}
            <div className="flex gap-2 mt-4 pt-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
              {STEPS.map((step, idx) => (
                <button
                  key={step.key}
                  onClick={() => setActiveStep(step.key)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors"
                  style={{
                    background: activeStep === step.key ? 'rgba(74,158,255,0.1)' : 'transparent',
                    color: activeStep === step.key ? 'var(--color-accent)' : 'var(--color-text-muted)',
                    border: `1px solid ${activeStep === step.key ? 'var(--color-accent)' : 'transparent'}`,
                  }}
                >
                  {idx < STEPS.findIndex((s) => s.key === activeStep) && <span>✓</span>}
                  {step.label}
                  {idx < STEPS.length - 1 && <ChevronRight size={10} />}
                </button>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
