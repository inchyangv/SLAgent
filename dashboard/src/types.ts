// ── Receipt (matches actual gateway API response) ─────────────────────────────

export interface LLMPolicy {
  mode?: string          // 'llm' | 'disabled'
  sla_pass?: boolean
  recommended_payout?: string | number
  confidence?: number
  reason?: string
  model?: string
}

export interface ValidationResult {
  type?: string
  schema_id?: string
  pass?: boolean
  details?: string | null
}

export interface Receipt {
  request_id: string
  mandate_id?: string
  buyer?: string
  seller?: string
  gateway?: string
  timestamps?: {
    t_request_received?: string
    t_first_token?: string
    t_response_done?: string
  }
  metrics?: {
    ttft_ms?: number
    latency_ms?: number
  }
  outcome?: {
    success?: boolean
    error_code?: string | null
    llm_policy?: LLMPolicy
  }
  validation?: {
    overall_pass?: boolean
    results?: ValidationResult[]
  }
  pricing?: {
    max_price?: string
    computed_payout?: string
    computed_refund?: string
    rule_applied?: string
    breach_reasons?: string[]
  }
  hashes?: {
    request_hash?: string
    response_hash?: string
    receipt_hash?: string
  }
  signatures?: {
    gateway_signature?: string
  }
  attestations?: {
    count?: number
    complete?: boolean
    all_verified?: boolean
    parties_signed?: string[]
  }
  breach_reasons?: string[]
  settlement?: {
    tx_hash?: string
    block?: number
    status?: string
  }
}

// ── Balances ──────────────────────────────────────────────────────────────────

export interface BalancesResponse {
  available?: boolean
  error?: string | null
  token?: {
    symbol: string
    address?: string
    decimals?: number
  }
  roles?: {
    buyer?: { address?: string; balance?: string | number }
    seller?: { address?: string; balance?: string | number }
    gateway?: { address?: string; balance?: string | number }
  }
  updated_at?: number  // unix timestamp
}

// ── Mandate ───────────────────────────────────────────────────────────────────

export interface Mandate {
  mandate_id?: string
  offer_id?: string
  version?: string
  chain_id?: number
  settlement_contract?: string
  payment_token?: string
  seller?: string
  buyer?: string
  max_price?: string
  base_pay?: string
  bonus_rules?: {
    type?: string
    tiers?: Array<{ lte_ms: number; payout: string }>
  }
  timeout_ms?: number
  validators?: Array<{ type: string; schema_id?: string }>
  dispute?: {
    window_seconds?: number
    bond_amount?: string
    resolver?: string
  }
  created_at?: string
  expires_at?: string
  seller_signature?: string
  buyer_signature?: string
}

// ── Event ─────────────────────────────────────────────────────────────────────

export interface Event {
  kind: string
  ts?: number           // unix timestamp
  ts_iso?: string       // ISO string
  request_id?: string
  mandate_id?: string
  data?: Record<string, unknown>
}

// ── Demo / Autopilot ──────────────────────────────────────────────────────────

export interface SimulatorConfig {
  force_schema_fail: boolean
  force_upstream_error: boolean
  force_timeout: boolean
}

export interface DemoRunPayload {
  modes?: string[]
  scenario?: string
  seller_url?: string
  delay_ms?: number
  simulator?: SimulatorConfig
  negotiate?: boolean
  autopilot_mode?: string
}

export interface DemoRunResult {
  request_id?: string
  ok?: boolean
  validation_passed?: boolean
  payout?: string        // raw µUSDT string
  refund?: string        // raw µUSDT string
  max_price?: string
  latency_ms?: number
  llm_policy?: LLMPolicy
  error?: string
}

// ── Dispute ───────────────────────────────────────────────────────────────────

export interface DisputeState {
  request_id?: string
  status?: string        // 'open' | 'resolved' | 'finalized'
  bond_amount?: string | number
  final_payout?: string | number
  opened_at?: string
  resolved_at?: string
  finalized_at?: string
  detail?: string        // error message
}

// ── Seller Capabilities ───────────────────────────────────────────────────────

export interface SellerCapabilities {
  seller_address?: string
  llm_provider?: string
  llm_model?: string
  llm_available?: boolean
  supported_schemas?: string[]
  supported_modes?: string[]
}

// ── Simulation Presets ────────────────────────────────────────────────────────

export type SimPreset = 'happy' | 'slow' | 'breaches'

export const SIM_PRESETS: Record<
  SimPreset,
  { label: string; autopilot_mode: string; delay_ms: number; simulator: SimulatorConfig }
> = {
  happy: {
    label: 'Happy Path',
    autopilot_mode: 'fast',
    delay_ms: 0,
    simulator: { force_schema_fail: false, force_upstream_error: false, force_timeout: false },
  },
  slow: {
    label: 'Slow SLA',
    autopilot_mode: 'slow',
    delay_ms: 4000,
    simulator: { force_schema_fail: false, force_upstream_error: false, force_timeout: false },
  },
  breaches: {
    label: 'Breaches',
    autopilot_mode: 'invalid',
    delay_ms: 0,
    simulator: { force_schema_fail: true, force_upstream_error: true, force_timeout: false },
  },
}
