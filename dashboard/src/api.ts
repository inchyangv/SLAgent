import type {
  Receipt,
  BalancesResponse,
  Mandate,
  Event,
  DemoRunPayload,
  DemoRunResult,
  DisputeState,
  SellerCapabilities,
} from './types'

const DEFAULT_TIMEOUT = 15000

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`
      try {
        const body = await res.json()
        errMsg = body.detail ?? body.message ?? errMsg
      } catch {
        // ignore parse error
      }
      throw new Error(errMsg)
    }
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timer)
  }
}

// ── Receipts ──────────────────────────────────────────────────────────────────

export async function fetchReceipts(gatewayUrl: string, limit = 100): Promise<Receipt[]> {
  return apiFetch<Receipt[]>(`${gatewayUrl}/v1/receipts?limit=${limit}`)
}

export async function fetchReceipt(gatewayUrl: string, requestId: string): Promise<Receipt> {
  return apiFetch<Receipt>(`${gatewayUrl}/v1/receipts/${encodeURIComponent(requestId)}`)
}

// ── Balances ──────────────────────────────────────────────────────────────────

export async function fetchBalances(gatewayUrl: string): Promise<BalancesResponse> {
  return apiFetch<BalancesResponse>(`${gatewayUrl}/v1/balances`)
}

// ── Mandates ──────────────────────────────────────────────────────────────────

export async function fetchMandates(gatewayUrl: string): Promise<{ mandates: Mandate[] }> {
  return apiFetch<{ mandates: Mandate[] }>(`${gatewayUrl}/v1/mandates`)
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function fetchEvents(
  gatewayUrl: string,
  kind?: string,
  limit = 80,
  requestId?: string,
  mandateId?: string,
): Promise<{ events: Event[] }> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (kind) params.set('kind', kind)
  if (requestId) params.set('request_id', requestId)
  if (mandateId) params.set('mandate_id', mandateId)
  return apiFetch<{ events: Event[] }>(`${gatewayUrl}/v1/events?${params}`)
}

// ── Demo / Autopilot ──────────────────────────────────────────────────────────

export async function runDemo(
  gatewayUrl: string,
  payload: DemoRunPayload,
): Promise<{ results: DemoRunResult[] }> {
  return apiFetch<{ results: DemoRunResult[] }>(`${gatewayUrl}/v1/demo/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function fetchDemoOffers(gatewayUrl: string): Promise<unknown> {
  return apiFetch<unknown>(`${gatewayUrl}/v1/demo/offers`)
}

// ── Disputes ──────────────────────────────────────────────────────────────────

export async function openDispute(
  gatewayUrl: string,
  requestId: string,
  bondAmount?: number,
): Promise<DisputeState> {
  return apiFetch<DisputeState>(`${gatewayUrl}/v1/disputes/open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: requestId,
      ...(bondAmount !== undefined ? { bond_amount: bondAmount } : {}),
    }),
  })
}

export async function resolveDispute(
  gatewayUrl: string,
  requestId: string,
  finalPayout: number,
): Promise<DisputeState> {
  return apiFetch<DisputeState>(`${gatewayUrl}/v1/disputes/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, final_payout: finalPayout }),
  })
}

export async function finalizeDispute(
  gatewayUrl: string,
  requestId: string,
): Promise<DisputeState> {
  return apiFetch<DisputeState>(`${gatewayUrl}/v1/disputes/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId }),
  })
}

export async function fetchDispute(gatewayUrl: string, requestId: string): Promise<DisputeState> {
  return apiFetch<DisputeState>(
    `${gatewayUrl}/v1/disputes/${encodeURIComponent(requestId)}`,
  )
}

// ── Seller ────────────────────────────────────────────────────────────────────

export async function fetchSellerCapabilities(sellerUrl: string): Promise<SellerCapabilities> {
  return apiFetch<SellerCapabilities>(`${sellerUrl}/seller/capabilities`)
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function fetchHealth(gatewayUrl: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`${gatewayUrl}/v1/health`)
}
