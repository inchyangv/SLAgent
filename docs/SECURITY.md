# Security Notes & Threat Model — SLAgent-402

## Overview

This document captures the MVP trust model for the current WDK + deposit-first design.

## Trust Model

### Gateway Is Trusted

The gateway is still the measurement and receipt authority:

- measures latency
- runs deterministic validators
- computes payout/refund
- signs settlement authorization
- submits settlement/dispute transactions

Implication: a compromised gateway can lie about performance.

Planned mitigation:
- multi-party receipt signatures
- independently reproducible metrics capture

### Buyer Trust

- Buyer loss is capped by `max_price`.
- Buyer deposit is visible on-chain before work begins.
- Buyer receives automatic refund according to deterministic pricing rules.
- Buyer can open a bonded dispute within the dispute window.

### Seller Trust

- Seller cannot receive more than `max_price`.
- Seller payout is gated by escrowed funds and settlement state.
- Frivolous disputes cost a bond.

## What Improved in the Deposit-First Migration

### On-Chain Deposit Verification

The gateway now checks:

- transaction hash format
- transaction target equals settlement contract
- decoded `deposit()` calldata matches `request_id` and buyer
- `Deposited` event matches calldata
- deposited amount covers the mandate `max_price`

This is stronger than trusting an off-chain payment header.

### Local WDK Signing Surface

The WDK sidecar exposes only wallet operations needed by the demo:

- approve
- deposit
- balance
- sign-message
- sign-bytes

The sidecar is still part of the local operator trust boundary and should not be exposed publicly.

## Disputes

- Disputer posts `bondAmount`
- Resolver chooses `finalPayout`
- Correct dispute returns bond
- Incorrect dispute slashes bond

## Known MVP Limits

1. Gateway remains a trusted coordinator.
2. Resolver is centralized.
3. Receipt/event storage is local unless persistent DB is configured.
4. No production-grade rate limiting or auth.
5. WDK sidecar is localhost-oriented infrastructure, not a hardened multi-tenant service.

## Strong Invariants

1. `payout <= max_price` is enforced on-chain.
2. Same `requestId` cannot be deposited/settled twice.
3. Refund is `max_price - payout`.
4. Deposit verification is tied to actual calldata and emitted event.
5. Validation logic is deterministic and reproducible.

## Production Recommendations

1. Add multi-party receipt signing.
2. Decentralize the resolver role.
3. Persist receipts and events in durable storage.
4. Add authentication and rate limiting around gateway/sidecar services.
5. Audit the contracts and wallet bridge before mainnet-like usage.
