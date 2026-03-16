# SLAgent-402

**Don't pay upfront. Pay by proof.**

SLAgent-402 is a pay-by-performance settlement layer for agent-to-agent API calls.
A buyer agent uses a local WDK sidecar to hold Sepolia mock USDT, deposit `max_price`
into escrow, call a seller through the gateway, and receive automatic payout/refund
settlement from measured SLA results.

## Core Flow

1. Buyer loads a WDK wallet through `wdk-service/`.
2. Buyer approves and deposits mock USDT into `SLASettlement`.
3. Buyer calls `POST /v1/call` with `request_id` and `deposit_tx_hash`.
4. Gateway verifies the deposit on-chain, forwards work to seller, measures latency,
   validates output, and computes payout/refund.
5. Gateway signs settlement authorization, submits `settle()`, and stores a receipt.
6. Dashboard shows balances, receipt hashes, and settlement transactions.

## Architecture

```text
Buyer Agent ──► WDK Sidecar ──► Sepolia USDT + SLASettlement
     │                               ▲
     └──────────────► Gateway ───────┘
                        │
                        ├── seller call
                        ├── metrics + schema validation
                        ├── pricing + receipt hash
                        └── settle() submission
```

Default chain:
- Ethereum Sepolia (`11155111`)
- Mock USDT (`Tether USD`, `USDT`, `6 decimals`)

## Quickstart

Prerequisites:
- Python 3.11+
- Node.js 20+
- Foundry optional for contract tests

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd wdk-service && npm install && cd ..
cp .env.example .env
```

Minimal local demo:

```bash
SELLER_FALLBACK=true \
DEMO_MNEMONIC="test test test test test test test test test test test junk" \
python scripts/demo_one_command.py
```

Open:

```text
http://localhost:8000/dashboard/console.html
```

## Manual Run

Start the WDK sidecar:

```bash
cd wdk-service
node src/server.mjs
```

Start seller:

```bash
uvicorn seller.main:app --port 8001
```

Start gateway:

```bash
uvicorn gateway.app.main:app --port 8000
```

Run the buyer:

```bash
python -m buyer_agent.main
```

Run the multi-step tool demo:

```bash
python scripts/run_deposit_chain_demo.py
```

## Project Structure

```text
contracts/          settlement contract + mock USDT
gateway/            FastAPI gateway, validators, receipts, settlement bridge
seller/             seller service with Gemini/fallback execution
buyer_agent/        autonomous buyer + deposit-first tool chain
wdk-service/        local Node.js sidecar for WDK wallet actions
dashboard/          static demo console
scripts/            orchestration and demo utilities
docs/               submission, architecture, API, security notes
```

## Demo Notes

- `scripts/demo_one_command.py` starts `wdk-service`, seller, gateway, then runs the buyer.
- `scripts/run_demo.py` runs the three core scenarios: fast, slow, invalid.
- `scripts/run_deposit_chain_demo.py` shows 2+ paid tool calls with deterministic budget tracking.

## Security Assumptions

- Gateway is still the trusted measurement and settlement coordinator in the MVP.
- Resolver is centralized.
- WDK sidecar is expected to run locally and share the same operator trust boundary as the Python services.
- Receipt storage is best-effort unless `RECEIPT_DB_PATH` is configured.

## Optional Extensions

- A2A/AP2 envelope endpoints remain available under `gateway/app/a2a/`.
- Gemini negotiation/policy layers are optional and fail open to deterministic logic.

## License

MIT
