# SLA-Pay v2 — Execution Tickets
**Rule:** Execute tickets top-to-bottom. Do not skip unless explicitly blocked by dependencies.

## Ticket Status Legend
- TODO
- IN_PROGRESS
- DONE
- BLOCKED (must include reason)

## Priority Legend
- P0: must-have for hackathon MVP demo
- P1: strong-to-have for judging and polish
- P2: optional stretch

## Definition of Done (DoD)
A ticket is DONE only when:
- Acceptance Criteria are met
- Tests added/updated and passing
- Docs updated (where applicable)
- Ticket status updated with completion notes and artifact pointers

---

## T-000 — Repo Bootstrap & Standards
**Status:** DONE
**Priority:** P0  
**Depends on:** none

### Description
Initialize repository structure and engineering standards so all subsequent tickets can be executed without churn.

### Tasks
- Create directory structure: `contracts/`, `gateway/`, `dashboard/`, `docs/`
- Add root README with quickstart
- Add basic tooling:
    - Python: `pyproject.toml` (ruff, mypy), pytest
    - Solidity: Hardhat (TypeScript) or Foundry (choose one)
    - Node: package manager lockfile
- Add `.editorconfig`, `.gitignore`
- Add CI config (GitHub Actions) to run:
    - Python lint + tests
    - Solidity tests
- Add environment templates:
    - `.env.example` for gateway and dashboard

### Acceptance Criteria
- Clean repo layout exists and matches PROJECT.md target layout
- CI passes on a no-op run
- Local quickstart documented in README

### Deliverables
- repo structure + configs + README

### Completion Notes
- Created: contracts/, gateway/, dashboard/, docs/, facilitator/, scripts/, .github/workflows/
- Tooling: pyproject.toml (ruff/mypy/pytest), foundry.toml, package.json
- CI: .github/workflows/ci.yml (Python lint+test, Solidity build+test)
- Configs: .gitignore, .editorconfig, .env.example files
- README.md with quickstart
- Validate: `pytest gateway/tests/ -v`

---

## T-001 — Choose Chain + Token Strategy (MVP)
**Status:** DONE
**Priority:** P0  
**Depends on:** T-000

### Description
Define how value moves in the demo: which network, which token, and how decimals are handled.

### Tasks
- Pick SKALE chain RPC used for demo (testnet or mainnet-like environment)
- Decide token type:
    - simplest: deploy an ERC20 mock token with fixed decimals
- Document decimals and amount units in docs

### Acceptance Criteria
- `docs/ARCHITECTURE.md` includes chain + token decisions
- Amount unit conventions are defined and consistent

### Deliverables
- docs update + optional token contract scaffold

### Completion Notes
- SKALE Europa Hub (chain 2046399126, zero gas fees)
- ERC20 mock token (SLAT, 6 decimals) — matches USDC convention
- Amount conventions documented in docs/ARCHITECTURE.md
- Integer arithmetic rules: round down, payout <= max_price invariant

---

## T-010 — Settlement Contract (Core Split + Refund)
**Status:** DONE
**Priority:** P0  
**Depends on:** T-001

### Description
Implement the on-chain settlement primitive:
- receive `max_price`
- record settlement with receipt hash
- pay seller + refund buyer

### Tasks
- Implement ERC20-based settlement contract:
    - `settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, gatewaySig)`
    - verify: `payout <= maxPrice`, addresses non-zero
    - transfer payout to seller
    - transfer refund to buyer
    - emit `Settled(...)`
- Implement signature verification for gateway attestation:
    - define `EIP-712` typed data or `eth_sign` style; pick one and document it
- Add unit tests: payout/refund correctness, signature checks, replay protection

### Acceptance Criteria
- Contract passes all tests
- Receipt hash appears in emitted event
- Replay protection exists (cannot settle same requestId twice)

### Deliverables
- `contracts/src/Settlement.sol`
- tests and deployment scripts

### Completion Notes
- contracts/src/SLASettlement.sol: settle() with ECDSA sig verification, replay protection, split+refund
- contracts/src/SLAToken.sol: mock ERC20 (6 decimals)
- contracts/test/SLASettlement.t.sol: 9 tests (full/partial/zero payout, replay, overflow, zero-addr, bad sig, event)
- Validate: `cd contracts && forge test -v`

---

## T-011 — Dispute Contract (Minimal Escrow or Delay Mechanism)
**Status:** DONE
**Priority:** P0  
**Depends on:** T-010

### Description
Add an MVP dispute mechanism with bonding to deter spam. For MVP safety and simplicity, implement **delayed finalization**:
- funds are escrowed at settle-time
- seller withdrawal is allowed only after dispute window passes without dispute
- dispute can freeze and require resolver final decision

### Tasks
- Extend settlement contract with:
    - store settlement state: `PENDING`, `DISPUTED`, `FINALIZED`
    - `openDispute(requestId)` requiring bond
    - `resolveDispute(requestId, finalPayout)` callable by resolver
    - `finalize(requestId)` callable after window expiration if not disputed
- Decide how bonds are handled in MVP:
    - keep bond in contract and pay/slash on resolution
- Add tests: normal finalize, dispute open, resolver finalize

### Acceptance Criteria
- In normal path, seller can withdraw after window
- Dispute path blocks withdrawal until resolved
- Bond is required and accounted for

### Deliverables
- updated contract + tests + docs

### Completion Notes
- SLASettlement.sol extended: escrow-based delayed finalization, PENDING→DISPUTED→FINALIZED states
- openDispute(requestId) with bond, resolveDispute(requestId, finalPayout) by resolver
- finalize(requestId) after window expires without dispute
- Bond returned to disputer if they win, slashed to resolver if they lose
- 18 Foundry tests covering settle, finalize, dispute open/resolve paths
- Validate: `cd contracts && forge test -v`

---

## T-020 — SLA Mandate & Receipt Schemas (Canonical)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-000

### Description
Codify SLA Mandate and Receipt structures as JSON schema, plus hashing rules, so all components interoperate.

### Tasks
- Create `docs/API.md` with:
    - Mandate JSON schema
    - Receipt JSON schema
    - Hashing rules: canonical JSON serialization, field order, etc.
- Implement reference hashing in code:
    - `mandate_id = keccak256(canonical_mandate_payload)`
    - `receipt_hash = keccak256(canonical_receipt_payload)`
- Add test vectors:
    - known input → known hash output

### Acceptance Criteria
- Schema docs are unambiguous
- Hashing outputs are deterministic across runs
- At least 3 test vectors exist

### Deliverables
- `docs/API.md`
- reference implementation code in gateway (or shared lib)

---

## T-030 — Gateway Skeleton (FastAPI Reverse Proxy)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-000

### Description
Build the FastAPI gateway that proxies to seller service, measures metrics, validates output, and produces receipts.

### Tasks
- FastAPI app with endpoints:
    - `POST /v1/call` (main)
    - `GET /v1/health`
    - `GET /v1/receipts/{request_id}`
- Config: seller upstream URL, chain RPC, contract address, token address
- Streaming support:
    - capture TTFT and overall latency
- Basic request/response hashing

### Acceptance Criteria
- Gateway can proxy a request to a dummy seller service
- TTFT/latency are measured and returned in a debug response
- Receipt storage works (in-memory + optional file/db)

### Deliverables
- `gateway/app/main.py` etc.
- tests for core paths

---

## T-031 — Deterministic Validator: JSON Schema
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-030, T-020

### Description
Implement JSON schema validation as the MVP proof of correctness.

### Tasks
- Add validator module:
    - load schema by `schema_id`
    - validate response JSON
    - return structured result object
- Include at least one demo schema: `invoice_v1` or similar
- Add tests: pass/fail cases

### Acceptance Criteria
- Validator deterministically returns pass/fail + error details
- Receipt includes validator result block

### Deliverables
- `gateway/app/validators/json_schema.py`
- schema files + tests

---

## T-032 — Pricing Engine (Base + Bonus Rules)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-030, T-020

### Description
Compute payout from mandate + measured metrics + validator result.

### Tasks
- Implement pricing engine:
    - input: mandate, metrics, validation outcome
    - output: payout, refund, rule_applied
- Implement example latency tier rule set
- Add unit tests for pricing decisions

### Acceptance Criteria
- Pricing decisions match PROJECT.md example
- Receipt includes pricing block with rule_applied

### Deliverables
- `gateway/app/pricing.py` + tests

---

## T-040 — x402 Payment Gating (402 Challenge Flow)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-030, T-010

### Description
Implement the payment gating flow:
- first call returns 402 with payment details
- second call includes payment authorization and proceeds

### Tasks
- Implement x402-related middleware / handler:
    - detect missing payment → respond 402
    - verify payment token/authorization on paid request
- For MVP, support a simplified local verification strategy if necessary, but align with x402 semantics.
- Document how to run the flow end-to-end.

### Acceptance Criteria
- Unpaid request returns 402
- Paid request succeeds
- Gateway logs include payment reference

### Deliverables
- `gateway/app/x402.py`
- `docs/DEMO.md` updated

---

## T-041 — Facilitator Service (Self-hosted Minimal)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-040

### Description
Provide a minimal facilitator-compatible module/service that:
- verifies payment artifacts
- coordinates calling the settlement contract
- abstracts chain submission from gateway

### Tasks
- Decide architecture:
    - Option A: facilitator is a library inside gateway
    - Option B: separate small service
- Implement chain client and settlement call wrapper
- Add retry logic and idempotency keys

### Acceptance Criteria
- Settlement tx submission works reliably
- Duplicate submissions do not create double settlements

### Deliverables
- `facilitator/` code + docs

---

## T-050 — Settlement Integration: Gateway → Contract
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-010, T-032, T-041

### Description
After receiving seller response and producing receipt, gateway must submit settlement to contract and return final result to buyer.

### Tasks
- Implement:
    - gateway signing of receipt hash
    - settlement tx call with parameters
- Store tx hash in receipt record
- Return response to buyer with:
    - request_id
    - payout/refund amounts
    - receipt_hash
    - tx reference

### Acceptance Criteria
- A complete call produces an on-chain settlement event
- Buyer receives response including tx hash and receipt id
- Receipts are retrievable via API

### Deliverables
- `gateway/app/settlement_client.py`
- integration tests (local chain or mocked)

---

## T-060 — Seller Service (Demo Endpoint)
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-000

### Description
Provide a demo seller endpoint to generate:
- fast valid output
- slow valid output
- invalid output (schema fail)

### Tasks
- Implement a simple seller service:
    - `POST /seller/call?mode=fast|slow|invalid`
    - returns deterministic JSON
- Add optional streaming simulation for TTFT testing

### Acceptance Criteria
- Modes reliably trigger different receipts:
    - fast valid → full payout
    - slow valid → partial bonus
    - invalid → zero payout

### Deliverables
- `gateway/demo_seller/` (or separate `seller/`)

---

## T-070 — Dashboard (Minimal, Must Show the Money)
**Status:** TODO  
**Priority:** P1  
**Depends on:** T-050

### Description
Create a dashboard that visualizes:
- request list
- metrics
- validation status
- payout/refund
- tx links / event references

### Tasks
- Implement a lightweight UI (Next.js or simple static + JS)
- Add gateway endpoint to list recent receipts:
    - `GET /v1/receipts?limit=…`
- Display scenario filters

### Acceptance Criteria
- Human-readable page shows the three demo scenarios
- Each row links to receipt JSON and tx hash

### Deliverables
- `dashboard/` + docs

---

## T-080 — Dispute UX & Resolver Script (MVP)
**Status:** TODO  
**Priority:** P1  
**Depends on:** T-011, T-070

### Description
Add minimal ability to open and resolve disputes for one example scenario.

### Tasks
- Add gateway endpoint:
    - `POST /v1/disputes/open`
- Add resolver script (CLI):
    - `resolve --request_id ... --final_payout ...`
- Update dashboard to show dispute state

### Acceptance Criteria
- Dispute can be opened and changes on-chain state
- Resolver can finalize and unblock withdrawal

### Deliverables
- CLI + endpoints + docs

---

## T-090 — End-to-End Demo Script
**Status:** TODO  
**Priority:** P0  
**Depends on:** T-050, T-060

### Description
Produce a repeatable script that runs the three scenarios in sequence and prints the outputs.

### Tasks
- Implement `scripts/run_demo.py` that:
    - calls gateway unpaid → expects 402
    - retries paid → obtains response
    - repeats for fast/slow/invalid
    - prints: request_id, metrics, payout, refund, tx hash
- Add a “one command demo” instruction in `docs/DEMO.md`

### Acceptance Criteria
- One command executes all scenarios reliably
- Outputs match expected payout mapping

### Deliverables
- `scripts/run_demo.py`
- `docs/DEMO.md`

---

## T-100 — Security Notes & Threat Model (Hackathon-ready)
**Status:** TODO  
**Priority:** P1  
**Depends on:** T-050, T-011

### Description
Document realistic security assumptions and what MVP does/does not protect against.

### Tasks
- Write `docs/SECURITY.md` including:
    - attestation trust model
    - replay protection
    - dispute griefing mitigations
    - what can be cheated (and how future work would improve)
- Add “assumptions” section in README

### Acceptance Criteria
- Security posture is explicit and defensible
- Known limitations are stated plainly

### Deliverables
- `docs/SECURITY.md`

---

## T-110 — Packaging & Submission Checklist
**Status:** TODO  
**Priority:** P0  
**Depends on:** All P0 tickets

### Description
Finalize what judges will see: clean docs, clean demo path, artifact links.

### Tasks
- Ensure README contains:
    - what it is
    - architecture diagram (ASCII ok)
    - how to run demo
- Provide:
    - contract addresses (or deployment instructions)
    - short pitch bullets for SKALE / Coinbase x402 / Google AP2
- Add `docs/SUBMISSION.md` with:
    - repo overview
    - demo steps
    - screenshots placeholders

### Acceptance Criteria
- A new developer can run the demo in ≤ 15 minutes
- Submission doc contains all required hackathon links/info

### Deliverables
- `docs/SUBMISSION.md` + README final pass

---

## Stretch Tickets (Optional)
### T-200 — Add SQL Test Harness Validator
**Status:** TODO  
**Priority:** P2  
**Depends on:** T-031, T-032

### T-210 — Receipt Indexing (SQLite) + Search
**Status:** TODO  
**Priority:** P2  
**Depends on:** T-050

### T-220 — Multi-attestation (Buyer + Seller + Gateway)
**Status:** TODO  
**Priority:** P2  
**Depends on:** T-020, T-010
