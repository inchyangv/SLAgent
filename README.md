# SLAgent-402

**Don't pay upfront. Pay by proof.**

SLAgent-402 is a pay-by-performance settlement layer for agent-to-agent API calls.
It measures QoS + deterministic validity, generates signed Performance Receipts,
and settles payment on-chain with automatic split + refund.

## Architecture

```
Buyer Agent ──► SLAgent-402 Gateway ──► Seller Service
                    │
                    ├── Measures TTFT / latency
                    ├── Runs deterministic validators (JSON schema)
                    ├── Computes pricing + receipt
                    └── Submits on-chain settlement
                            │
Dashboard (static) ◄─────────┘
Settlement Contract (SKALE Base Sepolia / BITE v2 Sandbox 2)
```

## Quickstart

Prerequisites:
- Python 3.11+
- Foundry (optional for contracts/tests)

Install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create `.env`:
```bash
cp .env.example .env
```

Optional local-only demo overrides (no chain, deterministic seller):
```bash
PAYMENT_MODE=hmac
SELLER_FALLBACK=true
```

Run the one-command demo (starts seller + gateway + buyer agent):
```bash
python scripts/demo_one_command.py
```

If you want signing/attestations, set `DEMO_PRIVATE_KEY` or `DEMO_MNEMONIC` in `.env`
or inline when you run the demo:
```bash
DEMO_PRIVATE_KEY=0x... python scripts/demo_one_command.py
```

Open the demo console:
```text
http://localhost:8000/dashboard/console.html
```

For full x402 + on-chain settlement, set `PAYMENT_MODE=x402` and role keys in `.env`.
See `LOCAL.md` and `DEMO.md` for the full checklist.

## Manual Run

Start seller (set `SELLER_FALLBACK=true` if you do not have a Gemini key):
```bash
uvicorn seller.main:app --port 8001
```

Start gateway:
```bash
uvicorn gateway.app.main:app --port 8000
```

Run the autonomous buyer agent:
```bash
python -m buyer_agent.main
```

Or run the scripted end-to-end scenarios:
```bash
python scripts/run_demo.py
```

## Project Structure

```
contracts/         Solidity settlement + dispute contracts (Foundry)
gateway/           FastAPI reverse proxy, validators, pricing, receipts
gateway/demo_seller/  Minimal deterministic seller stub
seller/            Gemini-backed seller service (fast/slow/invalid)
buyer_agent/       Autonomous buyer CLI (negotiation + 402 + receipt checks)
facilitator/       Settlement transaction coordinator
shared/            Shared env loader and utilities
dashboard/         Static demo console (console.html)
scripts/           Demo orchestration and utilities
docs/              Architecture, API, security, demo documentation
data/              Local SQLite receipts (optional)
```

## Documentation

- [Demo Guide](DEMO.md)
- [Local Setup](LOCAL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Schemas](docs/API.md)
- [Security Notes](docs/SECURITY.md)
- [Submission](docs/SUBMISSION.md)

## Security Assumptions (MVP)

- **Gateway is trusted** as the single attestation authority (future: multi-party signing)
- **Resolver is centralized** (future: decentralized arbitration)
- **Payment verification is off-chain** (HMAC or x402 headers); settlement is on-chain
- **Storage is best-effort** — receipts are in-memory unless `RECEIPT_DB_PATH` is set
- **LLM policy is advisory** and constrained by deterministic guardrails

## License

MIT
