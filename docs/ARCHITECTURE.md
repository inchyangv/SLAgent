# Architecture — SLAgent-402

## Roles

### Buyer Agent

- Discovers seller capabilities
- Negotiates mandate terms
- Uses WDK sidecar to approve and deposit `max_price`
- Calls gateway with `request_id` and `deposit_tx_hash`
- Verifies receipt invariants fail-closed

### Seller Service

- Accepts mandates
- Produces work output
- Returns schema-compliant JSON

### Gateway

- Verifies buyer deposit on-chain
- Measures TTFT and total latency
- Runs deterministic validators
- Computes payout/refund
- Builds receipt hash
- Signs settlement authorization
- Submits `settle()` and dispute transactions

### Settlement Contract

- Holds buyer deposit in escrow
- Stores settlement state per `requestId`
- Pays seller and refunds buyer after settlement/finalization
- Supports bonded disputes

## Deposit-First Sequence

```text
Buyer Agent            WDK Sidecar           Gateway              Seller              SLASettlement
    │                       │                  │                    │                       │
    │ wallet/import         │                  │                    │                       │
    │──────────────────────►│                  │                    │                       │
    │ approve + deposit     │                  │                    │                       │
    │──────────────────────►│──────────────────────────────────────────────────────────────►│
    │                       │                  │                    │                       │
    │ POST /v1/call + deposit_tx_hash          │                    │                       │
    │─────────────────────────────────────────►│                    │                       │
    │                       │                  │ verify deposit tx   │                       │
    │                       │                  │ forward request ───►│                       │
    │                       │                  │◄──── seller output  │                       │
    │                       │                  │ validate + price    │                       │
    │                       │                  │ settle() ──────────────────────────────────►│
    │◄─────────────────────────────────────────│ receipt + tx hashes │                       │
```

## Trust Boundary

```text
Local operator boundary:
  buyer_agent/ + gateway/ + wdk-service/

Deterministic core:
  validation, pricing, receipt hashing

On-chain source of truth:
  deposit tx, settle tx, settlement state
```

## WDK Sidecar

`wdk-service/` exists because the current Python services do not talk to the WDK SDK directly.

Endpoints:

```text
POST /wallet/create
POST /wallet/import
GET  /wallet/:address/balance
POST /wallet/approve
POST /wallet/deposit
POST /wallet/sign-message
POST /wallet/sign-bytes
GET  /health
```

Buyer and gateway both reuse the same sidecar pattern with role-specific account indexes.

## Chain / Token

- **Chain:** Ethereum Sepolia
- **Chain ID:** `11155111`
- **Token:** Mock USDT
- **Decimals:** `6`

All pricing values use the smallest token unit.

Examples:

| Human | Raw |
|------|-----|
| 0.10 USDT | `100000` |
| 0.08 USDT | `80000` |
| 0.06 USDT | `60000` |

## Optional Surfaces

- `gateway/app/a2a/` keeps the A2A/AP2 envelope flow available for protocol demos.
- Gemini negotiation and SLA policy layers remain optional overlays, not the settlement source of truth.
