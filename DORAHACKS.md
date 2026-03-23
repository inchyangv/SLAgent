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

---

## DoraHacks Submission Answers (Copy-Paste Ready)

아래는 DoraHacks BUIDL 제출 폼 각 필드에 복붙할 플레인 텍스트.

---

### BUIDL Name

SLAgent

---

### One-Liner / Short Description

Autonomous AI agents trade services using WDK wallets, with on-chain escrow that settles payment based on measured SLA performance — not trust.

---

### Track

Agent Wallets (WDK / Openclaw and Agents Integration)

---

### Description (Long)

SLAgent is a pay-by-performance settlement layer for autonomous agent-to-agent API calls. When an AI buyer agent calls another AI seller agent's API, payment is no longer fixed — it is determined by measured SLA outcomes.

The buyer agent uses a WDK wallet sidecar to deposit max_price into an on-chain escrow before execution. After the seller responds, the gateway measures latency, validates output against a JSON schema, and deterministically computes payout based on latency tiers. The settlement contract splits funds: seller receives payout, buyer receives automatic refund for the remainder. Every settlement emits a receipt hash on-chain.

The system includes a full dispute mechanism with bond slashing, 3-party receipt attestation (buyer + seller + gateway), an event ledger that records every step from negotiation to settlement, and a React dashboard for real-time monitoring and SLA simulation.

All wallet operations — approve, deposit, sign, transfer — go through a WDK sidecar built on @tetherto/wdk and @tetherto/wdk-wallet-evm, with production hardening: per-wallet nonce manager, retry with circuit breaker, Bearer token authentication, RPC provider fallback, structured logging, and graceful shutdown.

---

### How does your project use WDK?

SLAgent uses WDK as the core wallet infrastructure for all agent roles. The WDK sidecar (Node.js service built on @tetherto/wdk + @tetherto/wdk-wallet-evm) handles every wallet operation in the system:

1. Wallet creation and key derivation from a BIP-39 mnemonic, with separate accounts per role (buyer index 0, seller index 1, gateway index 2, resolver index 3)
2. ERC-20 approve and deposit calls for escrow funding
3. Transaction signing for settlement and dispute operations
4. An atomic approve-and-deposit endpoint with retry for reliable on-chain interactions
5. Message signing for receipt attestation (buyer/seller/gateway 3-party signatures)

The sidecar runs as a standalone service and is called by the Python buyer agent and gateway via HTTP. No private keys are ever handled in application code — all signing goes through WDK. The sidecar includes production hardening: per-wallet nonce manager to prevent transaction collisions, retry with exponential backoff and circuit breaker, Bearer token authentication, RPC provider fallback, structured request logging with a /metrics endpoint, and graceful shutdown.

---

### What problem does your project solve?

In current AI API markets, buyers pay the same price regardless of whether the response is fast or slow, valid or malformed, successful or failed. When autonomous agents make thousands of calls without human oversight, this misalignment wastes capital and provides zero quality incentive to sellers.

SLAgent solves this by introducing verifiable, SLA-driven settlement:
- Buyers lock max_price into escrow before execution, guaranteeing they never overpay
- Sellers earn more for faster, valid responses (latency tier bonuses)
- Failed or invalid outputs trigger automatic full refund — no manual dispute needed
- Every settlement is backed by a signed performance receipt with on-chain proof
- Disputes are handled through a bonded challenge mechanism with slashing

The result: agents can trade services autonomously with aligned economic incentives, verifiable proofs, and zero trust required.

---

### How does the agent operate autonomously?

The buyer agent operates a fully autonomous loop without human intervention:

1. Discovers seller capabilities by querying the seller API
2. Negotiates SLA terms — selects from Bronze/Silver/Gold offer presets, optionally uses Gemini LLM to evaluate mandate conditions
3. Calls the WDK sidecar to execute approve and deposit on-chain
4. Sends the API call to the gateway with deposit proof
5. Receives and verifies the performance receipt (fail-closed: any invariant violation triggers rejection)
6. Submits receipt attestation (buyer signature)
7. If SLA breach is detected, automatically opens an on-chain dispute with bond
8. Tracks cumulative spend against a budget limit across multiple calls
9. Executes multi-step tool chains (2+ paid calls per workflow) with per-step deposit and receipt tracking

The entire cycle — from negotiation through settlement — runs on a configurable autopilot timer with no human input required.

---

### Technical Architecture

The system has five components:

Buyer Agent (Python): Autonomous agent that discovers sellers, negotiates SLA terms, calls WDK for approve/deposit, sends requests through the gateway, verifies receipts, and opens disputes when needed. Supports multi-step agentic tool chains with budget tracking.

SLA Gateway (FastAPI): Reverse proxy that sits between buyer and seller. Verifies on-chain deposit before forwarding work. Measures TTFT and total latency. Runs JSON schema validation. Computes payout from deterministic latency tiers. Signs performance receipts. Submits settlement on-chain. Maintains an event ledger of every step.

Seller Service (FastAPI + Gemini): LLM-powered API service using Gemini 2.0 Flash. Supports controllable demo modes (fast/slow/invalid/error/timeout) with simulation controls (delay_ms slider, force_error toggle).

WDK Sidecar (Node.js): Self-custodial wallet service built on @tetherto/wdk + @tetherto/wdk-wallet-evm. Handles create, approve, deposit, sign, transfer, balance. Production hardened with nonce manager, circuit breaker, retry, Bearer auth, RPC fallback, structured logging, graceful shutdown.

Settlement Contract (Solidity/Foundry): On-chain escrow with deposit, settle, openDispute, resolveDispute, finalize. Escrow-based payout delayed until dispute window closes. Bond slashing for wrongful disputes. Receipt hash emitted on-chain.

Dashboard (React + Vite): Real-time monitoring with live balance panel, receipts table, event timeline, SLA simulator with latency slider and failure toggles, history page with full lifecycle replay, negotiation history, and dispute panel.

---

### Economic Model

The payout model uses a bonus structure, not a penalty structure:

max_price = 100,000 µUSDT (0.10 USDT), locked by buyer in escrow before execution.

If the seller succeeds and output passes schema validation:
- Latency 2 seconds or less: payout 100,000 (full pay, zero refund)
- Latency between 2 and 5 seconds: payout 80,000 (refund 20,000)
- Latency over 5 seconds: payout 60,000 base only (refund 40,000)

If the seller fails or output is invalid: payout 0, full refund 100,000.

This aligns incentives: sellers earn more for better performance, buyers are protected from bad outcomes, and no one is punished into zero for slight slowness.

---

### Demo Link

https://dashboard-woad-nine-19.vercel.app

---

### GitHub Repository

https://github.com/inchyangv/SLAgent

---

### Live API Endpoints

Gateway: https://gateway-production-c5d6.up.railway.app
Seller: https://seller-production-c5ae.up.railway.app
WDK Sidecar: https://wdk-production.up.railway.app

---

### Smart Contract Addresses (Sepolia)

Mock USDT Token: 0x4029A86BcD3c366DD750EaFe3a899c9C6144d662
SLASettlement Contract: 0xDEf30B0ae11b26BAA1218C485C3D00090aDD5936
Chain: Ethereum Sepolia (Chain ID 11155111)

---

### Tech Stack

Smart Contracts: Solidity 0.8.24, Foundry, OpenZeppelin
Gateway: Python 3.11, FastAPI, web3.py, eth-account, httpx
Buyer Agent: Python 3.11, httpx async, Gemini SDK
Seller: Python 3.11, FastAPI, Google Gemini 2.0 Flash
WDK Sidecar: Node.js 20, @tetherto/wdk, @tetherto/wdk-wallet-evm, ethers v6, Express
Dashboard: React 19, Vite, TypeScript, TanStack Query, Recharts, Tailwind CSS, wagmi, RainbowKit
Deployment: Railway (backend), Vercel (frontend), Sepolia (contracts)

---

### What makes your project different from existing solutions?

Existing AI API payment is fixed-price and trust-based. SLAgent introduces three things that do not exist today:

1. Proof that an SLA was met or breached — every call produces a signed performance receipt with latency metrics, validation results, and payout computation, with the receipt hash recorded on-chain.

2. Automatic split and refund based on measured outcomes — the settlement contract deterministically divides escrowed funds between seller (payout) and buyer (refund) based on SLA tier results. No human arbitration needed for the common case.

3. WDK-native autonomous wallet operations — agents hold their own wallets through WDK, execute approve/deposit/sign autonomously, and never expose private keys to application code. The sidecar is production-hardened with nonce management, circuit breaking, and retry logic.

The result is a system where any AI API can be wrapped with SLA-guaranteed settlement by placing the gateway in front of it.

---

### Challenges faced during development

The main challenge was making WDK reliable enough for autonomous agent use. When an agent sends transactions without human oversight, every failure mode matters. We built per-wallet nonce management to prevent transaction collisions, retry with exponential backoff and circuit breaker to handle RPC instability, an atomic approve-and-deposit endpoint to avoid partial state, and RPC provider fallback for resilience. We also had to ensure the settlement contract's escrow timing aligned correctly with the dispute window — payout is delayed until the window closes, which required careful coordination between the gateway's settlement calls and the contract state machine.

---

### Future plans

- Support more validator types beyond JSON schema (SQL test harness, function-call validation)
- Multi-gateway federation for decentralized measurement
- Cross-chain settlement with receipt bridging
- Reputation scoring for seller endpoints based on historical SLA compliance
- Standardized receipt signing with multi-sig (buyer + seller + gateway)
- Receipt storage and indexing layer for large-scale audit
- Production USDT deployment on mainnet
