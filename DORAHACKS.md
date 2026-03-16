# DoraHacks Details — SLAgent-402

## Summary

SLAgent-402 lets autonomous agents trade with performance-backed payment terms.
The buyer agent uses a local WDK wallet sidecar, deposits Sepolia mock USDT into
escrow before execution, and pays only according to measured SLA outcomes.

Tagline: **Pay by proof, not upfront.**

## What We Built

- **WDK wallet sidecar**
  - Local wallet create/import/balance/approve/deposit/sign endpoints
  - Used by the buyer agent and gateway signing path
- **Deposit-first gateway**
  - Verifies `deposit_tx_hash` on-chain before forwarding work
  - Measures latency and schema validity
  - Computes payout/refund deterministically
- **Settlement contract**
  - `deposit()`, `settle()`, `openDispute()`, `resolveDispute()`, `finalize()`
- **Buyer agent**
  - Negotiates mandate terms
  - Submits deposit automatically
  - Verifies receipt invariants fail-closed
- **Dashboard**
  - Live balances, receipts, timeline, negotiation history, dispute controls

## Why It Fits Autonomous DeFi Agent

- Real asset handling through WDK
- Escrowed deposit before execution
- Autonomous budgeted spending by the buyer agent
- On-chain payout/refund settlement after measurable work
- Clear path from single call to repeated agentic tool usage

## Demo Flow

```text
Buyer Agent -> WDK Sidecar -> deposit(max_price)
Buyer Agent -> Gateway (/v1/call + deposit_tx_hash)
Gateway -> Seller
Gateway -> SLASettlement.settle()
Dashboard -> receipt + deposit tx + settle tx
```

Judges see:
1. WDK wallet loading and balance visibility
2. Buyer-funded USDT deposit into escrow
3. Fast / slow / invalid scenarios with different payouts
4. On-chain verification of deposit and settlement hashes
5. Deterministic receipts and optional disputes

## Network / Token

- **Chain:** Ethereum Sepolia (`11155111`)
- **Token:** Mock USDT (`Tether USD`, `USDT`, `6 decimals`)
- **Wallet stack:** `@tetherto/wdk` + `@tetherto/wdk-wallet-evm`

Addresses are environment-driven because demo deployments can be redeployed quickly.
See `.env.example` for `PAYMENT_TOKEN_ADDRESS` and `SETTLEMENT_CONTRACT_ADDRESS`.

## How To Run

```bash
cp .env.example .env
cd wdk-service && npm install && cd ..
source .venv/bin/activate
python scripts/demo_one_command.py
```

For a deterministic local demo:

```bash
SELLER_FALLBACK=true \
DEMO_MNEMONIC="test test test test test test test test test test test junk" \
python scripts/demo_one_command.py
```

## Technical Highlights

- Deposit verification checks the actual Sepolia transaction input and `Deposited` event.
- Gateway can source settlement authorization signatures from the WDK sidecar.
- Buyer tool-chain demo supports 2+ paid tool calls with budget tracking and per-step deposit records.
- Gemini remains useful for negotiation and SLA judgement, but deterministic pricing is still the hard guardrail.

## Current MVP Limits

- Gateway is still trusted for measurement and receipt issuance.
- Resolver is centralized.
- Mock USDT is used for repeatable testnet demos rather than production liquidity.
