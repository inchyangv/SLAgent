import React, { useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
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
import type { SimPreset } from '../types'

const presetColors: Record<SimPreset, 'pass' | 'warning' | 'fail'> = {
  happy: 'pass',
  slow: 'warning',
  breaches: 'fail',
}

const PRESETS: SimPreset[] = ['happy', 'slow', 'breaches']

export function DashboardPage() {
  const qc = useQueryClient()
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
    <div className="max-w-screen-2xl mx-auto px-4 py-4 flex flex-col gap-4">
      {/* Config bar */}
      <div
        className="flex flex-wrap items-end gap-3 p-3 rounded-md border"
        style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border)' }}
      >
        <div className="flex items-end gap-2 flex-1 min-w-[200px]">
          <Input
            label="Gateway URL"
            value={gatewayUrl}
            onChange={(e) => setGatewayUrl(e.target.value)}
            className="flex-1"
          />
        </div>
        <div className="flex items-end gap-2 flex-1 min-w-[200px]">
          <Input
            label="Seller URL"
            value={sellerUrl}
            onChange={(e) => setSellerUrl(e.target.value)}
            className="flex-1"
          />
        </div>
        <Button variant="default" size="sm" onClick={handleRefreshAll}>
          <RefreshCw size={13} />
          Refresh All
        </Button>
        <div className="flex items-center gap-1">
          {PRESETS.map((p) => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`px-2.5 py-1 rounded text-xs font-medium capitalize transition-colors border ${
                currentPreset === p
                  ? p === 'happy'
                    ? 'bg-green-900 text-green-300 border-green-800'
                    : p === 'slow'
                      ? 'bg-amber-900 text-amber-300 border-amber-800'
                      : 'bg-red-900 text-red-300 border-red-800'
                  : 'bg-transparent text-zinc-500 border-zinc-800 hover:text-zinc-300'
              }`}
            >
              {p}
            </button>
          ))}
          <Badge variant={presetColors[currentPreset]} className="ml-1">
            {currentPreset.toUpperCase()}
          </Badge>
        </div>
      </div>

      {/* Top shell: Balance panel */}
      <div className="flex flex-wrap gap-4 items-start">
        <div className="flex-1 min-w-[260px] max-w-sm">
          <BalancePanel />
        </div>
        <div className="flex-1 min-w-[300px]">
          <div
            className="p-4 rounded-md border h-full flex items-center"
            style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border)' }}
          >
            <div>
              <div
                className="text-2xl font-bold tracking-tight"
                style={{ color: 'var(--color-accent)' }}
              >
                SLAgent<span style={{ color: 'var(--color-text-muted)' }}>-402</span>
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Autonomous SLA Enforcement · Sepolia Testnet
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Autopilot */}
      <AutopilotWidget />

      {/* Negotiation History */}
      <NegotiationHistory />

      {/* Hero Stats */}
      <HeroStats receipts={receipts} />

      {/* 2-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SellerCapabilities />
        <MandateList />
        <DisputePanel />
        <ActivityLog />
      </div>

      {/* Event Timeline */}
      <EventTimeline />

      {/* Receipts Table */}
      <ReceiptsTable
        receipts={receipts}
        isLoading={receiptsLoading}
        onRefresh={() => void refetchReceipts()}
      />
    </div>
  )
}
