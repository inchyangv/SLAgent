# SLAgent — DoraHacks Submission

> **Pay by proof, not upfront.**

## One-Liner

Autonomous AI agents trade services using WDK wallets, with on-chain escrow that settles payment based on measured SLA performance — not trust.

---

## Problem

AI agents buying services from other agents today face a broken payment model:

- Fast or slow response → same price
- Valid or malformed output → same price
- Success or failure → same price

When agents autonomously make thousands of calls, this misalignment compounds. There is no verifiable proof of what was promised, what was delivered, or how payment was computed.

## Solution

SLAgent puts WDK wallets in the hands of autonomous agents and introduces an **SLA-driven settlement layer**:

1. **Buyer locks `max_price`** into on-chain escrow via WDK wallet
2. **Gateway measures performance** — latency, schema validity, success/failure
3. **Deterministic payout split** — Seller gets paid proportional to SLA compliance, Buyer gets automatic refund for the rest
4. **Everything on-chain** — receipt hash, settlement tx, dispute state

---

## What We Built

### WDK Wallet Sidecar (Node.js)
- `@tetherto/wdk` + `@tetherto/wdk-wallet-evm` integration
- Endpoints: create, approve, deposit, sign, transfer, balance
- Production hardening: nonce manager, retry with circuit breaker, Bearer auth, RPC fallback, structured logging, graceful shutdown
- Atomic `approve-and-deposit` with retry

### Autonomous Buyer Agent (Python)
- Discovers seller capabilities, negotiates SLA terms (with Gemini LLM)
- Automatically calls WDK sidecar for `approve → deposit → call`
- Verifies receipts fail-closed, tracks per-call budget
- Multi-step agentic tool chains (2+ paid calls per workflow)
- Opens disputes when breach is detected

### SLA Gateway (FastAPI)
- Reverse proxy with x402 payment gating
- Measures TTFT and total latency precisely
- Runs deterministic validators (JSON Schema)
- Computes payout from latency tiers — no LLM scoring
- Signs performance receipts, submits settlement on-chain
- Event ledger: full timeline from negotiation to settlement

### Settlement Contract (Solidity / Foundry)
- `deposit()` → `settle()` → `finalize()`
- `openDispute()` → `resolveDispute()` with bond slashing
- Escrow-based: payout delayed until dispute window closes
- Receipt hash emitted on-chain for auditability

### Gemini Seller Service
- LLM-powered API service (Gemini 2.0 Flash)
- Controllable demo modes: fast / slow / invalid / error / timeout
- Simulation controls: `delay_ms` slider, `force_error` toggle

### Dashboard (React + Vite)
- Live balance panel with network status indicator
- Receipts table with detail modal and breach reason pills
- Event timeline: negotiation → payment → execution → validation → settlement
- SLA simulator: latency slider + failure toggles for live demos
- History page: full lifecycle replay per request
- Negotiation history with chat bubble UI
- Dispute panel with step-by-step workflow
- SLA offer catalog: Bronze / Silver / Gold presets

---

## Payout Model

| SLA Result | Payout | Refund |
|------------|--------|--------|
| Success + latency ≤ 2s | 100,000 µUSDT (full) | 0 |
| Success + 2s < latency ≤ 5s | 80,000 µUSDT | 20,000 µUSDT |
| Success + latency > 5s | 60,000 µUSDT (base only) | 40,000 µUSDT |
| Failure or schema invalid | 0 | 100,000 µUSDT (full refund) |

Sellers earn more for faster, valid responses. Buyers are protected from failures. No one is "punished into zero" for slight slowness.

---

## Architecture

```
Buyer Agent (Python)
    │
    ├─ 1. WDK Wallet → approve + deposit(max_price) on-chain
    ├─ 2. x402 payment → Gateway /v1/call
    │
    └─ Gateway (FastAPI)
           ├─ 3. Forward to Seller, measure TTFT + latency
           ├─ 4. JSON Schema validation
           ├─ 5. Deterministic payout from latency tier
           ├─ 6. Sign Performance Receipt
           └─ 7. SLASettlement.settle() on-chain
                    ├─ Seller receives payout
                    └─ Buyer receives refund

WDK Sidecar (Node.js, port 3100)
    └─ Key isolation, nonce management, signing for all roles

Dashboard (React + Vite)
    └─ Real-time monitoring, simulator, history replay
```

---

## Track Fit

### 🤖 Agent Wallets (WDK / Openclaw) — Primary Track

| Requirement | Implementation |
|-------------|----------------|
| WDK wallet integration | `@tetherto/wdk` + `@tetherto/wdk-wallet-evm` sidecar with full CRUD |
| Agents hold wallets | Buyer / Seller / Gateway each have independent EOA (derived from single mnemonic) |
| Autonomous asset movement | Buyer Agent auto-executes approve → deposit → call → attest cycle |
| On-chain settlement | SLASettlement contract on Sepolia with escrow + dispute |
| Production-grade WDK usage | Nonce manager, circuit breaker, retry, Bearer auth, RPC fallback, metrics |

### 🌊 Autonomous DeFi Agent — Secondary Track

- Escrow → conditional settlement = classic DeFi pattern, agent-operated
- Buyer agent manages budget autonomously without human input
- Dispute mechanism with bond slashing for trustless guarantees
- Multi-step tool chains with per-step deposit tracking

---

## Demo Flow (7 min)

**Step 1 — Environment** (30s)
Open dashboard, verify Gateway / Seller / WDK connectivity

**Step 2 — Happy Path** (2 min)
Select Gold SLA preset → Start Autopilot → Watch: `Payout: 100,000`, `Refund: 0`, full 3-party attestation, on-chain `Settled` event

**Step 3 — Slow SLA** (1.5 min)
Switch to slow mode → `Payout: 80,000`, `Refund: 20,000`, breach reason: `BREACH_LATENCY_TIER_DOWN`

**Step 4 — SLA Simulator** (2 min)
Drag latency slider to 7s → `Payout: 60,000` (base only). Toggle schema fail → `Payout: 0`, `Refund: 100,000` (full refund)

**Step 5 — History Replay** (1 min)
Open History page → select request → see full lifecycle: negotiation → 402 → execution → validation → settlement → attestation

**Step 6 — On-chain Proof** (30s)
Click `tx_hash` → Sepolia explorer shows `Settled` event with receipt hash

Judges see:
1. WDK wallet loading and live balance updates
2. Autonomous deposit → call → settle cycle with no human input
3. Deterministic payout changes in real-time based on SLA
4. On-chain proof for every settlement
5. Dispute flow with bond mechanics

---

## Live Deployment

| Service | URL |
|---------|-----|
| **Dashboard** | https://dashboard-woad-nine-19.vercel.app |
| **Gateway API** | https://gateway-production-c5d6.up.railway.app |
| **Seller API** | https://seller-production-c5ae.up.railway.app |
| **WDK Sidecar** | https://wdk-production.up.railway.app |

## Network / Token

| | |
|--|--|
| **Chain** | Ethereum Sepolia (`11155111`) |
| **Token (Mock USDT)** | [`0x4029A86BcD3c366DD750EaFe3a899c9C6144d662`](https://sepolia.etherscan.io/address/0x4029A86BcD3c366DD750EaFe3a899c9C6144d662) |
| **Settlement Contract** | [`0xDEf30B0ae11b26BAA1218C485C3D00090aDD5936`](https://sepolia.etherscan.io/address/0xDEf30B0ae11b26BAA1218C485C3D00090aDD5936) |
| **Wallet** | `@tetherto/wdk` + `@tetherto/wdk-wallet-evm` |

---

## How To Run

```bash
# 1. Install
cp .env.example .env          # fill in GEMINI_API_KEY
cd wdk-service && npm install && cd ..
pip install -e ".[dev]"

# 2. One-command demo (deploy + run + prove)
python scripts/demo_one_command.py

# 3. Open dashboard
open http://localhost:8000/dashboard/
```

Deterministic mode (no Gemini required):
```bash
SELLER_FALLBACK=true \
DEMO_MNEMONIC="test test test test test test test test test test test junk" \
python scripts/demo_one_command.py
```

---

## Technical Highlights

- **WDK-native**: All wallet operations (approve, deposit, sign, attest) go through WDK sidecar — no raw private key handling in application code
- **Deterministic pricing**: Payout computed from measured latency tiers + schema validation. No LLM scoring on the settlement path
- **Fail-closed**: Invalid output or upstream failure → full refund. `payout ≤ max_price` enforced at contract level
- **Deposit verification**: Gateway checks actual on-chain `Deposited` event before forwarding work
- **Multi-attestation**: Buyer + Seller + Gateway all sign each receipt (3-party attestation)
- **Single-secret demo**: One mnemonic derives all role keys — clean demo, clear role separation
- **Agentic tool chains**: Buyer executes 2+ paid tool calls in sequence, each with its own deposit and receipt
- **Event ledger**: Every step from negotiation to settlement is recorded and replayable
- **50+ test files** covering contracts, gateway, buyer agent, seller, WDK sidecar

## Limits (Honest)

- Gateway is trusted for measurement and receipt issuance
- Dispute resolver is centralized in MVP
- Mock USDT on testnet — not production liquidity
- Single-gateway topology (no multi-gateway federation yet)
