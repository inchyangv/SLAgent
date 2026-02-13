# DoraHacks Details — SLAgent-402

## Summary

**SLAgent-402** is a pay-by-performance trust layer for agent-to-agent commerce.
It combines x402 payment gating, Gemini-based SLA judgement/negotiation, and SKALE on-chain settlement so buyers pay for delivered quality, not promises.

Tagline: **Don't pay upfront. Pay by proof.**

## Why This Problem Matters

In autonomous AI commerce, failures are expensive:
- A buyer can be charged full price even when output is late, invalid, or low quality.
- Static API billing does not reflect probabilistic model performance.
- Without real-time adjudication, agent-to-agent payments are not economically safe.

SLAgent-402 closes that gap with measurable, auditable, programmable settlement.

## What We Built

- **Seller Service (Gemini)**
  - Produces realistic `invoice_v1` responses with explicit LLM evidence headers.
- **SLA Gateway (x402 + Gemini policy)**
  - Enforces `402 -> paid request` flow.
  - Measures latency and schema validity.
  - Uses Gemini as SLA judge and negotiation engine.
  - Applies guardrails and computes payout/refund.
  - Persists receipts/events and submits SKALE settlement txs.
- **Settlement Contract**
  - `deposit()` escrow + `settle()` payout/refund split + dispute lifecycle.
- **Dashboard (FE-first demo)**
  - Preset-based autopilot, negotiation history, receipts, timeline, and live balances.

## Gemini Role (Critical)

Gemini is not decorative. It is part of the economic control loop:
- **SLA judgement**: decides pass/degraded/breach tendency and recommends payout.
- **SLA negotiation**: proposes/counters mandate pricing terms before execution.
- **Scenario-sensitive behavior**: different negotiation and payout posture for `Happy Path`, `Slow SLA`, `Breaches`.

Result: the system demonstrates adaptive settlement logic aligned with runtime service quality.

## Live Demo Flow

`Buyer (dashboard autopilot) -> Gateway -> Seller (Gemini) -> Receipt/Event ledger -> SKALE deposit + settle`

What judges see:
1. x402-style payment gating (`402` challenge and paid request path).
2. Buyer-funded escrow deposit on SKALE.
3. Gemini-in-the-loop SLA judgement and negotiation traces.
4. Scenario-based payout/refund changes in real time.
5. On-chain proof via `deposit_tx_hash` and `settle_tx_hash`.

## Network / Token (Hackathon)

SKALE Hackathon chain: **BITE v2 Sandbox 2**
- Chain ID: `103698795`
- RPC: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Explorer: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- Gas token: `sFUEL`

Payment token: predeployed **USDC (6 decimals)**
- USDC: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- x402/EIP-712 domain: `name=USDC`, `version=""`

Note:
- Endpoint includes `base-sepolia` in hostname, but this is SKALE infrastructure (not Ethereum Base Sepolia).

## Wallet Roles / Real Money Path

- `BUYER`: submits deposit and pays max budget
- `SELLER`: receives payout when SLA is met
- `GATEWAY`: submits settlement/dispute transactions

Economic path:
- Buyer locks `max_price` -> Gateway computes SLA result -> Seller gets payout -> Buyer receives refund (`max_price - payout`).

## How To Run

1) Configure `.env`
```bash
cp .env.example .env
```
Set at minimum:
- `PAYMENT_MODE=x402`
- `GEMINI_API_KEY`
- `LLM_POLICY_ENABLED=true`
- `LLM_NEGOTIATION_ENABLED=true`
- `BUYER_PRIVATE_KEY`, `SELLER_PRIVATE_KEY`, `GATEWAY_PRIVATE_KEY`
- `SETTLEMENT_CONTRACT_ADDRESS`

2) Deploy settlement contract (Foundry)
```bash
set -a; source .env; set +a
cd contracts
forge script script/DeploySlaPayV2.s.sol:DeploySlaPayV2 --rpc-url "$RPC_URL" --broadcast -vvvv
```

3) Approve buyer USDC to settlement
```bash
set -a; source .env; set +a
cast send --rpc-url "$CHAIN_RPC_URL" --private-key "$BUYER_PRIVATE_KEY" \
  "$PAYMENT_TOKEN_ADDRESS" "approve(address,uint256)" "$SETTLEMENT_CONTRACT_ADDRESS" \
  "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
```

4) Run services and open dashboard
```bash
source .venv/bin/activate
uvicorn seller.main:app --port 8001
uvicorn gateway.app.main:app --port 8000
```
- `http://localhost:8000/dashboard/console.html`

## Track Fit

- **SKALE**: low-cost per-request settlement and auditable dispute lifecycle
- **x402**: standard payment challenge/paid request interface
- **Agentic Commerce**: machine-to-machine mandate, monitoring, and settlement
- **AI-native trust**: Gemini-driven adjudication + negotiation in the critical path

## Track Add-ons (Implemented)

- **Agentic Tool Usage on x402**: 2+ paid tool calls per workflow (402 → pay → retry each), CDP Wallet signing/custody, budget-aware tool choice with spend logs.
- **Best Integration of AP2**: explicit intent → authorization → settlement → receipt pattern over A2A/AP2 envelopes, including an authorization failure mode demo.
- **Encrypted Agents (BITE v2)**: encrypted conditions/pricing/policy, decrypted and settled only on success; failure path keeps data sealed.

## Current Limitation

- LLM policy is fail-open by design: if Gemini is unavailable or malformed, gateway falls back to deterministic rule logic.
