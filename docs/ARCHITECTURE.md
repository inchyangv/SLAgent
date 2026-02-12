# Architecture — SLA-Pay v2

## Chain & Token Strategy (MVP)

### Network: SKALE Europa Hub

- **Chain ID:** 2046399126
- **RPC:** `https://mainnet.skalenodes.com/v1/elated-tan-skat`
- **Explorer:** `https://elated-tan-skat.explorer.mainnet.skalenodes.com`
- **Key property:** Zero gas fees — ideal for high-frequency micro-settlements

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
