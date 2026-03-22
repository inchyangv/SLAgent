import { useCallback, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react'
import { useSettingsStore } from '../store/settings'
import { useAutopilotStore } from '../store/autopilot'
import { useReceipts } from '../hooks/useReceipts'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { BalancePanel } from '../components/dashboard/BalancePanel'
import { HeroStats } from '../components/dashboard/HeroStats'
import { AutopilotWidget } from '../components/dashboard/AutopilotWidget'
import { NegotiationHistory } from '../components/dashboard/NegotiationHistory'
import { EventTimeline } from '../components/dashboard/EventTimeline'
import { ReceiptsTable } from '../components/dashboard/ReceiptsTable'
import { DisputePanel } from '../components/dashboard/DisputePanel'
import { MandateList } from '../components/dashboard/MandateList'
import { SellerCapabilities } from '../components/dashboard/SellerCapabilities'
import { ActivityLog } from '../components/dashboard/ActivityLog'
import { LatencyChart, PayoutChart, PassFailChart } from '../components/dashboard/Charts'
import { SimulatorControls } from '../components/dashboard/SimulatorControls'
import type { SimPreset } from '../types'

const PRESET_STYLES: Record<SimPreset, { active: string; label: string }> = {
  happy: { active: 'bg-green-950 text-green-300 border-green-800', label: 'Happy Path' },
  slow: { active: 'bg-amber-950 text-amber-300 border-amber-800', label: 'Slow SLA' },
  breaches: { active: 'bg-red-950 text-red-300 border-red-800', label: 'Breaches' },
}

const PRESET_BADGE: Record<SimPreset, 'pass' | 'warning' | 'fail'> = {
  happy: 'pass',
  slow: 'warning',
  breaches: 'fail',
}

function SectionTitle({ children, href }: { children: ReactNode; href?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2
        className="text-xs font-semibold uppercase tracking-widest"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {children}
      </h2>
      {href && (
        <Link
          to={href}
          className="flex items-center gap-1 text-xs transition-colors"
          style={{ color: 'var(--color-accent)' }}
        >
          View All
          <ArrowRight size={11} />
        </Link>
      )}
    </div>
  )
}

export function DashboardPage() {
  const qc = useQueryClient()
  const [configOpen, setConfigOpen] = useState(false)

  const gatewayUrl = useSettingsStore((s) => s.gatewayUrl)
  const sellerUrl = useSettingsStore((s) => s.sellerUrl)
  const setGatewayUrl = useSettingsStore((s) => s.setGatewayUrl)
  const setSellerUrl = useSettingsStore((s) => s.setSellerUrl)
  const currentPreset = useSettingsStore((s) => s.currentPreset)
  const setPreset = useSettingsStore((s) => s.setPreset)

  const isRunning = useAutopilotStore((s) => s.isRunning)
  const { receipts, isLoading: receiptsLoading, refetch: refetchReceipts } = useReceipts({
    isAutopilotRunning: isRunning,
  })

  const handleRefreshAll = useCallback(() => {
    void qc.invalidateQueries()
  }, [qc])

  return (
    <div className="max-w-screen-2xl mx-auto px-4 py-4 flex flex-col gap-5">

      {/* ─── Config bar (collapsible) ─── */}
      <div
        className="rounded-md border overflow-hidden"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <button
          className="w-full flex items-center justify-between px-4 py-2 text-xs transition-colors"
          style={{
            background: 'var(--color-bg-elevated)',
            color: 'var(--color-text-secondary)',
          }}
          onClick={() => setConfigOpen((v) => !v)}
        >
          <div className="flex items-center gap-3">
            <span className="font-medium">Config</span>
            <span className="font-mono" style={{ color: 'var(--color-text-muted)' }}>
              {gatewayUrl}
            </span>
            <Badge variant={PRESET_BADGE[currentPreset]} className="text-xs">
              {PRESET_STYLES[currentPreset].label}
            </Badge>
          </div>
          {configOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {configOpen && (
          <div
            className="flex flex-wrap items-end gap-3 px-4 py-3 border-t"
            style={{
              background: 'var(--color-bg-secondary)',
              borderColor: 'var(--color-border)',
            }}
          >
            <Input
              label="Gateway URL"
              value={gatewayUrl}
              onChange={(e) => setGatewayUrl(e.target.value)}
              className="w-52"
            />
            <Input
              label="Seller URL"
              value={sellerUrl}
              onChange={(e) => setSellerUrl(e.target.value)}
              className="w-52"
            />

            {/* Preset buttons */}
            <div className="flex flex-col gap-1">
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Scenario Preset
              </span>
              <div className="flex gap-1">
                {(Object.keys(PRESET_STYLES) as SimPreset[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPreset(p)}
                    className={`px-2.5 py-1 rounded text-xs font-medium capitalize transition-colors border ${
                      currentPreset === p
                        ? PRESET_STYLES[p].active
                        : 'bg-transparent border-zinc-800 hover:border-zinc-600'
                    }`}
                    style={
                      currentPreset !== p ? { color: 'var(--color-text-secondary)' } : undefined
                    }
                  >
                    {PRESET_STYLES[p].label}
                  </button>
                ))}
              </div>
            </div>

            <Button variant="default" size="sm" onClick={handleRefreshAll}>
              <RefreshCw size={13} />
              Refresh All
            </Button>

            <Link
              to="/settings"
              className="text-xs transition-colors"
              style={{ color: 'var(--color-accent)' }}
            >
              Full Settings →
            </Link>
          </div>
        )}
      </div>

      {/* ─── Hero Stats ─── */}
      <section>
        <SectionTitle>Overview</SectionTitle>
        <HeroStats receipts={receipts} />
      </section>

      {/* ─── Charts ─── */}
      <section>
        <SectionTitle>Analytics</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <LatencyChart receipts={receipts} slaThresholdMs={2000} />
          <PayoutChart receipts={receipts} />
          <PassFailChart receipts={receipts} />
        </div>
      </section>

      {/* ─── Primary row: Balance + Mandate ─── */}
      <section>
        <SectionTitle>Protocol State</SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BalancePanel />
          <MandateList />
        </div>
      </section>

      {/* ─── Autopilot + Simulator ─── */}
      <section>
        <SectionTitle>SLA Evaluator & Simulator</SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AutopilotWidget />
          <SimulatorControls />
        </div>
      </section>

      {/* ─── Negotiation + Seller Caps ─── */}
      <section>
        <SectionTitle>Negotiation & Seller</SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <NegotiationHistory />
          <SellerCapabilities />
        </div>
      </section>

      {/* ─── Disputes + Activity Log ─── */}
      <section>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DisputePanel />
          <ActivityLog />
        </div>
      </section>

      {/* ─── Event Timeline ─── */}
      <section>
        <SectionTitle>Event Timeline</SectionTitle>
        <EventTimeline />
      </section>

      {/* ─── Receipts (preview) ─── */}
      <section>
        <SectionTitle href="/receipts">Recent Receipts</SectionTitle>
        <ReceiptsTable
          receipts={receipts.slice(0, 25)}
          isLoading={receiptsLoading}
          onRefresh={() => void refetchReceipts()}
        />
      </section>
    </div>
  )
}
