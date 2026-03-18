import React, { useState } from 'react'
import { openDispute, resolveDispute, finalizeDispute, fetchDispute } from '../../api'
import { useSettingsStore } from '../../store/settings'
import { useLogStore } from '../../store/log'
import { useToastStore } from '../../store/toast'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { formatAmount } from '../../lib/format'
import type { DisputeState } from '../../types'

function statusVariant(status?: string) {
  if (status === 'open') return 'warning'
  if (status === 'resolved') return 'info'
  if (status === 'finalized') return 'pass'
  return 'neutral'
}

export function DisputePanel() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const addLog = useLogStore((s) => s.addLog)
  const addToast = useToastStore((s) => s.addToast)

  const [openId, setOpenId] = useState('')
  const [openBond, setOpenBond] = useState('')
  const [resolveId, setResolveId] = useState('')
  const [resolvePayout, setResolvePayout] = useState('')
  const [finalizeId, setFinalizeId] = useState('')

  const [loading, setLoading] = useState<string | null>(null)
  const [disputeState, setDisputeState] = useState<DisputeState | null>(null)

  async function handleOpen() {
    if (!openId) return
    setLoading('open')
    try {
      const bond = openBond ? parseFloat(openBond) * 1_000_000 : undefined
      const res = await openDispute(gatewayUrl, openId, bond)
      setDisputeState(res)
      addLog(`[dispute] opened: ${openId}`, 'ok')
      addToast('Dispute opened', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] open failed: ${msg}`, 'err')
      addToast(`Open failed: ${msg}`, 'error')
    } finally {
      setLoading(null)
    }
  }

  async function handleResolve() {
    if (!resolveId || !resolvePayout) return
    setLoading('resolve')
    try {
      const payout = parseFloat(resolvePayout) * 1_000_000
      const res = await resolveDispute(gatewayUrl, resolveId, payout)
      setDisputeState(res)
      addLog(`[dispute] resolved: ${resolveId}`, 'ok')
      addToast('Dispute resolved', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] resolve failed: ${msg}`, 'err')
      addToast(`Resolve failed: ${msg}`, 'error')
    } finally {
      setLoading(null)
    }
  }

  async function handleFinalize() {
    if (!finalizeId) return
    setLoading('finalize')
    try {
      const res = await finalizeDispute(gatewayUrl, finalizeId)
      setDisputeState(res)
      addLog(`[dispute] finalized: ${finalizeId}`, 'ok')
      addToast('Dispute finalized', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog(`[dispute] finalize failed: ${msg}`, 'err')
      addToast(`Finalize failed: ${msg}`, 'error')
    } finally {
      setLoading(null)
    }
  }

  async function handleFetchStatus() {
    const id = openId || resolveId || finalizeId
    if (!id) return
    setLoading('fetch')
    try {
      const res = await fetchDispute(gatewayUrl, id)
      setDisputeState(res)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addToast(`Fetch failed: ${msg}`, 'error')
    } finally {
      setLoading(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Disputes</CardTitle>
      </CardHeader>
      <CardBody>
        <div className="flex flex-col gap-4">
          {/* Open Dispute */}
          <div className="p-3 rounded border" style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border-subtle)' }}>
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>Open Dispute</div>
            <div className="flex flex-col gap-2">
              <Input
                placeholder="request_id"
                value={openId}
                onChange={(e) => setOpenId(e.target.value)}
              />
              <Input
                placeholder="bond_amount (USDT, optional)"
                type="number"
                value={openBond}
                onChange={(e) => setOpenBond(e.target.value)}
              />
              <Button
                variant="danger"
                size="sm"
                onClick={() => void handleOpen()}
                loading={loading === 'open'}
                disabled={!openId}
              >
                Open
              </Button>
            </div>
          </div>

          {/* Resolve Dispute */}
          <div className="p-3 rounded border" style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border-subtle)' }}>
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>Resolve Dispute</div>
            <div className="flex flex-col gap-2">
              <Input
                placeholder="request_id"
                value={resolveId}
                onChange={(e) => setResolveId(e.target.value)}
              />
              <Input
                placeholder="final_payout (USDT)"
                type="number"
                value={resolvePayout}
                onChange={(e) => setResolvePayout(e.target.value)}
              />
              <Button
                variant="primary"
                size="sm"
                onClick={() => void handleResolve()}
                loading={loading === 'resolve'}
                disabled={!resolveId || !resolvePayout}
              >
                Resolve
              </Button>
            </div>
          </div>

          {/* Finalize Dispute */}
          <div className="p-3 rounded border" style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border-subtle)' }}>
            <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>Finalize Dispute</div>
            <div className="flex flex-col gap-2">
              <Input
                placeholder="request_id"
                value={finalizeId}
                onChange={(e) => setFinalizeId(e.target.value)}
              />
              <Button
                variant="default"
                size="sm"
                onClick={() => void handleFinalize()}
                loading={loading === 'finalize'}
                disabled={!finalizeId}
              >
                Finalize
              </Button>
            </div>
          </div>

          {/* Status */}
          {disputeState && (
            <div className="p-3 rounded border" style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border-subtle)' }}>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>Status</div>
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant(disputeState.status)}>{disputeState.status?.toUpperCase()}</Badge>
                  <Button size="sm" variant="ghost" onClick={() => void handleFetchStatus()} loading={loading === 'fetch'}>
                    Refresh
                  </Button>
                </div>
              </div>
              <div className="text-xs flex flex-col gap-1">
                <div className="flex justify-between">
                  <span style={{ color: 'var(--color-text-muted)' }}>Request ID</span>
                  <span className="font-mono" style={{ color: 'var(--color-text-secondary)' }}>{disputeState.request_id}</span>
                </div>
                {disputeState.bond_amount !== undefined && (
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--color-text-muted)' }}>Bond</span>
                    <span className="font-mono">{formatAmount(disputeState.bond_amount, 'USDT')}</span>
                  </div>
                )}
                {disputeState.final_payout !== undefined && (
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--color-text-muted)' }}>Final Payout</span>
                    <span className="font-mono">{formatAmount(disputeState.final_payout, 'USDT')}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  )
}
