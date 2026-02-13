# Architecture — SLA-Pay v2

## Agent Roles & Trust Boundaries

SLA-Pay v2 has three distinct agent roles. Each role has clear responsibilities and signing authority.

### Buyer Agent (`buyer_agent/`)

| Aspect | Detail |
|--------|--------|
| **Code path** | `buyer_agent/main.py` → `buyer_agent/client.py` |
| **Identity** | EVM address (`BUYER_ADDRESS`) + private key (`BUYER_PRIVATE_KEY`) |
| **LLM usage** | SHOULD use Gemini for negotiation strategy (draft requirements, evaluate quotes) |

**MUST:**
- Discover seller capabilities (`GET /seller/capabilities`)
- Negotiate SLA (select/accept mandate from quote or offer catalog)
- Handle `402 Payment Required` challenge (sign x402 authorization)
- Fund escrow: transfer `max_price` to settlement contract
- Verify receipt invariants deterministically after receiving response
- Open disputes when SLA is violated

**MUST NOT:**
- Compute pricing or validation (that is the gateway's job)
- Trust seller responses without receipt verification

### Seller Agent/Service (`seller/`)

| Aspect | Detail |
|--------|--------|
| **Code path** | `seller/main.py` → `seller/gemini_client.py` |
| **Identity** | EVM address (`SELLER_ADDRESS`) |
| **LLM usage** | MUST use Gemini for actual work execution (invoice generation, task completion) |

**MUST:**
- Expose capabilities (`GET /seller/capabilities`)
- Accept mandates from buyer (`POST /seller/mandates/accept`)
- Execute work via LLM: Gemini (`POST /seller/call`)
- Return schema-compliant output (e.g., `invoice_v1` JSON schema)
- Retry/correct LLM output to meet schema (up to 2 retries)

**MUST NOT:**
- Compute its own payout (gateway does this)
- Directly interact with settlement contract for payout

### Gateway (`gateway/app/`)

| Aspect | Detail |
|--------|--------|
| **Code path** | `gateway/app/main.py` (orchestration), `gateway/app/pricing.py`, `gateway/app/validators/`, `gateway/app/settlement_client.py` |
| **Identity** | EVM address (`GATEWAY_ADDRESS`) + private key (`GATEWAY_PRIVATE_KEY`) |
| **LLM usage** | MUST NOT use LLM for validation, pricing, or settlement (deterministic only) |

**MUST:**
- Gate access via x402 (`402 Payment Required` challenge)
- Verify payment authorization
- Forward requests to seller and measure TTFT/latency
- Run deterministic validators (JSON schema)
- Compute payout using integer arithmetic (base + bonus tiers)
- Generate and sign performance receipts
- Submit settlement transaction on-chain
- Emit receipt hash via `Settled` event

**MUST NOT:**
- Use LLM for any validation or pricing decision (breaks reproducibility)
- Hold buyer funds beyond escrow settlement window

### Resolver (optional, MVP)

| Aspect | Detail |
|--------|--------|
| **Code path** | `scripts/resolve_dispute.py`, `gateway/app/settlement_client.py` |
| **Identity** | EVM address (`RESOLVER_ADDRESS`) + private key (`RESOLVER_PRIVATE_KEY`) |

**MUST:**
- Resolve disputes by calling `resolveDispute(requestId, finalPayout)` on-chain
- Remain neutral (not buyer or seller in production; shared key acceptable for demo)

### Who Signs What

| Artifact | Signer(s) | Purpose |
|----------|-----------|---------|
| x402 payment authorization | **Buyer** | Proves buyer authorized `max_price` payment |
| Performance receipt | **Gateway** | Attests to measured metrics + validation + pricing |
| Receipt attestation | **Buyer, Seller, Gateway** | Multi-party agreement on receipt correctness |
| Settlement transaction | **Gateway** | Submits payout/refund split on-chain |
| Dispute open | **Buyer** (or seller) | Challenges a settlement with bond |
| Dispute resolution | **Resolver** | Final payout decision |

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                    OFF-CHAIN (subjective)                        │
│                                                                 │
│  Buyer Agent ◄──── Gemini (negotiation) ────► Seller Agent      │
│  (buyer_agent/)         LLM decisions         (seller/)         │
│                         NOT on-chain                            │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                    │
             ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                GATEWAY (deterministic boundary)                  │
│                                                                 │
│  x402 verify → forward → measure → validate → price → receipt   │
│  (gateway/app/)                                                 │
│  ALL decisions here are deterministic and reproducible           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ON-CHAIN (trustless)                          │
│                                                                 │
│  Settlement Contract (SKALE)                                    │
│  - escrow, split, refund, receipt hash, dispute                 │
│  (contracts/src/SLASettlement.sol)                               │
└─────────────────────────────────────────────────────────────────┘
```

### End-to-End Sequence

```
Buyer Agent          Gateway              Seller Agent         Settlement Contract
    │                    │                     │                      │
    │ 1. GET /seller/capabilities ────────────►│                      │
    │◄─────────────── capabilities ────────────│                      │
    │                    │                     │                      │
    │ 2. negotiate mandate (quote/accept)      │                      │
    │────────────────────────────────────────► │                      │
    │◄──────────── mandate accepted ───────────│                      │
    │                    │                     │                      │
    │ 3. POST /v1/call (no payment)            │                      │
    │───────────────────►│                     │                      │
    │◄── 402 Payment Required ─────────────────│                      │
    │                    │                     │                      │
    │ 4. POST /v1/call + X-PAYMENT (x402 auth) │                      │
    │───────────────────►│                     │                      │
    │                    │ 5. forward ────────►│                      │
    │                    │  (measure TTFT)      │                      │
    │                    │◄── response ────────│                      │
    │                    │  (measure latency)   │                      │
    │                    │                     │                      │
    │                    │ 6. validate (JSON schema, deterministic)    │
    │                    │ 7. compute payout (integer arithmetic)      │
    │                    │ 8. build + sign receipt                     │
    │                    │                     │                      │
    │                    │ 9. settle() ───────────────────────────────►│
    │                    │                     │    split payout/refund│
    │                    │◄───────────── tx_hash ─────────────────────│
    │                    │                     │                      │
    │◄── response + receipt + tx_hash          │                      │
    │                    │                     │                      │
    │ 10. verify receipt invariants (deterministic)                    │
    │ 11. (optional) attest receipt                                   │
    │ 12. (optional) open dispute if SLA violated                     │
    │                    │                     │                      │
```

---

## Chain & Token Strategy (MVP)

### Network: SKALE Europa (Testnet for demo)

- **Chain ID:** 1444673419
- **RPC:** `https://testnet.skalenodes.com/v1/juicy-low-small-testnet`
- **Key property:** Zero gas fees — ideal for high-frequency micro-settlements

Alternative (mainnet):
- **Chain ID:** 2046399126
- **RPC:** `https://mainnet.skalenodes.com/v1/elated-tan-skat`
- **Explorer:** `https://elated-tan-skat.explorer.mainnet.skalenodes.com`

### Token: ERC20 Mock (SLAToken)

For the hackathon MVP, we deploy a simple ERC20 mock token:

- **Name:** SLA Test Token
- **Symbol:** SLAT
- **Decimals:** 6
- **Rationale:** 6 decimals matches USDC convention and keeps amounts human-readable

### Amount Unit Conventions

All amounts in the protocol are denominated in the **smallest token unit** (6 decimals).

| Human Amount | On-chain Value | Description |
|-------------|---------------|-------------|
| $0.10       | 100000        | max_price   |
| $0.06       | 60000         | base_pay    |
| $0.04       | 40000         | bonus_total |
| $0.08       | 80000         | mid-tier payout |

### Integer Arithmetic Rules

- All pricing computations use **integer arithmetic only** (no floats).
- Rounding direction: **always round down** (favor buyer / protocol safety).
- `payout <= max_price` is an invariant enforced on-chain.
- `refund = max_price - payout` (exact subtraction, no rounding needed).

### Settlement Flow (On-chain)

1. Buyer's `max_price` is transferred to the Settlement contract (via x402 payment).
2. Gateway computes `payout` off-chain based on mandate rules + measured metrics.
3. Gateway calls `settle()` with signed receipt.
4. Contract transfers `payout` to seller, `max_price - payout` back to buyer.
5. Receipt hash emitted via `Settled` event.

### Component Diagram

```
                        ┌──────────────┐
   Buyer Agent ───────► │  SLA Gateway  │ ───────► Seller Agent
   (pays max_price)     │  (FastAPI)    │          (AI endpoint)
                        │              │
                        │  - metrics   │
                        │  - validate  │
                        │  - receipt   │
                        │  - settle    │
                        └──────┬───────┘
                               │
                    ┌──────────▼──────────┐
                    │  Settlement Contract │
                    │  (SKALE Europa)      │
                    │                     │
                    │  - split funds      │
                    │  - emit receipt hash│
                    │  - dispute escrow   │
                    └─────────────────────┘
```
