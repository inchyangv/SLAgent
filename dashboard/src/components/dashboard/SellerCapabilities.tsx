import React, { useState } from 'react'
import { fetchSellerCapabilities } from '../../api'
import { useSettingsStore } from '../../store/settings'
import { useLogStore } from '../../store/log'
import { useToastStore } from '../../store/toast'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { shortAddr } from '../../lib/format'
import type { SellerCapabilities as SellerCaps } from '../../types'

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b last:border-0 text-xs" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span className="text-right" style={{ color: 'var(--color-text-primary)' }}>{value}</span>
    </div>
  )
}

export function SellerCapabilities() {
  const sellerUrl = useSettingsStore((s) => s.sellerUrl)
  const addLog = useLogStore((s) => s.addLog)
  const addToast = useToastStore((s) => s.addToast)

  const [loading, setLoading] = useState(false)
  const [caps, setCaps] = useState<SellerCaps | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFetch() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSellerCapabilities(sellerUrl)
      setCaps(data)
      addLog(`[seller] capabilities fetched`, 'ok')
      addToast('Seller capabilities loaded', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      addLog(`[seller] fetch failed: ${msg}`, 'err')
      addToast(`Fetch failed: ${msg}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Seller Capabilities</CardTitle>
        <Button size="sm" variant="default" onClick={() => void handleFetch()} loading={loading}>
          Fetch
        </Button>
      </CardHeader>
      <CardBody>
        {error && (
          <div className="text-xs mb-3 p-2 rounded border" style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-error)', color: 'var(--color-error)' }}>
            {error}
          </div>
        )}
        {caps ? (
          <>
            <KV label="Address" value={<span className="font-mono">{shortAddr(caps.seller_address)}</span>} />
            <KV label="LLM Provider" value={caps.llm_provider ?? '—'} />
            <KV label="LLM Model" value={<span className="font-mono">{caps.llm_model ?? '—'}</span>} />
            <KV
              label="LLM Available"
              value={
                caps.llm_available !== undefined ? (
                  <Badge variant={caps.llm_available ? 'pass' : 'fail'}>
                    {caps.llm_available ? 'YES' : 'NO'}
                  </Badge>
                ) : '—'
              }
            />
            <KV
              label="Schemas"
              value={
                <div className="flex flex-wrap gap-1 justify-end">
                  {(caps.supported_schemas ?? []).map((s) => (
                    <Badge key={s} variant="neutral">{s}</Badge>
                  ))}
                  {(!caps.supported_schemas || caps.supported_schemas.length === 0) && '—'}
                </div>
              }
            />
            <KV
              label="Modes"
              value={
                <div className="flex flex-wrap gap-1 justify-end">
                  {(caps.supported_modes ?? []).map((m) => (
                    <Badge key={m} variant="info">{m}</Badge>
                  ))}
                  {(!caps.supported_modes || caps.supported_modes.length === 0) && '—'}
                </div>
              }
            />
          </>
        ) : (
          <div className="text-xs py-2" style={{ color: 'var(--color-text-muted)' }}>
            Click "Fetch" to load seller capabilities
          </div>
        )}
      </CardBody>
    </Card>
  )
}
