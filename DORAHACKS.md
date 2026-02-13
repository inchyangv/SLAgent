# DoraHacks Details — SLAgent-402

## Summary

**SLAgent-402** is a pay-by-performance settlement layer for agent-to-agent API calls.
The buyer pays up to `max_price` and automatically gets a refund based on measured SLA (latency + deterministic validity), settled on-chain on **SKALE (BITE v2 Sandbox 2)**.

Tagline: **Don't pay upfront. Pay by proof.**

---

## What We Built

- **Seller Service (Gemini)**: calls Google Gemini to generate a realistic `invoice_v1` JSON response.
- **Gateway (deterministic)**: measures latency, validates output with JSON Schema, computes payout/refund, stores receipts + event timeline, and submits on-chain settlement.
- **Settlement Contract**: escrow `deposit()` + split/refund `settle()` (with dispute lifecycle available).
- **Dashboard**: one-page console to run scenarios and view receipts/events/tx hashes.

LLM evidence:
- Seller responses include `X-LLM-Provider`, `X-LLM-Model`, `X-LLM-Used`, `X-LLM-Mode`.

---

## Demo Flow

`Buyer (dashboard/runner) -> Gateway -> Seller (Gemini) -> Receipt/Event ledger -> SKALE deposit + settle`

What judges can see live:
1. Call without payment -> `402 Payment Required` (x402-style challenge)
2. Retry with payment header -> request executed
3. Seller generates invoice via Gemini (real LLM call)
4. Gateway enforces SLA deterministically:
   - latency tiers (payout changes with speed)
   - schema validity (invalid output -> payout 0)
5. Gateway returns `receipt_hash`, `breach_reasons`, and SKALE tx hashes:
   - `deposit_tx_hash`
   - `settle_tx_hash`

SLA simulation (demo-friendly):
- Seller supports `fast`, `slow`, `invalid`, `error`, `timeout` and `delay_ms`.

---

## Network / Token (Hackathon)

SKALE Hackathon chain: **BITE v2 Sandbox 2**
- Chain ID: `103698795`
- RPC: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Explorer: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- Gas token: `sFUEL`
- Reference: `https://docs.skale.space/get-started/hackathon/info#bite-v2-sandbox-2`

Payment/settlement token: predeployed **USDC (6 decimals)**
- USDC: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- x402/EIP-712 domain: `name=USDC`, `version=""` (empty string)

Faucet/support:
- SKALE Builders Telegram: `https://t.me/+dDdvu5T6BOEzZDEx` (ask `@TheGreatAxios` for `sFUEL`/`USDC`)

---

## How To Run (Local + SKALE)

This repo uses a single root `.env` for Gateway/Seller/scripts (Python services auto-load it).

1) Configure env
```bash
cp .env.example .env
```
Fill at least:
- `GEMINI_API_KEY`
- `PRIVATE_KEY` (contract deploy)
- `GATEWAY_PRIVATE_KEY` (on-chain signer)
- `SETTLEMENT_CONTRACT_ADDRESS` (after deploy)

2) Deploy contracts (Foundry)
```bash
set -a; source .env; set +a
cd contracts
forge script script/DeploySlaPayV2.s.sol:DeploySlaPayV2 --rpc-url "$RPC_URL" --broadcast -vvvv
```

3) Run services
```bash
source .venv/bin/activate
uvicorn seller.main:app --port 8001
uvicorn gateway.app.main:app --port 8000
```

4) Open dashboard
- `http://localhost:8000/dashboard/console.html`

---

## Track Fit

- **SKALE**: per-request on-chain settlement (escrow + split + refund)
- **x402**: `402 -> paid request` payment gating (optional EIP-712 verification mode exists)
- **Agentic Commerce**: mandate-like SLA terms + receipts as proofs + programmable settlement
- **AI**: Gemini-powered seller with explicit evidence headers

---

## Current Limitation

- For demo simplicity, the current `deposit()` payer is the **Gateway EOA**, so `GATEWAY_PRIVATE_KEY` must hold USDC + sFUEL.

