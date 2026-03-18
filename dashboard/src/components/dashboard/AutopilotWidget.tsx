import React, { useState } from 'react'
import { Play, Square, ChevronDown, ChevronUp } from 'lucide-react'
import { useAutopilotStore } from '../../store/autopilot'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { useSettingsStore } from '../../store/settings'
import { formatAmount, formatLatency, shortId } from '../../lib/format'
import type { SimPreset } from '../../types'

const PRESETS: SimPreset[] = ['happy', 'slow', 'breaches']

const presetStyles: Record<SimPreset, string> = {
  happy: 'bg-green-900 text-green-300 border border-green-800',
  slow: 'bg-amber-900 text-amber-300 border border-amber-800',
  breaches: 'bg-red-900 text-red-300 border border-red-800',
}

function MetricCell({
  label,
  value,
  mono = false,
}: {
  label: string
  value: React.ReactNode
  mono?: boolean
}) {
  return (
    <div
      className="rounded p-3 border flex flex-col gap-1 transition-colors hover:border-zinc-600"
      style={{
        background: 'var(--color-bg-primary)',
        borderColor: 'var(--color-border-subtle)',
      }}
    >
      <div
        className="text-xs uppercase tracking-wide"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </div>
      <div
        className={`text-sm font-medium ${mono ? 'font-mono' : ''} truncate`}
        style={{ color: 'var(--color-text-primary)' }}
      >
        {value ?? '—'}
      </div>
    </div>
  )
}

export function AutopilotWidget() {
  const isRunning = useAutopilotStore((s) => s.isRunning)
  const toggle = useAutopilotStore((s) => s.toggle)
  const lastResult = useAutopilotStore((s) => s.lastResult)
  const tickCount = useAutopilotStore((s) => s.tickCount)
  const [detailOpen, setDetailOpen] = useState(false)

  const autopilotInterval = useSettingsStore((s) => s.autopilotInterval)
  const setAutopilotInterval = useSettingsStore((s) => s.setAutopilotInterval)
  const currentPreset = useSettingsStore((s) => s.currentPreset)
  const setPreset = useSettingsStore((s) => s.setPreset)

  const r = lastResult
  const llm = r?.llm_policy
  const token = 'USDT'
  const slaStatus = r ? (r.ok && r.validation_passed ? 'PASS' : 'BREACH') : null
  const slaVariant = r ? (r.ok && r.validation_passed ? 'pass' : 'fail') : 'neutral'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>SLA Evaluator</CardTitle>
          <Badge variant={isRunning ? 'pass' : 'neutral'}>
            {isRunning ? '● RUNNING' : 'STOPPED'}
          </Badge>
          {tickCount > 0 && (
            <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
              ×{tickCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Preset selector */}
          <div className="flex items-center gap-1">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  currentPreset === p ? presetStyles[p] : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          {/* Interval input */}
          <div className="flex items-center gap-1">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              every
            </span>
            <input
              type="number"
              min={1}
              max={60}
              value={autopilotInterval}
              onChange={(e) =>
                setAutopilotInterval(Math.max(1, parseInt(e.target.value) || 1))
              }
              className="w-12 px-1.5 py-0.5 rounded text-xs font-mono border text-center"
              style={{
                background: 'var(--color-bg-elevated)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
              disabled={isRunning}
            />
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>s</span>
          </div>
          <Button variant={isRunning ? 'danger' : 'primary'} size="sm" onClick={toggle}>
            {isRunning ? <><Square size={12} /> Stop</> : <><Play size={12} /> Start</>}
          </Button>
        </div>
      </CardHeader>

      <CardBody>
        {/* 5 core metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <MetricCell label="Mode" value={currentPreset} />
          <MetricCell
            label="SLA Status"
            value={
              slaStatus ? (
                <Badge variant={slaVariant as 'pass' | 'fail' | 'neutral'}>{slaStatus}</Badge>
              ) : (
                '—'
              )
            }
          />
          <MetricCell label="Payout" value={formatAmount(r?.payout, token)} mono />
          <MetricCell label="Refund" value={formatAmount(r?.refund, token)} mono />
          <MetricCell
            label="LLM Judge"
            value={
              llm?.mode === 'llm' ? (
                <Badge variant={llm.sla_pass ? 'pass' : 'fail'}>
                  {llm.sla_pass ? 'PASS' : 'FAIL'}
                </Badge>
              ) : (
                '—'
              )
            }
          />
        </div>

        {/* Expandable details */}
        {r && (
          <div className="mt-3">
            <button
              onClick={() => setDetailOpen((v) => !v)}
              className="flex items-center gap-1 text-xs transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {detailOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {detailOpen ? 'Hide' : 'Show'} details
              {r.request_id && (
                <span className="font-mono ml-1" style={{ color: 'var(--color-text-muted)' }}>
                  ({shortId(r.request_id)})
                </span>
              )}
            </button>

            {detailOpen && (
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
                <MetricCell label="Request ID" value={shortId(r.request_id)} mono />
                <MetricCell
                  label="Latency"
                  value={r.latency_ms ? formatLatency(r.latency_ms) : '—'}
                  mono
                />
                <MetricCell label="LLM Model" value={llm?.model ?? '—'} />
                <MetricCell
                  label="LLM Confidence"
                  value={
                    llm?.confidence !== undefined
                      ? `${(llm.confidence * 100).toFixed(0)}%`
                      : '—'
                  }
                />
                <MetricCell
                  label="LLM Payout"
                  value={formatAmount(llm?.recommended_payout, token)}
                  mono
                />
                <MetricCell
                  label="LLM Reason"
                  value={
                    <span title={llm?.reason ?? ''} className="truncate block max-w-full">
                      {llm?.reason ?? '—'}
                    </span>
                  }
                />
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
