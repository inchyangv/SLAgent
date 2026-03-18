import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'
import type { Receipt } from '../../types'

const ACCENT = '#4a9eff'
const SUCCESS = '#22c55e'
const ERROR = '#ef4444'
const WARNING = '#f59e0b'
const MUTED = '#333333'
const TEXT = '#999999'

function parseAmount(val: string | number | undefined): number {
  if (val === undefined || val === null) return 0
  return Number(val) / 1_000_000
}

// ── Latency Line Chart ─────────────────────────────────────────────────────

interface LatencyChartProps {
  receipts: Receipt[]
  slaThresholdMs?: number
}

export function LatencyChart({ receipts, slaThresholdMs = 2000 }: LatencyChartProps) {
  const data = receipts
    .slice()
    .reverse()
    .slice(-30)
    .map((r, i) => ({
      i,
      latency: r.metrics?.latency_ms ?? null,
      pass: r.validation?.overall_pass,
    }))

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Latency Trend</CardTitle>
        </CardHeader>
        <CardBody>
          <EmptyChart />
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Latency Trend</CardTitle>
        <span className="text-xs" style={{ color: TEXT }}>
          last {data.length} requests (ms)
        </span>
      </CardHeader>
      <CardBody className="py-2">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid stroke={MUTED} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="i" hide />
            <YAxis tick={{ fill: TEXT, fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: '#161616',
                border: '1px solid #333',
                borderRadius: 6,
                fontSize: 11,
              }}
              formatter={(v: unknown) => [`${v}ms`, 'Latency']}
            />
            <ReferenceLine
              y={slaThresholdMs}
              stroke={WARNING}
              strokeDasharray="4 2"
              label={{ value: `SLA ${slaThresholdMs}ms`, fill: WARNING, fontSize: 9, position: 'insideTopRight' }}
            />
            <Line
              type="monotone"
              dataKey="latency"
              stroke={ACCENT}
              strokeWidth={2}
              dot={{ r: 3, fill: ACCENT, stroke: ACCENT }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  )
}

// ── Payout Bar Chart ───────────────────────────────────────────────────────

interface PayoutChartProps {
  receipts: Receipt[]
}

export function PayoutChart({ receipts }: PayoutChartProps) {
  const data = receipts
    .slice()
    .reverse()
    .slice(-20)
    .map((r, i) => ({
      i,
      payout: parseAmount(r.pricing?.computed_payout),
      refund: parseAmount(r.pricing?.computed_refund),
      pass: r.validation?.overall_pass,
    }))

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Payout Distribution</CardTitle>
        </CardHeader>
        <CardBody>
          <EmptyChart />
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Payout Distribution</CardTitle>
        <span className="text-xs" style={{ color: TEXT }}>
          last {data.length} (USDT)
        </span>
      </CardHeader>
      <CardBody className="py-2">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid stroke={MUTED} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="i" hide />
            <YAxis tick={{ fill: TEXT, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip
              contentStyle={{
                background: '#161616',
                border: '1px solid #333',
                borderRadius: 6,
                fontSize: 11,
              }}
              formatter={(v: unknown, name: unknown) => [`$${Number(v).toFixed(4)}`, String(name)]}
            />
            <Bar dataKey="payout" name="Payout" stackId="a" fill={SUCCESS} radius={[0, 0, 0, 0]} />
            <Bar dataKey="refund" name="Refund" stackId="a" fill={ACCENT} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  )
}

// ── Pass/Fail Donut ────────────────────────────────────────────────────────

interface PassFailChartProps {
  receipts: Receipt[]
}

export function PassFailChart({ receipts }: PassFailChartProps) {
  const pass = receipts.filter((r) => r.validation?.overall_pass).length
  const fail = receipts.length - pass

  if (receipts.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pass / Fail</CardTitle>
        </CardHeader>
        <CardBody>
          <EmptyChart />
        </CardBody>
      </Card>
    )
  }

  const pieData = [
    { name: 'Pass', value: pass, color: SUCCESS },
    { name: 'Fail', value: fail, color: ERROR },
  ]

  const passRate = receipts.length > 0 ? Math.round((pass / receipts.length) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pass / Fail</CardTitle>
        <span className="text-xs font-mono" style={{ color: SUCCESS }}>
          {passRate}% pass rate
        </span>
      </CardHeader>
      <CardBody className="py-2">
        <div className="flex items-center gap-4">
          <ResponsiveContainer width={130} height={130}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={56}
                paddingAngle={2}
                dataKey="value"
                startAngle={90}
                endAngle={-270}
              >
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#161616', border: '1px solid #333', borderRadius: 6, fontSize: 11 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-2">
            <div>
              <div className="text-2xl font-bold font-mono" style={{ color: SUCCESS }}>
                {pass}
              </div>
              <div className="text-xs" style={{ color: TEXT }}>
                Pass
              </div>
            </div>
            <div>
              <div className="text-2xl font-bold font-mono" style={{ color: ERROR }}>
                {fail}
              </div>
              <div className="text-xs" style={{ color: TEXT }}>
                Fail
              </div>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────

function EmptyChart() {
  return (
    <div className="flex flex-col items-center py-8 gap-2">
      <span className="text-2xl">📊</span>
      <p className="text-xs" style={{ color: TEXT }}>
        No data yet
      </p>
    </div>
  )
}
