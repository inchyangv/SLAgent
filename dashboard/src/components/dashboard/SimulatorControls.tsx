import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { runDemo } from '../../api'
import { useSettingsStore } from '../../store/settings'
import { useLogStore } from '../../store/log'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import type { DemoRunResult } from '../../types'

// Latency tier thresholds (ms) from the default mandate
const TIER_FAST = 2000
const TIER_SLOW = 5000

function latencyBadge(ms: number): { label: string; variant: 'pass' | 'warning' | 'fail' } {
  if (ms <= TIER_FAST) return { label: 'Full Payout', variant: 'pass' }
  if (ms <= TIER_SLOW) return { label: 'Partial Payout', variant: 'warning' }
  return { label: 'Base Only', variant: 'fail' }
}

interface ResultRow {
  result: DemoRunResult
  delayMs: number
}

export function SimulatorControls() {
  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const sellerUrl = useSettingsStore((s) => s.sellerUrl)
  const addLog = useLogStore((s) => s.add)
  const qc = useQueryClient()

  // Slider & toggle state
  const [delayMs, setDelayMs] = useState(0)
  const [forceSchemaFail, setForceSchemaFail] = useState(false)
  const [forceUpstreamError, setForceUpstreamError] = useState(false)
  const [forceTimeout, setForceTimeout] = useState(false)
  const [history, setHistory] = useState<ResultRow[]>([])

  const tierInfo = latencyBadge(delayMs)

  const { mutate: run, isPending } = useMutation<{ results: DemoRunResult[] }, Error>({
    mutationFn: () => {
      const mode = forceSchemaFail ? 'invalid' : forceUpstreamError ? 'error' : forceTimeout ? 'timeout' : delayMs > TIER_FAST ? 'slow' : 'fast'
      return runDemo(gatewayUrl, {
        modes: [mode],
        seller_url: sellerUrl,
        delay_ms: delayMs,
        simulator: {
          force_schema_fail: forceSchemaFail,
          force_upstream_error: forceUpstreamError,
          force_timeout: forceTimeout,
        },
      })
    },
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['receipts'] })
      void qc.invalidateQueries({ queryKey: ['events'] })
      const r = data.results?.[0]
      if (r) {
        setHistory((h) => [{ result: r, delayMs }, ...h.slice(0, 9)])
        const ok = r.ok && r.validation_passed
        addLog(
          ok
            ? `Sim run OK — payout ${r.payout ?? '?'} latency ${r.latency_ms ?? '?'}ms`
            : `Sim run BREACH — ${r.error ?? 'validation/schema fail'}`,
          ok ? 'ok' : 'err',
        )
      }
    },
    onError: (err) => {
      addLog(`Sim run failed: ${err.message}`, 'err')
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>SLA Simulator</CardTitle>
        <Badge variant={forceSchemaFail || forceUpstreamError || forceTimeout ? 'fail' : tierInfo.variant}>
          {forceSchemaFail ? 'Schema Fail' : forceUpstreamError ? 'Upstream Error' : forceTimeout ? 'Timeout' : tierInfo.label}
        </Badge>
      </CardHeader>
      <CardBody className="space-y-4">

        {/* Latency slider */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
              Delay
            </label>
            <span className="text-xs font-mono" style={{ color: 'var(--color-text-primary)' }}>
              {delayMs === 0 ? '0ms (fast)' : `${delayMs}ms`}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={8000}
            step={100}
            value={delayMs}
            onChange={(e) => setDelayMs(Number(e.target.value))}
            disabled={forceUpstreamError || forceTimeout}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
            style={{ accentColor: 'var(--color-accent)' }}
          />
          {/* Tick markers */}
          <div className="flex justify-between mt-1">
            {[0, 2000, 5000, 8000].map((tick) => (
              <button
                key={tick}
                onClick={() => setDelayMs(tick)}
                className="text-xs transition-colors"
                style={{
                  color: delayMs === tick ? 'var(--color-accent)' : 'var(--color-text-muted)',
                  fontSize: '10px',
                }}
              >
                {tick === 0 ? '0' : `${tick / 1000}s`}
              </button>
            ))}
          </div>
        </div>

        {/* Force error toggles */}
        <div className="flex flex-wrap gap-3">
          {[
            { label: 'Schema Fail', value: forceSchemaFail, set: setForceSchemaFail },
            { label: 'Upstream Error', value: forceUpstreamError, set: setForceUpstreamError },
            { label: 'Timeout', value: forceTimeout, set: setForceTimeout },
          ].map(({ label, value, set }) => (
            <label key={label} className="flex items-center gap-1.5 cursor-pointer text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <input
                type="checkbox"
                checked={value}
                onChange={(e) => set(e.target.checked)}
                className="w-3.5 h-3.5 accent-red-500"
              />
              {label}
            </label>
          ))}
        </div>

        {/* Run button */}
        <Button
          onClick={() => run()}
          disabled={isPending}
          variant="default"
          size="sm"
          className="w-full"
        >
          {isPending
            ? <><Loader2 size={13} className="animate-spin" /> Running…</>
            : <><Play size={13} /> Run Scenario</>
          }
        </Button>

        {/* Recent results */}
        {history.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
              Recent Runs
            </div>
            {history.slice(0, 5).map((row, i) => {
              const ok = row.result.ok && row.result.validation_passed
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 py-1.5 px-2 rounded border text-xs"
                  style={{
                    background: 'var(--color-bg-primary)',
                    borderColor: 'var(--color-border-subtle)',
                  }}
                >
                  <Badge variant={ok ? 'pass' : 'fail'} className="shrink-0">
                    {ok ? 'OK' : 'BREACH'}
                  </Badge>
                  <span className="font-mono" style={{ color: 'var(--color-text-muted)' }}>
                    {row.delayMs}ms
                  </span>
                  {row.result.payout && (
                    <span style={{ color: 'var(--color-text-secondary)' }}>
                      payout {row.result.payout}
                    </span>
                  )}
                  {row.result.latency_ms != null && (
                    <span className="ml-auto font-mono" style={{ color: 'var(--color-text-muted)' }}>
                      {row.result.latency_ms}ms
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
