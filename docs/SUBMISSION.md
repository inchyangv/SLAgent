# Submission — SLAgent-402

## What It Is

SLAgent-402 is a pay-by-performance trust layer for agent-to-agent services.
The buyer agent uses a WDK wallet sidecar to deposit Sepolia mock USDT into escrow
before execution, and the gateway settles payout/refund only after measured SLA outcomes.

## Key Innovation

- **Deposit-first settlement:** payment proof is an on-chain escrow deposit, not an HTTP challenge
- **WDK-native wallet flow:** buyer and gateway can use the sidecar for wallet actions and signatures
- **Deterministic adjudication:** schema validation and integer pricing rules stay reproducible
- **Receipt-backed settlement:** every call returns receipt hashes plus deposit/settlement tx hashes
- **Budgeted tool usage:** the buyer can run 2+ paid tool calls with per-step spend tracking

## Stack

| Component | Technology |
|-----------|------------|
| Settlement contract | Solidity 0.8.24, Foundry |
| Wallet layer | WDK + WDK EVM wallet + local Node.js sidecar |
| Gateway | Python, FastAPI |
| Seller | Python, Gemini/fallback execution |
| Chain | Ethereum Sepolia |
| Token | Mock USDT (6 decimals) |
| Dashboard | Static HTML + vanilla JS |

## Repository Overview

```text
contracts/        SLASettlement + mock USDT
gateway/          deposit verification, pricing, receipts, disputes
seller/           seller execution service
buyer_agent/      buyer CLI + deposit-first tool chain
wdk-service/      local WDK bridge for wallet actions
dashboard/        demo console
scripts/          orchestration and demos
docs/             architecture, API, security notes
```

## Demo Path

1. Load WDK wallet from mnemonic or seed phrase.
2. Approve and deposit `max_price` into escrow.
3. Call gateway with `request_id` and `deposit_tx_hash`.
4. Gateway verifies deposit on-chain.
5. Gateway forwards work, validates output, computes payout/refund.
6. Gateway submits `settle()` and returns receipt + tx hashes.

## What Judges See

- WDK wallet creation/import and balance visibility
- Buyer-funded USDT escrow deposit
- Three SLA scenarios with different payouts
- On-chain deposit verification and settlement evidence
- Receipt hashes and dispute-ready settlement lifecycle

## Track Relevance

### Autonomous DeFi Agent

- The buyer agent controls a real wallet flow through WDK.
- Capital is committed before work through escrow deposit.
- Spending decisions and tool chaining are autonomous and budget-aware.
- Settlement is on-chain and conditioned on delivered quality.

### Optional Protocol Surface

- A2A/AP2 envelope endpoints remain available for protocol-facing demos.
- Gemini negotiation/policy traces show the system can mix LLM guidance with deterministic settlement.

## How To Run

```bash
cp .env.example .env
cd wdk-service && npm install && cd ..
source .venv/bin/activate
python scripts/demo_one_command.py
```

Optional:

```bash
python scripts/run_deposit_chain_demo.py
```

## Addresses

Deployment addresses are environment-driven:

- `PAYMENT_TOKEN_ADDRESS`
- `SETTLEMENT_CONTRACT_ADDRESS`

This keeps the repo reusable across repeated Sepolia deployments during the hackathon.
