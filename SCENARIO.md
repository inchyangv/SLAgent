SLAgent-402 Demo Script (5 min)

URL: https://sl-agent-two.vercel.app/
Nav: Dashboard | Receipts | Disputes | History | Settings


BEFORE RECORDING

  Open the URL above. Top nav should show green dot + "Sepolia".
  If old data is showing, go to Settings page and click save, then come back to Dashboard.


1. INTRO (30s)

  [Screen: Dashboard page. Overview section shows stats. Charts are visible.]

  This is SLAgent-402.
  When an AI agent buys a service from another agent, it pays the same whether the result is good or bad. That's broken.
  SLAgent fixes it. Buyer locks max price in escrow. Gateway measures the actual performance. Good result — full pay. Bad result — automatic refund. All on-chain.
  Let me show you.


2. FAST + VALID = FULL PAY (60s)

  [Section: "SLA Evaluator & Simulator" — two cards side by side]

  DO: Left card "SLA Evaluator" — click "happy" preset button (top right of card).
  DO: Click green "Start" button.
  DO: Wait 1-2 ticks. The 5 metric boxes update: Mode=happy, SLA Status=PASS (green), Payout, Refund, LLM Judge.

  Latency under 2 seconds, schema valid — seller gets 100% payout. Buyer refund is zero.

  DO: Click "Show details" link below the metrics to expand — shows Request ID, Latency, LLM info.
  DO: Click "Stop" button.

  DO: Scroll down to "Recent Receipts" table at the bottom.
  (point at green row) Every call gets a receipt with payout, latency, validation status.

  DO: Scroll down more to "Event Timeline" section.
  (point at timeline) Full audit trail — payment verified, seller response, schema pass, pricing computed. Every step recorded.


3. SLOW = PARTIAL REFUND (60s)

  DO: Scroll back up to "SLA Evaluator" card.
  DO: Click "slow" preset button (turns amber).
  DO: Click "Start". Wait 1-2 ticks.
  DO: SLA Status changes to BREACH (red). Payout drops. Refund appears.
  DO: Click "Stop".

  Output is valid, but latency exceeded 2 seconds. Tier drops — payout is 60,000, buyer gets 40,000 back.

  DO: Scroll to "Recent Receipts" — new row with amber/red breach badge.
  (point at breach reasons) Deterministic — no LLM judging. Measured latency against SLA tiers.


4. INVALID = FULL REFUND (45s)

  DO: Scroll to right card "SLA Simulator".
  DO: Check the "Schema Fail" checkbox. Badge at top right turns red "Schema Fail".
  DO: Click "Run Scenario" button.
  DO: Result appears in "Recent Runs" list below the button — shows BREACH badge.

  Schema validation failed. Payout is zero, buyer gets full refund.
  Fail-closed — if output can't be verified, buyer is fully protected.


5. SIMULATOR SLIDER (45s)

  DO: Uncheck "Schema Fail".
  DO: Drag the "Delay" slider to 7000ms (or click the "8s" tick mark).
  DO: Badge changes to "Base Only" (red).
  DO: Click "Run Scenario".

  7 seconds — slowest tier. Seller gets only base pay, 60,000. 40% cut for being slow.

  DO: Now check "Schema Fail" again.
  DO: Click "Run Scenario".

  Schema broken on top of slow — zero payout, full refund. SLA enforced on every call.

  DO: Uncheck "Schema Fail" and reset slider to 0.


6. RECEIPT DETAIL (30s)

  DO: Click "Receipts" in the top nav bar.
  DO: Click any receipt row to expand detail.

  Payout, refund, latency, TTFT, pricing rule, schema result, cryptographic hashes — all in one receipt.
  Three-party attestation — buyer, seller, gateway all sign.
  TX hash links to the block explorer. On-chain proof.


7. HISTORY PAGE (30s)

  DO: Click "History" in the top nav bar.
  DO: Click a request on the left panel.
  DO: Right side shows full event timeline for that single request.

  Every call's entire lifecycle — from negotiation to settlement — is recorded and replayable.


8. DISPUTE (30s)

  DO: Go back to Dashboard (click "Dashboard" in nav).
  DO: Scroll to the Disputes card (below Negotiation & Seller section).
  DO: Enter a request_id from the receipts.
  DO: Click "Open Dispute".

  Either party can dispute by posting a bond. Resolver re-checks validators. Wrongful disputes get slashed.


9. CLOSE (30s)

  [Screen: Dashboard with charts showing mixed green/red results from the demo.]

  SLAgent turns "pay and hope" into "pay by proof."
  Sellers earn more for better performance. Buyers are protected from failures.
  No trust required — just math and proofs. Thank you.
