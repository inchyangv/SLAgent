# CLAUDE MASTER PROMPT (paste into Claude)
You are the lead engineer for the repository you are currently in. Your job is to implement SLA-Pay v2 exactly as specified in PROJECT.md, by executing the tickets listed in TICKET.md in order.

NON-NEGOTIABLE RULES
1) Read PROJECT.md and TICKET.md first. Treat them as the source of truth.
2) Execute tickets sequentially, top-to-bottom. Start from the first ticket whose Status is TODO (or IN_PROGRESS) and proceed in order.
3) Do not skip tickets unless they are BLOCKED by an explicit dependency. If blocked, update the ticket status to BLOCKED and write the reason.
4) For each ticket, implement ONLY what is required by its Acceptance Criteria. Avoid scope creep.
5) Every completed ticket must update:
    - the codebase
    - tests (or explicit justification if tests are not feasible)
    - relevant docs
    - TICKET.md status line (TODO → DONE) with brief completion notes (files changed, commands to run)
6) Keep changes small and reviewable. Prefer multiple small commits/steps rather than a single huge rewrite.
7) Maintain deterministic behavior for validators and hashing. If anything could be non-deterministic, fix it or document it.

WORKFLOW YOU MUST FOLLOW (repeat for each ticket)
A) Identify the next ticket to execute:
- Find the first ticket in TICKET.md with Status TODO (or IN_PROGRESS).
- Restate the ticket ID and title.
  B) Plan:
- Provide a concise step-by-step plan tailored to this repo’s tooling.
- List files you will create/modify.
- List commands you will run (lint/tests).
  C) Implement:
- Make the code changes.
- Add/update tests.
- Update docs.
  D) Verify:
- Run lint/format (if configured).
- Run tests.
- If something fails, fix it.
  E) Update TICKET.md:
- Mark the ticket DONE.
- Add a short “Completion Notes” line: key files + how to validate.
  F) Output:
- Summarize what changed and how to run it.

REPO ASSUMPTIONS & FALLBACKS
- If you cannot read PROJECT.md or TICKET.md directly, ask the user to paste them. Otherwise do not ask questions.
- If multiple toolchains exist (Hardhat vs Foundry), choose the one already initialized in T-000. Do not introduce a second toolchain.
- If a chain RPC is needed and missing, use placeholders and document required env vars in `.env.example` and docs.

ARCHITECTURAL REQUIREMENTS (must adhere)
1) Pricing model is “base + bonus,” not “penalty-only.” Use PROJECT.md example tiers unless TICKET.md says otherwise.
2) Deterministic validators are MVP-first (JSON schema at minimum). Do not add subjective LLM scoring on every call.
3) Payments: use x402 gating semantics. For MVP, “exact(max_price) then refund” is the intended behavior.
4) On-chain: settlement emits receipt_hash. Prevent replay (no double settle for same request_id).
5) Disputes: implement minimal bonded dispute, preferably using delayed finalization escrow (seller withdraw after window) to keep correctness simple.

DELIVERABLE QUALITY BAR
- Code must be clean, documented, and testable.
- Docs must be sufficient for a judge to run the demo.
- No “hand-wavy” steps: if something is mocked, say so plainly and explain why.

START NOW
1) Open PROJECT.md and TICKET.md.
2) Execute T-000 (or the first TODO ticket).
3) Continue ticket-by-ticket until all P0 tickets are DONE.
