<!-- PROJECT.md -->

# SLAgent-402
**Tagline:** Don’t pay upfront. Pay by proof.

## 0) What This Project Is
SLAgent-402 is a **pay-by-performance settlement layer** for agent-to-agent API calls. It sits between a **Buyer Agent** and a **Seller Agent** (or any AI-powered API), measures **QoS + deterministic validity**, generates a signed **Performance Receipt**, and then settles payment on-chain with **automatic split + refund**.

Core design principle:
- Use **x402 HTTP payments** for standardized “pay to access” gating.
- Use **`exact(max_price)` + on-chain refund** to emulate “pay up to” behavior without inventing a new payment scheme.
- Use **optimistic settlement + disputes** (bonded challenge) to avoid expensive third-party judging on every request.
- Prefer **deterministic validators** (schema/test harness) over subjective “LLM scoring.”

This is built for **high-frequency micro-settlements** where gas fees and settlement friction would otherwise kill the product.

---

## 1) Why It Exists (Problem)
### 1.1 Fixed pricing is misaligned with real outcomes
In most AI API markets, the buyer pays the same whether:
- the response is fast or slow,
- the output is valid or malformed,
- the request succeeds or fails.

### 1.2 Agentic commerce needs verifiable proofs, not “trust”
When agents autonomously purchase services from other agents, the key missing piece is an objective, auditable mechanism for:
- what was promised (SLA),
- what was delivered (receipt),
- how payment was computed (pricing function),
- how disputes are handled (bonded challenge).

### 1.3 Micro-settlement must be operationally cheap
Per-call settlement at scale requires:
- near-zero incremental fees,
- fast finality,
- simple, reliable on-chain accounting.

---

## 2) The Solution (One Sentence)
SLAgent-402 converts “pay-to-call” agent services into **SLA-driven contracts** that settle using **proof (receipts)** rather than trust.

---

## 3) Core Concepts
### 3.1 SLA Mandate (What was promised)
A signed object that defines:
- maximum price (`max_price`) locked upfront
- base pay (`base_pay`) and performance bonus rules (`bonus_rules`)
- required validators (schema/tests)
- timeouts and dispute parameters
- settlement target (chain + contract)

**Key property:** the mandate is stable and hashable (Mandate ID = hash).

### 3.2 Performance Receipt (What happened)
A signed, structured artifact produced per request:
- timing metrics: `ttft_ms`, `latency_ms`
- execution outcome: `success`, `error_code`
- validator outputs: `schema_pass`, `tests_pass`, etc.
- pricing decision inputs and computed payout
- cryptographic references: request hash, response hash, receipt hash
- signatures (gateway attestation at minimum)

Receipts are stored off-chain for convenience but their **hash** is recorded on-chain for auditability.

### 3.3 Optimistic Settlement (Default fast path)
- Buyer pays `exact(max_price)` once.
- Gateway computes payout using the mandate + measured receipt.
- Settlement contract splits funds:
    - pays Seller `payout_amount`
    - refunds Buyer `max_price - payout_amount`
- Receipt hash is emitted on-chain.

### 3.4 Bonded Dispute (Only when challenged)
- Either party can open a dispute inside a `dispute_window`.
- Disputer posts a bond.
- Resolver re-checks deterministic validators (and optionally triggers an LLM judge).
- Wrongful disputes lose bond (slashing), reducing spam and griefing.

---

## 4) What We Will NOT Do (Explicit Scope Control)
- No subjective “hallucination penalty” on every call.
- No always-on third-party LLM scoring.
- No assumption that Coinbase Paymaster is available on every EVM chain.
- No attempt to fully solve “truth” for arbitrary natural language tasks.

Instead:
- Only validate what can be verified deterministically in the MVP.
- Add LLM judge only as an optional dispute tool.

---

## 5) User Stories
### Buyer Agent
- As a buyer, I want to pay **at most** the max price.
- As a buyer, I want a refund if the service is slow or fails validation.
- As a buyer, I want an audit trail proving why I paid what I paid.

### Seller Agent
- As a seller, I want a guaranteed base pay for successful valid work.
- As a seller, I want bonus for meeting SLA goals.
- As a seller, I want a dispute process if the buyer claims the receipt is wrong.

### Protocol Operator / Hackathon Demo
- As a demo operator, I want a dashboard that shows:
    - per-request receipt metrics,
    - payout/refund amounts,
    - on-chain transaction references,
    - a few curated scenarios (fast / slow / invalid).

---

## 6) Pricing Model (Bonus, Not Penalty)
SLAgent-402 uses:
- `max_price`: locked upfront
- `base_pay`: minimum payout for successful + valid output
- `bonus_pay`: additional payout based on performance targets

### Example (MVP Rule Set)
Assume: `max_price = $0.10`, `base_pay = $0.06`, `bonus_total = $0.04`

If **success + validators pass**:
- latency ≤ 2000ms → payout = 0.10
- 2000ms < latency ≤ 5000ms → payout = 0.08
- latency > 5000ms → payout = 0.06

If **error OR validators fail**:
- payout = 0.00 (full refund)

This aligns incentives:
- Sellers aren’t “punished into zero” for slight slowness.
- Buyers are protected from failures and invalid outputs.

---

## 7) Architecture Overview
### 7.1 Components
1) **Buyer Agent**
    - initiates API call
    - handles x402 402 challenge
    - signs payment

2) **SLAgent-402 Gateway (FastAPI)**
    - reverse proxy to Seller
    - measures TTFT/latency
    - runs validators
    - generates and signs receipts
    - calls on-chain settlement

3) **Seller Agent / Service**
    - AI model endpoint (streaming supported)
    - returns response for validator checks

4) **Facilitator (self-hosted)**
    - processes/verifies x402 payments
    - coordinates settlement transactions

5) **Settlement Contract (SKALE Base Sepolia (BITE v2 Sandbox 2))**
    - receives `max_price`
    - pays Seller and refunds Buyer according to computed payout
    - stores receipt hash via event logs
    - hosts dispute state machine (MVP: minimal)

6) **Dashboard**
    - shows real-time request ledger and metrics
    - links to on-chain tx/event

### 7.2 High-level Sequence
1. Buyer calls gateway endpoint.
2. Gateway responds `402 Payment Required` with x402 payment details.
3. Buyer resends request with x402 payment authorization for `exact(max_price)`.
4. Gateway forwards to Seller, measures TTFT/latency, validates output.
5. Gateway builds **Receipt**, signs it, computes `payout_amount`.
6. Gateway submits settlement transaction:
    - Seller receives payout
    - Buyer receives refund
    - Receipt hash is emitted
7. Optional: dispute within window.

---

## 8) Data Formats (Canonical)
### 8.1 SLA Mandate (JSON)
```json
{
  "version": "1.0",
  "mandate_id": "0x…(hash)",
  "chain_id": 12345,
  "settlement_contract": "0x…",
  "payment_token": "0x…",
  "seller": "0x…",
  "buyer": "0x…(optional, for private offers)",
  "max_price": "100000" ,
  "base_pay": "60000",
  "bonus_rules": {
    "type": "latency_tiers",
    "tiers": [
      { "lte_ms": 2000, "payout": "100000" },
      { "lte_ms": 5000, "payout": "80000" },
      { "lte_ms": 999999999, "payout": "60000" }
    ]
  },
  "timeout_ms": 8000,
  "validators": [
    { "type": "json_schema", "schema_id": "invoice_v1" }
  ],
  "dispute": {
    "window_seconds": 600,
    "bond_amount": "50000",
    "resolver": "0x…"
  },
  "created_at": "2026-02-12T00:00:00Z",
  "expires_at": "2026-02-20T00:00:00Z",
  "seller_signature": "0x…",
  "buyer_signature": "0x…(optional)"
}
```

Notes:
- Amounts are denominated in token smallest units (e.g., 6 decimals).
- `mandate_id` is deterministic: hash of the unsigned mandate payload.

### 8.2 Performance Receipt (JSON)
```json
{
  "version": "1.0",
  "mandate_id": "0x…",
  "request_id": "req_20260212_000001",
  "buyer": "0x…",
  "seller": "0x…",
  "gateway": "0x…",
  "timestamps": {
    "t_request_received": "2026-02-12T12:00:00.000Z",
    "t_first_token": "2026-02-12T12:00:00.450Z",
    "t_response_done": "2026-02-12T12:00:01.800Z"
  },
  "metrics": {
    "ttft_ms": 450,
    "latency_ms": 1800
  },
  "outcome": {
    "success": true,
    "error_code": null
  },
  "validation": {
    "overall_pass": true,
    "results": [
      {
        "type": "json_schema",
        "schema_id": "invoice_v1",
        "pass": true,
        "details": null
      }
    ]
  },
  "pricing": {
    "max_price": "100000",
    "computed_payout": "100000",
    "computed_refund": "0",
    "rule_applied": "latency_tier_lte_2000"
  },
  "hashes": {
    "request_hash": "0x…",
    "response_hash": "0x…",
    "receipt_hash": "0x…"
  },
  "signatures": {
    "gateway_signature": "0x…"
  }
}
```

---

## 9) On-chain Contracts (MVP)
### 9.1 Settlement Contract Responsibilities
- Hold `max_price` funds received via x402.
- Accept a settlement call with:
  - buyer, seller
  - payout amount
  - receipt hash
  - gateway signature (attestation)
- Transfer payout to seller.
- Refund remainder to buyer.
- Emit `Settled(mandate_id, request_id, payout, refund, receipt_hash)`.

### 9.2 Dispute (Minimal but Real)
MVP dispute is intentionally simple:
- `openDispute(request_id)` requires bond.
- `resolveDispute(request_id, final_payout)` callable by resolver.

On resolve:
- If `final_payout` differs, adjust via additional transfer (or escrow-style delayed payout in v2).
- Slash bond accordingly.
- Emit `Disputed` / `Resolved`.

Important:
- For hackathon MVP, we can implement disputes as either:
  - payout is delayed until window ends, or
  - immediate payout + dispute triggers a compensating transfer funded by a protocol reserve.
- The simplest MVP is to delay final payout until dispute window ends (escrow).
- This is safest and easiest to reason about.

---

## 10) Off-chain Services (Gateway + Facilitator)
### 10.1 Gateway responsibilities
- Enforce x402 payment gating (`402 Payment Required` challenge).
- Measure TTFT/latency precisely.
- Run validators.
- Sign receipts.
- Submit settlement transactions.

### 10.2 Facilitator responsibilities
- Verify x402 payment proofs.
- Coordinate token transfers and settlement calls.
- Optionally batch or optimize transaction submission.

Note:
- We deliberately allow self-hosted facilitator so we can settle on SKALE Base Sepolia (BITE v2 Sandbox 2) without relying on a specific hosted facilitator network support policy.

---

## 11) Deterministic Validation (MVP-first)
MVP validators (choose 1-2):
- JSON Schema validator:
  - response must be valid JSON matching schema
- SQL test harness (optional):
  - generated SQL must pass predefined test cases on a sample DB
- Function-call validator (optional):
  - tool-call arguments must validate and execution must succeed

Non-MVP:
- subjective grading, style checks, or "is this true?" for arbitrary facts

---

## 12) Demo Plan (Three Scenarios)
- Fast + valid -> full payout
- Slow but valid -> base + partial bonus
- Invalid output (schema fails) -> full refund

For each scenario, show:
- dashboard metrics (TTFT/latency/validation)
- receipt JSON
- on-chain settlement event and amounts

---

## 13) Repository Layout (Target)
```text
/contracts
  /src
  /test
  hardhat.config.ts (or foundry config)
/gateway
  app/main.py
  app/x402.py
  app/metrics.py
  app/validators/
  app/receipt.py
  app/settlement_client.py
  tests/
/facilitator
  (minimal service or library, depending on x402 SDK usage)
/dashboard
  (simple Next.js or static page reading gateway API)
/docs
  ARCHITECTURE.md
  API.md
  SECURITY.md
  DEMO.md
PROJECT.md
TICKET.md
```

---

## 14) Definition of Done (Global)
A ticket is DONE only if:
- acceptance criteria are met
- relevant tests exist and pass
- documentation is updated (at least README/DEMO where relevant)
- `TICKET.md` status is updated with completion notes

---

## 15) Roadmap (After Hackathon)
- support more validator types
- standardized receipt signing (multi-sig: buyer + seller + gateway)
- receipt storage/indexing layer
- reputation scoring for seller endpoints
- multi-chain settlement + cross-chain receipts
- optional AP2/A2A integration layer (mandate/receipt as protocol message types)
