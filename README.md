# SLAgent-402

**Don't pay upfront. Pay by proof.**

SLAgent-402 is a pay-by-performance settlement layer for agent-to-agent API calls.
It measures QoS + deterministic validity, generates signed Performance Receipts,
and settles payment on-chain with automatic split + refund.

## Architecture

```
Buyer Agent ──► SLAgent-402 Gateway ──► Seller Agent
                    │
                    ├── Measures TTFT / latency
                    ├── Runs validators (JSON schema)
                    ├── Generates Performance Receipt
                    └── Submits on-chain settlement
                            │
                    Settlement Contract (SKALE Base Sepolia (BITE v2 Sandbox 2))
                    ├── Pays seller (payout)
                    ├── Refunds buyer (max_price - payout)
                    └── Emits receipt hash
```

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Foundry (for Solidity contracts)

### Gateway (Python / FastAPI)

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest gateway/tests/ -v

# Start gateway
uvicorn gateway.app.main:app --port 8000
```

### Contracts (Solidity / Foundry)

```bash
cd contracts
forge build
forge test -v
```

### Dashboard

Open `dashboard/index.html` in your browser (static page, no build needed).

### End-to-End Demo

```bash
# Start seller + gateway
uvicorn gateway.demo_seller.main:app --port 8001 &
uvicorn gateway.app.main:app --port 8000 &

# Run three demo scenarios
python scripts/run_demo.py
```

## Project Structure

```
contracts/       Solidity settlement + dispute contracts (Foundry)
gateway/         FastAPI reverse proxy, validators, pricing, receipts
facilitator/     Settlement transaction coordinator
dashboard/       Web UI for receipt/metrics visualization
docs/            Architecture, API, security, demo documentation
scripts/         Demo and utility scripts
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Schemas](docs/API.md)
- [Security](docs/SECURITY.md)
- [Demo Guide](docs/DEMO.md)
- [Submission](docs/SUBMISSION.md)

## Security Assumptions (MVP)

- **Gateway is trusted** as the single attestation authority (future: multi-party signing)
- **Resolver is centralized** (future: decentralized arbitration)
- **Payments use HMAC** instead of real x402 on-chain proofs (future: real x402)
- **In-memory storage** — restart loses state (future: persistent DB)
- See [Security Notes](docs/SECURITY.md) for full threat model

## License

MIT
