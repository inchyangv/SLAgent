# Architecture — SLAgent-402

## Agent Roles & Trust Boundaries

SLAgent-402 has three distinct agent roles. Each role has clear responsibilities and signing authority.

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
│  Settlement Contract (SKALE Base Sepolia (BITE v2 Sandbox 2))                             │
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

## Track Add-ons (Implemented)

- **x402 Agentic Tool Chain**: 2+ paid tool calls per workflow (402 → pay → retry), CDP Wallet signing/custody, budget-aware tool choice with spend logs.
- **AP2 Pattern**: explicit intent → authorization → settlement → receipt over A2A/AP2 envelopes with audit-ready records and failure modes.
- **BITE v2 Conditional Settlement**: encrypted conditions/pricing/policy, decrypted only when SLA passes; failure path keeps data sealed.

---

## Chain & Token Strategy (MVP)

### Network: SKALE Base Sepolia (BITE v2 Sandbox 2)

- **Chain ID:** `103698795`
- **RPC:** `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- **Explorer:** `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- **Note:** 이 체인 배포를 위해 `evm_version = "istanbul"`을 사용합니다.

### Token: USDC (SKALE Base Sepolia (BITE v2 Sandbox 2))

SKALE Base Sepolia (BITE v2 Sandbox 2)에서 USDC를 결제/정산 토큰으로 사용한다.

- **Name/Symbol:** USDC / USDC
- **Decimals:** 6
- **Address:** `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- **Rationale:** “실제 토큰”을 써서 x402/정산 데모의 현실성을 올린다.

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

1. Buyer(또는 facilitator)가 `deposit(requestId, buyer, max_price)`로 escrow에 예치한다.
2. Gateway는 mandate rules + 측정 metrics로 `payout`을 결정적으로 계산한다.
3. Gateway가 signed receipt로 `settle()`을 호출해 “이번 요청의 정산 조건”을 고정한다.
4. dispute window가 지나면 `finalize()`로 payout/refund가 분배된다(또는 dispute가 열리면 resolver가 `resolveDispute()`).
5. Receipt hash가 `Settled` 이벤트로 온체인에 남는다.

노트:
- HTTP 레벨의 x402(402→paid)은 “결제 증명/게이팅” 용도이고, 실제 자금 이동(escrow)은 `deposit()`으로 연결되어야 한다.
- 현재 gateway가 `deposit → settle`을 자동으로 엮는 작업은 티켓으로 남겨두었다(`TICKET.md`의 `T-123`).

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
                    │ (SKALE Base Sepolia (BITE v2 Sandbox 2))       │
                    │                     │
                    │  - split funds      │
                    │  - emit receipt hash│
                    │  - dispute escrow   │
                    └─────────────────────┘
```
