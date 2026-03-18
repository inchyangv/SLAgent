const DECIMALS = 1_000_000 // 6 decimal USDT (µUSDT → USDT)

export function formatAmount(
  raw: string | number | undefined | null,
  symbol?: string,
): string {
  if (raw === undefined || raw === null || raw === '') return '—'
  const n = typeof raw === 'string' ? parseFloat(raw) : raw
  if (isNaN(n)) return '—'
  const val = n / DECIMALS
  const sym = symbol ? ` ${symbol}` : ''

  if (Math.abs(val) >= 1_000_000) {
    return `${(val / 1_000_000).toFixed(2)}M${sym}`
  }
  if (Math.abs(val) >= 1_000) {
    return `${(val / 1_000).toFixed(2)}K${sym}`
  }
  // up to 4 decimal places, trimming trailing zeros
  const str = val.toFixed(4).replace(/\.?0+$/, '')
  return `${str}${sym}`
}

export function formatAmountShort(
  raw: string | number | undefined | null,
  symbol?: string,
): string {
  if (raw === undefined || raw === null || raw === '') return '—'
  const n = typeof raw === 'string' ? parseFloat(raw) : raw
  if (isNaN(n)) return '—'
  const val = n / DECIMALS
  const sym = symbol ? ` ${symbol}` : ''

  if (Math.abs(val) >= 1_000_000) {
    return `${(val / 1_000_000).toFixed(1)}M${sym}`
  }
  if (Math.abs(val) >= 1_000) {
    return `${(val / 1_000).toFixed(1)}K${sym}`
  }
  return `${val.toFixed(2)}${sym}`
}

export function shortAddr(addr: string | undefined | null): string {
  if (!addr) return '—'
  if (addr.length < 12) return addr
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}

export function shortHash(hash: string | undefined | null): string {
  if (!hash) return '—'
  if (hash.length < 14) return hash
  return `${hash.slice(0, 8)}…${hash.slice(-4)}`
}

export function shortId(id: string | undefined | null): string {
  if (!id) return '—'
  if (id.length <= 12) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

export function relativeTime(ts: string | undefined | null): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const diffMs = Date.now() - d.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 5) return '방금'
  if (diffSec < 60) return `${diffSec}초 전`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}분 전`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}시간 전`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}일 전`
}

export function formatDate(ts: string | undefined | null): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  return d.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatLatency(ms: number | undefined | null): string {
  if (ms === undefined || ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}
