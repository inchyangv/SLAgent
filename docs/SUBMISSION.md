# Submission — SLAgent-402

## What is SLAgent-402?

**Pay by proof, not upfront.**

SLAgent-402 is a pay-by-performance settlement layer for agent-to-agent API calls.
Instead of fixed pricing, buyers pay `max_price` upfront and receive automatic refunds
based on measured QoS (latency, validity) — settled on-chain with cryptographic receipts.

## Key Innovation

- **Performance-based pricing:** Sellers earn more for faster, valid responses
- **Deterministic validation:** JSON schema checks, not subjective LLM scoring
- **On-chain receipts:** Every settlement emits a verifiable receipt hash
- **Bonded disputes:** Challenge results with skin-in-the-game (bond slashing)
- **x402 compatible:** Standard HTTP payment gating for agent commerce

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Settlement Contract | Solidity 0.8.24, Foundry |
| Gateway | Python, FastAPI |
| Pricing Engine | Integer arithmetic, latency tiers |
| Validation | JSON Schema (deterministic) |
| Chain | SKALE Base Sepolia (BITE v2 Sandbox 2) (Chain ID 103698795) |
| Token | USDC (6 decimals) |
| Dashboard | Static HTML + vanilla JS |

## Repository Overview

```
contracts/        Solidity settlement + dispute (Foundry)
  src/SLASettlement.sol    Main contract: escrow, split, dispute
  src/SLAToken.sol         (Optional) mock ERC20 for local-only testing
  test/                    18 Foundry tests

gateway/          FastAPI reverse proxy
  app/main.py              Endpoints: /v1/call, receipts, disputes
  app/pricing.py           Latency tier pricing engine
  app/validators/          JSON schema validator
  app/x402.py              402 Payment Required flow
  app/settlement_client.py Chain settlement bridge
  demo_seller/             Demo seller with fast/slow/invalid modes
  tests/                   42+ pytest tests

facilitator/      Settlement transaction coordinator
dashboard/        Static receipt ledger + metrics UI
scripts/          Demo script + dispute resolver CLI
docs/             Architecture, API, Security, Demo
```

## How to Run the Demo

### Prerequisites
- Python 3.11+
- Foundry (for contract tests)

### Quick Start (< 5 minutes)

```bash
# 1. Install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Run contract tests
cd contracts && forge test -v && cd ..

# 3. Run Python tests
pytest gateway/tests/ facilitator/tests/ -v

# 4. Start demo seller
uvicorn gateway.demo_seller.main:app --port 8001 &

# 5. Start gateway
uvicorn gateway.app.main:app --port 8000 &

# 6. Run end-to-end demo
python scripts/run_demo.py

# 7. Open dashboard
open dashboard/index.html
```

### What You'll See

Three scenarios demonstrating pay-by-performance:

1. **Fast + Valid** → Full payout ($0.10) — latency under 2s
2. **Slow + Valid** → Base pay ($0.06) — latency over 5s
3. **Invalid Output** → Zero payout, full refund ($0.10) — schema validation fails

## Hackathon Track Relevance

### SKALE Base Sepolia (BITE v2 Sandbox 2)
- Reproduces the full on-chain settlement flow on SKALE testnet
- Low gas overhead makes per-request settlement demos practical
- Escrow + delayed finalization improves dispute safety

### Coinbase x402
- x402-compatible payment gating (402 → paid request flow)
- `exact(max_price)` + refund pattern for "pay up to" behavior
- Standard HTTP headers for agent-to-agent commerce

### Agent Commerce (A2A/AP2)
- SLA mandates as structured contracts between buyer and seller agents
- Performance receipts as verifiable proofs of service delivery
- Deterministic validators for objective quality assessment

## Track Add-ons (Implemented)

- **Agentic Tool Usage on x402**: 2+ paid tool calls per workflow (402 → pay → retry each), CDP Wallet signing/custody, budget-aware tool choice with spend logs.
- **Best Integration of AP2**: explicit intent → authorization → settlement → receipt pattern over A2A/AP2 envelopes, including an authorization failure mode demo.
- **Encrypted Agents (BITE v2)**: encrypted conditions/pricing/policy, decrypted and settled only on success; failure path keeps data sealed.

## Contract Addresses

SKALE BITE v2 Sandbox 2 deployment:
- `SLASettlement`: `0xd5FBcF82364865E2477Aae988A3C3232Fae77756`
- `USDC`: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- Deploy tx: `0xaba602d851e3cd18f43bc765a80f266322b0f856e052a0c4b9b1fccc864607bf`

## Screenshots

[Dashboard showing receipt ledger with three demo scenarios]
[Terminal output from run_demo.py showing payout/refund per scenario]

## Team

Built during the hackathon — agent-to-agent commerce, settled by proof.
