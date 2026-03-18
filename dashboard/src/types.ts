// ── Receipt ───────────────────────────────────────────────────────────────────

export interface LLMPolicy {
  judge: string
  model: string
  passed: boolean
  reason: string
  confidence: number
  payout_ratio: number
  recommended_payout?: string | number
}

export interface ValidationResult {
  validator: string
  passed: boolean
  reason?: string
  breaches?: string[]
}

export interface Attestation {
  signer: string
  role: 'buyer' | 'seller' | 'gateway'
  signed: boolean
  signature?: string
  timestamp?: string
}

export interface Receipt {
  request_id: string
  mandate_id: string
  buyer_address: string
  seller_address: string
  gateway_address?: string
  token_address?: string
  token_symbol?: string
  gross_amount: string | number
  net_amount?: string | number
  service_fee?: string | number
  buyer_refund?: string | number
  seller_payout?: string | number
  latency_ms: number
  valid: boolean
  sla_status: 'pass' | 'fail' | 'partial'
  payout_rule: string
  schema_version?: string
  request_schema?: string
  response_schema?: string
  llm_policy?: LLMPolicy
  validations?: ValidationResult[]
  attestations?: {
    buyer?: Attestation
    seller?: Attestation
    gateway?: Attestation
  }
  buyer_attested?: boolean
  seller_attested?: boolean
  gateway_attested?: boolean
  receipt_hash?: string
  block_number?: number
  tx_hash?: string
  created_at?: string
  updated_at?: string
  metadata?: Record<string, unknown>
  raw?: Record<string, unknown>
}

// ── Balances ──────────────────────────────────────────────────────────────────

export interface RoleBalance {
  address: string
  balance: string | number
}

export interface TokenInfo {
  symbol: string
  decimals: number
  address?: string
}

export interface BalancesResponse {
  available: string | number
  error?: string
  token: TokenInfo
  roles: {
    buyer?: RoleBalance
    seller?: RoleBalance
    gateway?: RoleBalance
  }
  updated_at?: string
}

// ── Mandate ───────────────────────────────────────────────────────────────────

export interface Mandate {
  mandate_id: string
  buyer_address: string
  seller_address: string
  token_address?: string
  max_price: string | number
  schema_id?: string
  schema_version?: string
  request_schema?: string
  response_schema?: string
  sla_rules?: Record<string, unknown>
  payment_config?: Record<string, unknown>
  valid_until?: string
  created_at?: string
  status?: string
  raw?: Record<string, unknown>
}

// ── Event ─────────────────────────────────────────────────────────────────────

export interface Event {
  id?: string
  kind: string
  mandate_id?: string
  request_id?: string
  timestamp?: string
  created_at?: string
  data?: Record<string, unknown>
  payload?: Record<string, unknown>
  summary?: string
}

// ── Demo ──────────────────────────────────────────────────────────────────────

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
  mode?: string
  request_id?: string
  sla_status?: 'pass' | 'fail' | 'partial'
  valid?: boolean
  payout?: string | number
  refund?: string | number
  latency_ms?: number
  llm_policy?: LLMPolicy
  error?: string
  receipt?: Receipt
  raw?: Record<string, unknown>
}

// ── Dispute ───────────────────────────────────────────────────────────────────

export interface DisputeState {
  request_id: string
  status: 'open' | 'resolved' | 'finalized' | 'pending'
  bond_amount?: string | number
  final_payout?: string | number
  opened_at?: string
  resolved_at?: string
  finalized_at?: string
  buyer_address?: string
  seller_address?: string
  reason?: string
  resolution?: string
  raw?: Record<string, unknown>
}

// ── Seller Capabilities ───────────────────────────────────────────────────────

export interface SellerCapabilities {
  seller_address: string
  llm_provider?: string
  llm_model?: string
  llm_available?: boolean
  supported_schemas?: string[]
  supported_modes?: string[]
  raw?: Record<string, unknown>
}

// ── Simulation Presets ────────────────────────────────────────────────────────

export type SimPreset = 'happy' | 'slow' | 'breaches'

export const PRESETS: Record<SimPreset, DemoRunPayload> = {
  happy: {
    autopilot_mode: 'fast',
    delay_ms: 0,
    simulator: { force_schema_fail: false, force_upstream_error: false, force_timeout: false },
  },
  slow: {
    autopilot_mode: 'slow',
    delay_ms: 4000,
    simulator: { force_schema_fail: false, force_upstream_error: false, force_timeout: false },
  },
  breaches: {
    autopilot_mode: 'invalid',
    delay_ms: 0,
    simulator: { force_schema_fail: true, force_upstream_error: true, force_timeout: false },
  },
}
