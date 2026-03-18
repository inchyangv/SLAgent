import React, { useState } from 'react'
import { useSettingsStore } from '../store/settings'
import { useToastStore } from '../store/toast'
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import type { SimPreset } from '../types'

const PRESETS: SimPreset[] = ['happy', 'slow', 'breaches']

const presetDesc: Record<SimPreset, string> = {
  happy: 'Fast mode, no errors, no delays',
  slow: 'Slow mode, 4s delay, no errors',
  breaches: 'Invalid mode, schema fail + upstream error',
}

function NumberInput({ label, value, onChange, min = 1, max = 120, unit = 's' }: {
  label: string; value: number; onChange: (n: number) => void; min?: number; max?: number; unit?: string
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <label className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
          className="w-20 px-2 py-1 rounded text-xs font-mono border text-center"
          style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
        />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{unit}</span>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const store = useSettingsStore()
  const addToast = useToastStore((s) => s.addToast)

  const [gatewayUrl, setGatewayUrl] = useState(store.gatewayUrl)
  const [sellerUrl, setSellerUrl] = useState(store.sellerUrl)
  const [interval, setInterval] = useState(store.autopilotInterval)
  const [preset, setPreset] = useState<SimPreset>(store.currentPreset)
  const [balancePoll, setBalancePoll] = useState(store.balancePollInterval)
  const [receiptPoll, setReceiptPoll] = useState(store.receiptPollInterval)
  const [eventPoll, setEventPoll] = useState(store.eventPollInterval)

  function handleSave() {
    store.setGatewayUrl(gatewayUrl)
    store.setSellerUrl(sellerUrl)
    store.setAutopilotInterval(interval)
    store.setPreset(preset)
    store.setBalancePollInterval(balancePoll)
    store.setReceiptPollInterval(receiptPoll)
    store.setEventPollInterval(eventPoll)
    addToast('Settings saved', 'success')
  }

  function handleReset() {
    setGatewayUrl('http://localhost:8000')
    setSellerUrl('http://localhost:8001')
    setInterval(1)
    setPreset('happy')
    setBalancePoll(10)
    setReceiptPoll(5)
    setEventPoll(3)
  }

  const isDirty =
    gatewayUrl !== store.gatewayUrl ||
    sellerUrl !== store.sellerUrl ||
    interval !== store.autopilotInterval ||
    preset !== store.currentPreset ||
    balancePoll !== store.balancePollInterval ||
    receiptPoll !== store.receiptPollInterval ||
    eventPoll !== store.eventPollInterval

  return (
    <div className="max-w-2xl mx-auto px-4 py-4 flex flex-col gap-4">
      <h1
        className="text-xl font-semibold"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Settings
      </h1>

      {/* Connection Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Connection</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-4">
            <Input
              label="Gateway URL"
              value={gatewayUrl}
              onChange={(e) => setGatewayUrl(e.target.value)}
              placeholder="http://localhost:8000"
            />
            <Input
              label="Seller URL"
              value={sellerUrl}
              onChange={(e) => setSellerUrl(e.target.value)}
              placeholder="http://localhost:8001"
            />
          </div>
        </CardBody>
      </Card>

      {/* Autopilot Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Autopilot</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                Tick Interval (seconds)
              </label>
              <input
                type="number"
                min={1}
                max={60}
                value={interval}
                onChange={(e) => setInterval(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-24 px-2.5 py-1.5 rounded text-sm border"
                style={{
                  background: 'var(--color-bg-elevated)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Minimum: 1 second
              </span>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                Default Preset
              </label>
              <div className="flex flex-col gap-2">
                {PRESETS.map((p) => (
                  <label
                    key={p}
                    className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                      preset === p ? 'border-zinc-600' : 'hover:border-zinc-700'
                    }`}
                    style={{
                      background: preset === p ? 'var(--color-bg-elevated)' : 'var(--color-bg-primary)',
                      borderColor: preset === p ? 'var(--color-border-strong)' : 'var(--color-border)',
                    }}
                  >
                    <input
                      type="radio"
                      name="preset"
                      value={p}
                      checked={preset === p}
                      onChange={() => setPreset(p)}
                      className="mt-0.5"
                    />
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={p === 'happy' ? 'pass' : p === 'slow' ? 'warning' : 'fail'}
                        >
                          {p.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        {presetDesc[p]}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Display / Polling */}
      <Card>
        <CardHeader>
          <CardTitle>Display & Polling</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
            How often each data source refreshes in the background (seconds).
          </p>
          <div className="divide-y" style={{ borderColor: 'var(--color-border-subtle)' }}>
            <NumberInput label="Balance refresh interval" value={balancePoll} onChange={setBalancePoll} min={2} max={120} />
            <NumberInput label="Receipts refresh interval" value={receiptPoll} onChange={setReceiptPoll} min={1} max={60} />
            <NumberInput label="Events refresh interval" value={eventPoll} onChange={setEventPoll} min={1} max={30} />
          </div>
        </CardBody>
      </Card>

      {/* Current state */}
      <Card>
        <CardHeader>
          <CardTitle>Current State</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-1.5 text-xs">
            {[
              ['Gateway URL', store.gatewayUrl],
              ['Seller URL', store.sellerUrl],
              ['Autopilot Tick', `${store.autopilotInterval}s`],
              ['Default Preset', store.currentPreset],
              ['Balance Poll', `${store.balancePollInterval}s`],
              ['Receipts Poll', `${store.receiptPollInterval}s`],
              ['Events Poll', `${store.eventPollInterval}s`],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
                <span className="font-mono" style={{ color: 'var(--color-text-secondary)' }}>{value}</span>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Actions */}
      <div className="flex items-center gap-2 justify-end">
        {isDirty && (
          <span className="text-xs" style={{ color: 'var(--color-warning)' }}>
            Unsaved changes
          </span>
        )}
        <Button variant="ghost" size="md" onClick={handleReset}>
          Reset to Defaults
        </Button>
        <Button variant="primary" size="md" onClick={handleSave}>
          Save Settings
        </Button>
      </div>
    </div>
  )
}
