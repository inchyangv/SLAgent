SLAgent-402 Demo Script (5 min)


BEFORE RECORDING

  Open deployed dashboard in browser.
  Top-right should say "Gateway OK".
  If old receipts are showing, refresh or clear.


1. INTRO (30s)

  This is SLAgent-402.
  When an AI agent buys a service from another agent, it pays the same whether the result is good or bad. That's broken.
  SLAgent fixes it. Buyer locks max price in escrow. Gateway measures the actual performance. Good result — full pay. Bad result — automatic refund. All on-chain.
  Let me show you.


2. FAST + VALID = FULL PAY (60s)

  DO: SLA Offer -> Silver. Mode -> Fast. Delay 0ms. Click Run.

  Latency under 2 seconds, schema valid — seller gets 100% payout, 100,000 micro-USDT. Buyer refund is zero.
  (point at receipts row) Every call gets a receipt with payout, latency, and on-chain tx hash.
  (point at event timeline) Full audit trail — payment, execution, validation, pricing, settlement. Every step recorded.


3. SLOW = PARTIAL REFUND (60s)

  DO: Mode -> Slow. Click Run.

  Output is valid, but latency exceeded 2 seconds. Tier drops — payout is 80,000, buyer gets 20,000 back.
  (point at breach pill) LATENCY_TIER_DOWN. Deterministic — no LLM judging. Measured latency against SLA tiers.


4. INVALID = FULL REFUND (60s)

  DO: Mode -> Invalid. Click Run.

  Schema validation failed. Payout is zero, buyer gets full 100,000 back.
  Fail-closed — if output can't be verified, buyer is fully protected.


5. SIMULATOR (45s)

  DO: Drag delay slider to 7000ms. Mode -> Fast. Click Run.

  7 seconds — slowest tier. Seller gets only base pay, 60,000. 40% penalty for being slow.

  DO: Toggle "Force Invalid Schema" ON. Click Run.

  Schema broken — zero payout, full refund. SLA enforced on every call, no exceptions.


6. RECEIPT DETAIL (30s)

  DO: Click any receipt row to open detail panel.

  Payout, refund, latency, TTFT, pricing rule, schema result, cryptographic hashes — all in one receipt.
  Three-party attestation — buyer, seller, gateway all sign.
  TX hash links to the block explorer. On-chain proof.


7. DISPUTE (30s)

  DO: Copy a request_id. Paste in Disputes field. Click Open. Then click Resolve.

  Either party can dispute by posting a bond. Resolver re-checks validators. Wrongful disputes get slashed.


8. CLOSE (30s)

  SLAgent turns "pay and hope" into "pay by proof."
  Sellers earn more for better performance. Buyers are protected from failures.
  No trust required — just math and proofs. Thank you.
