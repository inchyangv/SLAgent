# Security Notes & Threat Model — SLAgent-402

## Overview

This document describes the security model, trust assumptions, and known limitations
of SLAgent-402 as implemented for the hackathon MVP.

## Trust Model

### Gateway is Trusted (MVP)

In the current design, the **gateway is the single attestation authority**:
- It measures TTFT/latency
- It runs validators
- It signs the performance receipt
- It submits the settlement transaction

**Implication:** A compromised gateway can produce false receipts and steal funds.

**Mitigation (future):** Multi-attestation (buyer + seller + gateway co-sign receipts),
allowing any party to detect and dispute fraudulent attestations.

### Buyer Trust

- Buyer pays `exact(max_price)` upfront (locked in escrow)
- Buyer's maximum loss is bounded by `max_price`
- Buyer receives automatic refund for underperformance via pricing engine
- Buyer can open disputes within the dispute window

### Seller Trust

- Seller receives at least `base_pay` for valid, successful work
- Seller cannot claim more than `max_price`
- Seller funds are escrowed until dispute window expires
- Seller can be disputed, but frivolous disputes are deterred by bonds

## Replay Protection

### On-chain
- Each `requestId` can only be settled once
- `settlements[requestId].status != NONE` check prevents replay
- Contract stores settlement state permanently

### Off-chain
- Facilitator tracks submitted `requestId`s in an idempotency set
- Duplicate submissions are silently dropped

## Dispute Mechanism

### Bond Requirement
- Disputer must deposit `bondAmount` tokens to open a dispute
- This deters griefing attacks (spam disputes to freeze seller funds)

### Resolution
- Resolver (trusted party in MVP) decides `finalPayout`
- If payout changes → disputer was right → bond returned
- If payout unchanged → disputer was wrong → bond slashed to resolver

### Window
- Disputes must be opened within `disputeWindow` seconds of settlement
- After window, seller can call `finalize()` to withdraw

## Known Limitations (MVP)

### 1. Single Gateway Attestation
The gateway is a single point of trust. A malicious gateway can:
- Report false latency (e.g., claim slow when fast)
- Forge validation results
- Sign receipts for requests that never happened

**Future fix:** Multi-party attestation with cryptographic proofs.

### 2. Centralized Resolver
The dispute resolver is a single trusted address. A colluding resolver can:
- Always side with one party
- Steal dispute bonds

**Future fix:** Decentralized arbitration (Kleros-style) or deterministic re-validation.

### 3. HMAC Payment (Not Real x402)
MVP uses HMAC-based payment tokens instead of real on-chain x402 proofs.
This means payments are not cryptographically tied to on-chain state.

**Future fix:** Integrate with actual x402 payment verification.

### 4. In-Memory State
Receipts and dispute state are stored in-memory. Server restart loses data.

**Future fix:** Persistent storage (SQLite, PostgreSQL, or IPFS for receipts).

### 5. No Rate Limiting
Gateway has no rate limiting, making it vulnerable to DoS.

**Future fix:** Rate limiting per buyer address.

### 6. Encrypted Conditional Settlement (BITE v2)
Sensitive conditions/pricing/policy are encrypted and only decrypted when
SLA and policy checks pass. Failed conditions keep data sealed and block
settlement.

## What Cannot Be Cheated (Even in MVP)

1. **Payout invariant:** `payout <= max_price` is enforced on-chain
2. **Replay protection:** Same requestId cannot be settled twice
3. **Bond slashing:** Opening a frivolous dispute costs real tokens
4. **Escrow safety:** Funds are locked until window expires or dispute resolves
5. **Deterministic validation:** JSON schema validation is reproducible by any party

## Recommendations for Production

1. Implement multi-party receipt signing
2. Add real x402 on-chain payment verification
3. Decentralize the resolver role
4. Add receipt storage with content-addressable hashing (IPFS)
5. Implement rate limiting and access controls
6. Conduct formal smart contract audit
7. Expand encrypted policy coverage and formalize decryption attestations
