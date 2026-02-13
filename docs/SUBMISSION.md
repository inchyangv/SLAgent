# Submission — SLA-Pay v2

## What is SLA-Pay v2?

**Pay by proof, not upfront.**

SLA-Pay v2 is a pay-by-performance settlement layer for agent-to-agent API calls.
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
| Chain | SKALE Hackathon: BITE v2 Sandbox 2 (Chain ID 103698795) |
| Token | Predeployed USDC (6 decimals) |
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

### SKALE
- Zero gas fees enable per-request micro-settlements
- Settlement contract designed for high-frequency on-chain operations
- Escrow + delayed finalization for dispute safety

### Coinbase x402
- x402-compatible payment gating (402 → paid request flow)
- `exact(max_price)` + refund pattern for "pay up to" behavior
- Standard HTTP headers for agent-to-agent commerce

### Agent Commerce (A2A/AP2)
- SLA mandates as structured contracts between buyer and seller agents
- Performance receipts as verifiable proofs of service delivery
- Deterministic validators for objective quality assessment

## Contract Addresses

MVP uses local/mock deployment. For live deployment:
- Set `CHAIN_RPC_URL`, `SETTLEMENT_CONTRACT_ADDRESS`, `PAYMENT_TOKEN_ADDRESS` in `.env`
- Deploy contracts via `forge script`

## Screenshots

[Dashboard showing receipt ledger with three demo scenarios]
[Terminal output from run_demo.py showing payout/refund per scenario]

## Team

Built during the hackathon — agent-to-agent commerce, settled by proof.
