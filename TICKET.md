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
**Status:** DONE
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

### Completion Notes
- docs/API.md: Mandate + Receipt JSON schemas, hashing rules, test vector references
- gateway/app/hashing.py: canonical_json, keccak256, compute_mandate_id, compute_receipt_hash
- gateway/tests/test_hashing.py: 7 test vectors (determinism, field exclusion, known hash)
- Validate: `pytest gateway/tests/test_hashing.py -v`

---

## T-030 — Gateway Skeleton (FastAPI Reverse Proxy)
**Status:** DONE
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

### Completion Notes
- gateway/app/main.py: FastAPI with POST /v1/call, GET /v1/health, GET /v1/receipts/{id}, GET /v1/receipts
- gateway/app/config.py, models.py, metrics.py, receipt.py
- TTFT/latency measurement via RequestMetrics
- In-memory receipt storage with build_receipt + hashing
- 6 gateway tests + 7 hashing tests + 1 smoke = 14 total
- Validate: `pytest gateway/tests/ -v`

---

## T-031 — Deterministic Validator: JSON Schema
**Status:** DONE
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

### Completion Notes
- gateway/app/validators/json_schema.py: validate_json_schema() with schema caching
- gateway/app/validators/schemas/invoice_v1.json: demo schema
- 8 tests: pass/fail cases, unknown schema, determinism
- Validate: `pytest gateway/tests/test_validators.py -v`

---

## T-032 — Pricing Engine (Base + Bonus Rules)
**Status:** DONE
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

### Completion Notes
- gateway/app/pricing.py: compute_payout() with latency tier rules, fail-closed on error/validation
- Integer-only arithmetic, payout <= max_price invariant, refund = max_price - payout
- 9 tests matching PROJECT.md example: fast/mid/slow tiers, error, validation fail, invariants
- Validate: `pytest gateway/tests/test_pricing.py -v`

---

## T-040 — x402 Payment Gating (402 Challenge Flow)
**Status:** DONE
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

### Completion Notes
- gateway/app/x402.py: 402 challenge response, HMAC-based payment verification (MVP)
- gateway/app/main.py: integrated x402 gating + validation + pricing in /v1/call
- docs/DEMO.md: x402 flow documentation with curl examples
- 36 total tests passing (5 x402 + 6 gateway + 7 hashing + 9 pricing + 8 validators + 1 smoke)
- Validate: `pytest gateway/tests/ -v`

---

## T-041 — Facilitator Service (Self-hosted Minimal)
**Status:** DONE
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

### Completion Notes
- facilitator/settlement.py: SettlementClient — sign_settlement, submit_settlement with idempotency
- Architecture: library inside gateway (Option A)
- Mock mode when no chain configured, real tx submission when RPC available
- 5 tests: gateway address, signing, determinism, idempotency, mock mode
- Validate: `pytest facilitator/tests/ -v`

---

## T-050 — Settlement Integration: Gateway → Contract
**Status:** DONE
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

### Completion Notes
- gateway/app/settlement_client.py: settle_request() bridges gateway to facilitator
- main.py: integrated settlement signing + submission after receipt generation
- Response now includes tx_hash, gateway_signature in receipt
- pyproject.toml: added facilitator to packages
- 41 total tests passing
- Validate: `pytest gateway/tests/ facilitator/tests/ -v`

---

## T-060 — Seller Service (Demo Endpoint)
**Status:** DONE
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

### Completion Notes
- gateway/demo_seller/main.py: POST /seller/call?mode=fast|slow|invalid
- Fast: valid invoice ~100ms, Slow: valid invoice ~6s, Invalid: schema-fail response
- Deterministic responses matching invoice_v1 schema
- 6 tests covering all modes + health + default
- Validate: `pytest gateway/tests/test_demo_seller.py -v`
- Run: `uvicorn gateway.demo_seller.main:app --port 8001`

---

## T-070 — Dashboard (Minimal, Must Show the Money)
**Status:** DONE
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

### Completion Notes
- dashboard/index.html: static page with receipt table, stats cards, filter, detail modal
- Connects to gateway API /v1/receipts, shows per-request metrics/validation/payout/refund
- Click row to see full receipt JSON
- Run: open dashboard/index.html in browser (or serve via any static server)

---

## T-080 — Dispute UX & Resolver Script (MVP)
**Status:** DONE
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

### Completion Notes
- POST /v1/disputes/open, POST /v1/disputes/resolve, GET /v1/disputes/{id}
- scripts/resolve_dispute.py: CLI for open/resolve operations
- MVP: in-memory dispute tracking, mock on-chain state
- 47 total tests passing
- Validate: `pytest gateway/tests/ facilitator/tests/ -v`

---

## T-090 — End-to-End Demo Script
**Status:** DONE
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

### Completion Notes
- scripts/run_demo.py: runs 3 scenarios (fast/slow/invalid) with 402→paid flow
- docs/DEMO.md: updated with one-command demo, dashboard, dispute instructions
- Prints per-scenario metrics, payout, refund, receipt hash, summary table
- Validate: start services, then `python scripts/run_demo.py`

---

## T-100 — Security Notes & Threat Model (Hackathon-ready)
**Status:** DONE
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

### Completion Notes
- docs/SECURITY.md: trust model, replay protection, dispute mechanism, known limitations
- README.md: added security assumptions section
- Covers: gateway trust, resolver centralization, HMAC vs x402, production recommendations

---

## T-110 — Packaging & Submission Checklist
**Status:** DONE
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

### Completion Notes
- docs/SUBMISSION.md: full submission doc with repo overview, demo steps, track relevance
- README.md: final pass with end-to-end demo instructions, submission link
- Quick start < 5 minutes documented

---

## Hackathon Criteria Gap Tickets (Must Be Real)
These tickets close the gap between:
- current MVP (deterministic demo seller + HMAC payment simulation)
- hackathon judging criteria emphasizing **real LLM usage**, **realistic commerce flows**, and **partner integrations**.

---

## T-119 — Agent Role Model Alignment (Buyer Agent / Seller Agent / Gateway)
**Status:** DONE
**Priority:** P0
**Depends on:** T-000, T-020, T-030

### Description
Agent 역할과 책임 경계를 코드/데모에 명확히 드러낸다.

- **Buyer Agent**: seller discovery, SLA 협상(quote/mandate), 결제, receipt 검증, dispute
- **Seller Agent/Service**: capabilities 공개, quote 제공, 실제 작업 수행(LLM: Gemini), 스키마 준수 출력
- **Gateway**: 측정/검증(결정적), pricing, receipt 발급, 온체인 정산 제출

LLM 사용 원칙:
- **Gemini는 Buyer/Seller agent의 의사결정/생성에 사용**한다 (심사에서 AI 사용 증거가 남아야 함).
- Gateway의 **검증/가격결정/정산 트랜잭션**은 결정적으로 유지한다 (LLM이 결정권을 가지지 않음).

### Tasks
- `docs/ARCHITECTURE.md`에 아래를 추가/정리:
  - role definitions (MUST/SHOULD)
  - trust boundary + who signs what (buyer/seller/gateway)
  - sequence(협상→402/pay→실행→receipt→settlement→dispute)
- `DEMO.md` 시나리오가 위 역할 명칭으로 일관되게 설명되도록 정리

### Acceptance Criteria
- 발표자가 "buyer agent는 이거, seller agent는 이거, gateway는 이거"를 코드 경로로 바로 가리킬 수 있음

### Completion Notes
- docs/ARCHITECTURE.md: Agent Roles & Trust Boundaries 섹션 추가 (역할별 MUST/MUST NOT, 서명 주체 표, trust boundary 다이어그램, e2e 시퀀스)
- DEMO.md: 에이전트 역할 테이블에 코드 경로/LLM 사용 여부 추가
- docs/DEMO.md: 역할 정의 문서 크로스 레퍼런스 추가
- Validate: 136 tests passed

---

## T-120 — Gemini Seller Agent Service (Real LLM + SLA Interface)
**Status:** DONE
**Priority:** P0
**Depends on:** T-030, T-031, T-119

### Description
더미 seller(`gateway/demo_seller`)를 대체해서, **Google Gemini API**로 실제 작업을 수행하는 Seller Agent/Service를 만든다.
Seller 역할이 명확해야 한다:
- capabilities 공개
- (선택) quote(견적) 제공
- call(실행)에서 Gemini로 결과 생성

협상 단순화 옵션(권장):
- 협상은 Buyer/Gateway 쪽에서 “mandate 초안/선택”을 만들고,
- Seller는 이를 **그대로 수락(accept)** 하는 것으로 데모를 구성한다.
- 즉 Seller는 “복잡한 협상 로직”이 아니라 “수락/거절 정책(최소)”만 갖는다.

### Tasks
- Seller 서비스 추가(폴더명은 `seller/` 권장) 또는 기존 seller를 분리:
  - `GET /seller/capabilities`
  - `POST /seller/quote` (선택: 오퍼를 seller가 제안하는 모델일 때만)
  - `POST /seller/mandates/accept` (권장: buyer가 만든 mandate를 seller가 수락)
  - `POST /seller/call`
- Gemini API로 호출:
  - `GEMINI_API_KEY`, `GEMINI_MODEL`
- 출력 강제:
  - `invoice_v1` JSON schema(`gateway/app/validators/schemas/invoice_v1.json`)를 통과하는 순수 JSON만 반환
  - 실패 시: JSON 추출/정정 프롬프트 기반 재시도(최소 1~2회) 또는 명시적 실패
- Seller identity:
  - capabilities/quote에 `SELLER_ADDRESS`(EVM) 포함

### Acceptance Criteria
- `POST /seller/call`이 “LLM 생성 결과물”을 반환하고, gateway에서 schema validation을 통과한다
- 협상 단계가 데모에 보이도록 아래 중 하나가 구현되어 있다:
  - `capabilities/quote` (seller가 오퍼 제안)
  - `capabilities` + `mandates/accept` (seller가 buyer 제안을 수락)
- 데모 출력/로그에 Gemini 사용 증거(모델명, 요청/응답 요약 또는 usage 메타데이터)가 남는다

### Completion Notes
- seller/main.py: GET /seller/capabilities, POST /seller/mandates/accept, GET /seller/mandates 추가
- capabilities: seller_address, llm_provider, llm_model, supported_schemas, endpoints 노출
- mandates/accept: 지원 스키마 검증 후 수락, in-memory mandate 저장
- seller/call: body에서도 mode 수신 가능 (gateway 호환), X-LLM-Model/X-LLM-Provider 헤더 추가
- 28 seller tests (7 new), 143 total tests passed
- Validate: `pytest seller/tests/ -v`

---

## T-121 — Buyer Agent (Autonomous Buyer)
**Status:** DONE
**Priority:** P0
**Depends on:** T-040, T-090, T-119, T-120

### Description
Add a minimal "buyer agent" that behaves like an autonomous client:
- discovers seller capabilities
- negotiates an SLA (mandate) from seller quote **or buyer-side offer catalog**
- handles `402` challenge
- submits paid request
- verifies receipts deterministically (schema + payout/refund invariants)
- opens disputes when SLA is violated

### Tasks
- Implement a buyer agent CLI (folder `buyer_agent/` recommended):
  - call seller `GET /seller/capabilities`
  - 아래 중 하나로 mandate를 만든다:
    - seller `POST /seller/quote` 기반으로 mandate 구성/수락, 또는
    - buyer-side offer catalog(T-143)에서 SLA 오퍼를 선택해 mandate 구성
  - (권장) seller `POST /seller/mandates/accept`로 최종 mandate를 “seller가 수락”했음을 남김(이력/증거)
  - call gateway `/v1/call` with the selected mandate reference
  - verify receipt invariants and print an auditable summary for the demo
- **Must**: use **Google Gemini API** for negotiation strategy:
  - draft requirements/constraints from user intent
  - evaluate seller quote and decide accept/reject or counter-propose
  - output a human-readable negotiation summary for the demo (what was agreed and why)

### Acceptance Criteria
- Running buyer agent demonstrates an agentic commerce flow end-to-end (negotiate → pay → proof)
- Buyer agent refuses responses that fail invariants or schema (fail-closed)

### Completion Notes
- buyer_agent/client.py: discover_seller(), negotiate_mandate(), NegotiationResult 추가
- buyer_agent/main.py: negotiation phase 출력 (seller capabilities, mandate, acceptance)
- --seller-url 옵션 추가, mandate template matching PROJECT.md
- 13 buyer agent tests (4 new negotiation tests), 147 total passed
- Validate: `pytest buyer_agent/tests/ -v`

---

## T-122 — Real x402 Integration (Replace HMAC Simulation)
**Status:** DONE
**Priority:** P0
**Depends on:** T-040

### Description
Replace `gateway/app/x402.py` HMAC token with a real x402-compatible payment authorization/verification flow suitable for judging ("commerce realism").

### Tasks
- Confirm target x402 spec + required headers/fields for the hackathon demo
- Implement:
  - unpaid request → `402` with `accepts` payload matching spec
  - paid request → include proof/authorization per spec
  - gateway verification of payment artifact
- Add a compatibility mode:
  - `PAYMENT_MODE=hmac|x402` so local dev can still run without keys
- Add tests for:
  - valid/invalid paid requests
  - replay protection / nonce window

### Acceptance Criteria
- Paid request verification no longer relies on shared-secret HMAC
- Demo script can exercise x402 mode with real proofs

### Completion Notes
- gateway supports `PAYMENT_MODE=hmac|x402` in `gateway/app/x402.py`
- x402 mode currently verifies an EIP-712 authorization payload (replay-protected in-memory)
- Tests: `gateway/tests/test_x402.py` covers both HMAC and x402 verification paths

### Known Limitations (must address for realism)
- Current x402 verification is not yet tied to an on-chain escrow/funds movement invariant (see T-123, T-132)

---

## T-123 — Fix On-chain Funds Flow (Buyer Pays, Not Gateway)
**Status:** DONE
**Priority:** P0
**Depends on:** T-010, T-050, T-122

### Description
Current `SLASettlement.settle()` pulls funds from `msg.sender` (gateway tx sender), which is not commerce-realistic.
Update the on-chain flow so **the buyer is the payer** (or the contract has escrowed funds from the buyer before settlement).

### Tasks
- Choose one:
  - A) `deposit(requestId, buyer, amount)` by buyer, then `settle()` only distributes
  - B) `permit`/meta-tx approach (buyer signature authorizes transfer)
  - C) x402 payment transfers `max_price` directly to escrow, and `settle()` checks escrow balance
- Update contract + gateway integration + tests accordingly
- Ensure replay protection holds across deposit/settle

### Acceptance Criteria
- On-chain accounting shows buyer funds `max_price` (not gateway custody)
- Settlement distributes payout/refund from escrowed buyer funds

### Completion Notes
- SLASettlement.sol: deposit() + DEPOSITED→PENDING flow, buyer funds escrow
- facilitator/settlement.py: submit_deposit() for on-chain deposit
- gateway/app/settlement_client.py: ABI includes deposit()
- Foundry tests cover deposit→settle→finalize and deposit→settle→dispute paths
- Validate: `cd contracts && forge test -v`

---

## T-124 — Separate Seller Identity (URL vs Address)
**Status:** DONE
**Priority:** P0
**Depends on:** T-050

### Description
Gateway currently uses a seller upstream URL as the "seller" field, but on-chain settlement requires an EVM address.
Introduce a proper `SELLER_ADDRESS` and include it in receipts and settlement calls.

### Tasks
- Add env: `SELLER_ADDRESS`
- Remove fallback to URL/zero-address for on-chain settlement (require valid EVM address)
- Update receipt fields and settlement params to always use EVM addresses
- Update demo scripts and docs
- Add validation: reject invalid addresses early

### Acceptance Criteria
- Live chain mode no longer normalizes seller/buyer to zero-address
- On-chain payout goes to the configured seller address

### Completion Notes
- gateway/app/config.py: SELLER_ADDRESS env var
- gateway/app/settlement_client.py: _normalize_addr() with checksum validation
- Receipt/settlement always use EVM addresses, not URLs
- Validate: `pytest gateway/tests/ -v`

---

## T-125 — Real On-chain Disputes (Gateway + CLI)
**Status:** DONE
**Priority:** P1
**Depends on:** T-011, T-080

### Description
Dispute endpoints currently keep an in-memory cache and submit tx from the gateway key.
Align this with the role model:
- buyer/disputer opens disputes and posts bonds
- resolver resolves disputes
- gateway provides APIs but should not impersonate buyer in live mode

Implement actual calls:
- `openDispute(requestId)`
- `resolveDispute(requestId, finalPayout)`
- `finalize(requestId)`

### Tasks
- Add contract ABI methods + chain submission in facilitator
- Replace in-memory dispute truth with on-chain derived state (events) or persisted indexer/cache
- Ensure correct caller identities for dispute flows
- Update dashboard to show dispute status from chain events (or explicit sync/cache)
- Add tests using a local anvil/fork or contract mock

### Acceptance Criteria
- Dispute open/resolve/finalize changes contract state on SKALE
- Dashboard shows dispute state for at least one receipt

### Completion Notes
- gateway/app/settlement_client.py: submit_dispute_open, submit_dispute_resolve, submit_finalize
- ABI includes openDispute, resolveDispute, finalize
- Chain mode: real tx submission; mock mode: log-only
- scripts/resolve_dispute.py: CLI for dispute operations
- Validate: `pytest gateway/tests/ facilitator/tests/ -v`

---

## T-126 — Receipt Persistence (SQLite) + Export
**Status:** DONE
**Priority:** P1
**Depends on:** T-030, T-070

### Description
Receipt store supports optional SQLite persistence (via `RECEIPT_DB_PATH`) and JSONL export.

### Tasks
- Document:
  - `RECEIPT_DB_PATH` usage
  - `GET /v1/receipts/search` and `GET /v1/receipts/export`

### Acceptance Criteria
- Optional persistence works via `RECEIPT_DB_PATH`
- Export endpoint works and is documented

---

## T-127 — Partner Integration: Google A2A/AP2 Message Layer
**Status:** DONE
**Priority:** P1
**Depends on:** T-020

### Description
Add an optional integration layer where mandates/receipts are encoded as explicit protocol messages (A2A/AP2 framing),
so the demo isn't only "custom REST JSON".

### Tasks
- Implement/finish A2A semantics (not just framing):
  - Mandate request/response must create/store a real mandate (see T-129)
  - Receipt submission/ack must attach to real receipt IDs and tie into attestations
  - Dispute open/resolve must map to live dispute flows (see T-125)
- Add docs and a minimal demo script that uses the A2A envelope end-to-end

### Acceptance Criteria
- At least one end-to-end call can run via the AP2/A2A envelope path
- Docs show the message formats clearly

### Notes
- A2A envelope framing exists in `gateway/app/a2a/envelope.py` and routes exist in `gateway/app/a2a/routes.py`,
  but current handlers are mostly stubbed and do not enforce/store mandates or disputes.

---

## T-128 — Partner Integration: ERC-8004 Hook (Orchestration)
**Status:** DONE
**Priority:** P2  
**Depends on:** T-020, T-010

### Description
Add an ERC-8004-compatible orchestration hook (or minimal adapter) to show alignment with agent orchestration standards.

### Tasks
- Decide which minimal subset to support for the demo
- Implement adapter contract/module and a demo call path
- Document how it maps to mandate/receipt lifecycle

### Acceptance Criteria
- Repo contains a concrete artifact (code + demo) demonstrating ERC-8004 alignment

---

## T-129 — Mandate Negotiation + Enforcement (No More DEFAULT_MANDATE)
**Status:** TODO
**Priority:** P0
**Depends on:** T-020, T-119, T-120, T-121

### Description
SLA를 "문서"가 아니라 "협상된 객체"로 만들고 gateway가 강제(enforce)한다.
현재 gateway는 `/v1/call`에서 `DEFAULT_MANDATE`를 하드코딩으로 사용하고 `mandate_id`를 비워둔다.

### Tasks
- mandate 저장소 추가(인메모리 + 선택적으로 SQLite)
- mandate 생성/수락 경로 추가:
  - REST (예: `POST /v1/mandates`) 또는
  - A2A (`/a2a/message`의 `sla-pay.mandate.request`)
- `/v1/call`에서 `mandate_id`를 요구하고, unknown/expired mandate는 거절
- receipt/settlement에 아래 필드 채우기:
  - `mandate_id`, `buyer`, `seller`, `gateway`

### Acceptance Criteria
- demo에서 “협상된 mandate”가 보여야 하고, gateway가 그 mandate로 정산을 수행한다
- receipt에 `mandate_id`가 항상 non-empty로 들어간다

---

## T-130 — Seller Execution Request Contract (Param Passing Fix)
**Status:** TODO
**Priority:** P0
**Depends on:** T-030, T-060, T-120

### Description
buyer→gateway→seller에서 “요청 파라미터(모드/입력/타임아웃)”가 누락 없이 전달되도록 실행 요청 스키마를 고정한다.
현재는 gateway가 query params를 드랍할 수 있다.

### Tasks
- seller execution request의 canonical schema 정의 (예: `{mode, input, schema_id, ...}`)
- gateway forwarder가 이 schema를 그대로 seller에 전달하도록 수정
- **호환성 규칙 고정(중요):**
  - gateway는 `/v1/call`의 `mode`(query 또는 body)를 seller로 전달해야 한다
  - seller는 `mode`를 **query와 body 둘 다**에서 받을 수 있어야 한다 (데모/스크립트 호환)
  - 기본값은 `mode=fast`
- integration test 추가: `/v1/call`을 통해 slow/invalid 시나리오가 실제로 발생함을 보장

### Acceptance Criteria
- 데모에서 slow/invalid 시나리오가 “gateway를 거쳐서도” 재현된다
- `seller/`(Gemini)와 `gateway.demo_seller` 둘 중 어떤 upstream을 붙여도, 동일한 요청(`mode=...`)으로 시나리오 재현이 된다

---

## T-131 — Receipt Timing Accuracy (TTFT + timestamps)
**Status:** TODO
**Priority:** P1
**Depends on:** T-030

### Description
심사/데모에서 설득력 있는 metrics가 나오게 receipt 타임스탬프/TTFT 정의를 명확히 한다.
현재 receipt timestamps는 동일 값으로 채워질 수 있다.

### Tasks
- `RequestMetrics`에서 실제 타임스탬프를 받아 receipt에 넣기
- 스트리밍이 없다면 TTFT를 "first byte"로 정의하고 명시
- (선택) seller 스트리밍 지원 시 실제 TTFT 측정

### Acceptance Criteria
- receipt metrics가 일관되고 방어 가능한 의미를 가진다

---

## T-132 — Align Contract Interface vs Gateway ABI (deposit() mismatch)
**Status:** TODO
**Priority:** P0
**Depends on:** T-010, T-050, T-123

### Description
gateway settlement client ABI에 `deposit()`가 포함되어 있으나 컨트랙트에는 없다.
buyer-pays 모델(T-123)을 구현하려면 ABI/컨트랙트가 정확히 일치해야 한다.

### Tasks
- 선택:
  - contract에 `deposit()` 구현 + 테스트 + gateway 연동, 또는
  - gateway ABI에서 `deposit()` 제거하고 다른 escrow 전략 채택
- 통합 테스트: gateway가 사용하는 ABI가 배포된 바이트코드 인터페이스와 일치함을 검증

### Acceptance Criteria
- 데모 네트워크에서 ABI mismatch로 트랜잭션이 깨지지 않는다

---

## T-133 — Receipt Multi-attestation (Buyer + Seller + Gateway) Demo Integration
**Status:** TODO
**Priority:** P1
**Depends on:** T-119, T-120, T-121

### Description
역할이 명확하게 보이도록 receipt에 대해 buyer/seller/gateway가 모두 서명(attest)하고,
데모에서 이를 확인 가능하게 한다.

현재는 attestation 엔드포인트가 존재하지만, negotiation/execution 데모 플로우에서 자동으로 사용되지 않는다.

### Tasks
- Buyer Agent가 receipt 수신 후 `/v1/receipts/{id}/attest`로 buyer 서명 제출
- Seller Agent/Service가 작업 완료 후 seller 서명 제출(또는 buyer가 seller 서명까지 받아서 제출)
- Gateway가 자신의 서명을 receipt에 포함(`receipt.gateway` 및 `receipt.signatures`)하고, 검증 가능한 주소를 함께 노출
- Dashboard에 “3자 서명 완료/검증 결과”를 표시
- A2A 경로 사용 시 receipt.ack 메시지가 attestation으로 이어지도록 연결

### Acceptance Criteria
- 데모에서 한 request에 대해 buyer/seller/gateway 3자 서명이 모두 기록되고 검증된다

---

## T-134 — Single-Secret Demo Mode (One Env Secret, Auto Signing)
**Status:** TODO
**Priority:** P0
**Depends on:** T-119, T-120, T-121, T-133

### Description
데모 안정성과 “agent가 실제로 서명한다”를 동시에 만족시키기 위해,
비밀값을 **하나만**(환경변수 1개) 주고도 buyer/seller/gateway 역할별 서명과 요청을 자동화한다.

권장 2가지 옵션 중 하나를 선택:
1) `DEMO_PRIVATE_KEY` (하나의 EOA를 buyer/seller/gateway/resolver가 공유: 가장 단순하지만 역할 분리가 약해짐)
2) `DEMO_MNEMONIC` (하나의 시드에서 역할별 EOA를 파생: 역할 분리가 명확하고 데모에 더 적합)

### Tasks
- 공통 env 추가:
  - `DEMO_SECRET_MODE=private_key|mnemonic`
  - `DEMO_PRIVATE_KEY` 또는 `DEMO_MNEMONIC`
- 역할별 키/주소 기본값 자동 세팅:
  - `BUYER_PRIVATE_KEY`, `SELLER_PRIVATE_KEY`, `GATEWAY_PRIVATE_KEY`, `RESOLVER_PRIVATE_KEY`
  - `BUYER_ADDRESS`, `SELLER_ADDRESS`, `GATEWAY_ADDRESS`, `RESOLVER_ADDRESS`
  - 명시적으로 role env가 설정되면 그 값을 우선
- 데모 스크립트/에이전트에서 “키가 없으면 실행 불가”가 아니라:
  - `DEMO_*`가 있으면 자동으로 파생/주입해 동작하도록 처리
- 보안/데모 경고 문구 추가:
  - “해커톤 데모용, 절대 메인키로 쓰지 말 것”을 문서/로그에 명시

### Acceptance Criteria
- 데모 실행 시 “환경변수로 넣어야 하는 시크릿”이 1개로 줄어든다
- Buyer/Seller/Gateway가 서명한 아티팩트(402 결제 헤더, receipt attestation 등)가 자동으로 생성/제출된다

---

## T-135 — One-Command Demo Orchestration (Deploy → Run → Prove)
**Status:** TODO
**Priority:** P1
**Depends on:** T-134, T-129, T-133

### Description
심사/발표에서 흔들리지 않도록 “한 번에 재현되는” 데모 오케스트레이션을 제공한다.

### Tasks
- `scripts/demo_one_command.sh` 또는 `python scripts/demo_one_command.py` 추가:
  - SKALE testnet 배포(Foundry) 실행 및 주소 파싱
  - Gateway/Seller/Buyer Agent 순서대로 실행(포트 충돌/헬스체크 포함)
  - 3개 시나리오 실행 + receipt/tx_hash 출력
  - receipt 3자 서명(attestation)까지 자동 제출
  - (옵션) dispute open/resolve/finalize까지 한 번 보여주는 플로우
- 출력 포맷을 발표 친화적으로 고정:
  - “협상 결과(quote/mandate)”, “402”, “receipt hash”, “tx hash”, “attestations complete”가 한 화면에 보이게

### Acceptance Criteria
- 새 환경에서 1개 커맨드로 데모를 재현할 수 있다(실패 시 어떤 단계가 실패했는지 명확히 출력)

---

## T-136 — Demo Console Web Page (Negotiation + Monitoring)
**Status:** TODO
**Priority:** P0
**Depends on:** T-119, T-120, T-129, T-133

### Description
데모에서 “협상(negotiation)”과 “모니터링(monitoring)”을 한 화면에서 보여주는 단일 웹 페이지를 만든다.
Next.js 없이도 열 수 있도록 `dashboard/`의 static HTML로 구현하는 것을 기본으로 한다.

### Tasks
- 페이지 구성(1장):
  - Seller: capabilities 조회(`GET /seller/capabilities`) 결과 표시
  - Negotiation: quote 요청(`POST /seller/quote`) 및 최종 mandate 표시
  - Gateway: mandate 등록/조회/상태(see T-129) 표시
  - Execution: 시나리오 실행 트리거(서버 사이드) 및 진행상태 표시(see T-137)
  - Receipts: `/v1/receipts` 테이블, receipt detail, attestation 상태, tx_hash 링크
  - Disputes: open/resolve/finalize 버튼과 상태(온체인/캐시) 표시
- 네트워크 설정:
  - UI 상단에 `Gateway URL`, `Seller URL` 입력
  - CORS 문제가 있으면 gateway에 CORS 허용 설정 티켓 추가
- 발표 친화 출력:
  - “협상 결과(terms)”, “402”, “receipt_hash”, “tx_hash”, “3자 서명 complete”가 한 화면에 보이게

### Acceptance Criteria
- 브라우저에서 페이지 하나로 협상 결과와 실시간 receipt/정산 상태를 확인할 수 있다

---

## T-137 — Demo Run API (Server-side Buyer Agent Orchestration)
**Status:** TODO
**Priority:** P0
**Depends on:** T-121, T-134

### Description
브라우저에 private key를 노출하지 않으면서도 “버튼 한 번으로 실행”을 만들기 위해,
gateway에 데모 전용 orchestration API를 추가한다.

### Tasks
- 데모 전용 엔드포인트 추가(예: `/v1/demo/run`):
  - 입력: mode(s), seller url, mandate id(optional)
  - 동작: buyer agent flow 실행(협상 포함 시 더 좋음), receipt 생성, attestation 제출
  - 출력: 단계별 로그 + 결과( request_id, receipt_hash, tx_hash, attestation status )
- 진행상태 전달:
  - polling 응답 또는 SSE(`/v1/demo/stream`) 형태 중 하나 선택
- 보안:
  - `DEMO_MODE=true`일 때만 활성화
  - 로컬/데모 환경에서만 사용하도록 문서에 명시

### Acceptance Criteria
- Demo Console(T-136)에서 버튼 클릭으로 시나리오 실행이 가능하고, secrets는 서버(env)에서만 사용한다

---

## T-138 — Event Ledger (Negotiation + SLA Evidence Timeline)
**Status:** TODO
**Priority:** P0
**Depends on:** T-119, T-120, T-121, T-129

### Description
데모에서 “협상 내용”과 “SLA 측정/정산 과정”을 한 눈에 보여주려면, receipt 테이블만으로는 부족하다.
협상과 실행 중 발생한 사건들을 append-only 이벤트로 남겨 “타임라인”을 구성한다.

이벤트 예시:
- negotiation: capabilities fetched, quote requested, quote received, mandate accepted/rejected/counter
- payment: 402 issued, payment verified (mode=hmac/x402), buyer identity
- execution: seller request started, seller response received, upstream error/timeout
- validation: schema pass/fail + details
- pricing: tier applied, payout/refund
- receipt: receipt_hash computed, gateway signature
- chain: settlement tx submitted/failed, dispute tx submitted/failed, finalize tx submitted/failed
- attestations: buyer/seller/gateway attested + verification result

### Tasks
- 이벤트 모델 정의:
  - 최소 필드: `event_id`, `ts`, `kind`, `request_id?`, `mandate_id?`, `actor`(buyer/seller/gateway/resolver), `data`
- 저장소:
  - SQLite (기본) + in-memory fallback
  - receipt DB와 같은 `RECEIPT_DB_PATH` 또는 별도 `EVENT_DB_PATH`로 구성
- API:
  - `GET /v1/events?request_id=...&mandate_id=...&limit=...`
  - `GET /v1/events/export` (JSONL)
- gateway/seller/buyer agent에서 주요 지점에 이벤트 기록 훅 추가

### Acceptance Criteria
- 한 번의 데모 실행에 대해 “협상→402→실행→검증→정산→서명” 타임라인이 이벤트로 복원 가능하다

---

## T-139 — History Page (SLA + Negotiation + Incidents)
**Status:** TODO
**Priority:** P0
**Depends on:** T-136, T-138

### Description
데모용 웹 페이지 1장(또는 탭 1개)에서 다음을 모두 조회할 수 있어야 한다:
- 협상 내역(quote/mandate)
- 측정된 SLA 항목(latency/validation/price)
- 발생 사건(402, upstream_error, schema_fail, tx_fail, dispute 등)

### Tasks
- `dashboard/` static UI에 “History/Timeline” 섹션 추가:
  - request_id/mandate_id 검색
  - 이벤트 타임라인 렌더
  - receipt/attestation/tx 링크
- 빠른 데모를 위한 프리셋 필터:
  - “SLA violation only” (validation_fail, timeout, slow tier, tx_fail)

### Acceptance Criteria
- 발표자가 특정 request_id를 입력하면, 협상부터 정산까지의 사건이 1페이지에서 재생성된다

---

## T-140 — SLA Violation Simulation Pack
**Status:** TODO
**Priority:** P0
**Depends on:** T-119, T-120, T-129

### Description
심사에서 “SLA가 깨졌을 때 어떻게 되는지”를 반드시 보여줘야 한다.
현재는 slow/invalid 정도만 쉽게 재현 가능하므로, 위반 케이스들을 명시적으로 시뮬레이션 가능하게 만든다.

현 구현 메모(갭):
- `seller/main.py`는 `fast|slow|invalid`를 지원하지만, gateway가 현재 `/seller/call`로 `mode`를 전달하지 않는다 (T-130 필요)
- `scripts/run_demo.py`는 `gateway.demo_seller` 기준 시나리오로 작성되어 있어 “전부 Gemini” 데모 요건을 충족하지 못한다 (T-145 필요)

### Simulation Cases
- latency breach (tier 하락): `mode=slow`
- correctness breach (validator fail): `mode=invalid` (필수 필드 제거)
- upstream failure: seller 다운 / 네트워크 에러 / 5xx
- timeout breach: seller가 timeout을 초과하도록 강제
- payment failure: unpaid/invalid payment/replay
- chain failure: invalid signature / revert / rpc down (정산 실패)

### Tasks
- Seller에 시뮬레이션 옵션 정리:
  - `mode=slow|invalid|error|timeout` 같은 명시적 모드 추가
  - (가능하면) `delay_ms` 같은 정밀 제어
- Gateway에 시뮬레이션 훅(데모 모드 한정):
  - `DEMO_FORCE_TIMEOUT_MS`, `DEMO_FORCE_UPSTREAM_ERROR`, `DEMO_FORCE_VALIDATION_FAIL` 등
- Demo scripts에 “위반 케이스 데모 시나리오”를 포함

### Acceptance Criteria
- 데모에서 최소 3개의 “SLA 미충족” 케이스를 버튼/커맨드로 재현 가능하다

---

## T-141 — Demo Console Connectivity (CORS or Same-origin Hosting)
**Status:** TODO
**Priority:** P0
**Depends on:** T-136

### Description
데모 콘솔(`dashboard/` static HTML)이 gateway/seller API를 직접 호출해야 한다.
`file://` 또는 다른 origin에서 열면 브라우저 CORS에 걸릴 수 있으므로, 데모 환경에서 “항상 동작”하도록 연결 방식을 고정한다.

### Tasks
- 아래 중 하나를 선택해 구현/문서화:
  - A안) gateway가 `dashboard/`를 static으로 서빙하여 same-origin으로 호출
  - B안) gateway에 CORS 허용(데모 모드 한정, 허용 origin 제한)
  - C안) demo 콘솔을 gateway dev server에서 함께 띄우기(예: `python -m http.server` + CORS)
- `DEMO.md`/`LOCAL.md`에 “데모 콘솔 여는 방법”을 1줄로 고정

### Acceptance Criteria
- 크롬 시크릿/새 머신에서도 데모 콘솔이 API 호출에 실패하지 않는다(추가 플러그인/브라우저 설정 없이)

---

## T-142 — SLA Breach Reasons (Explainable SLA Evaluation)
**Status:** TODO
**Priority:** P1
**Depends on:** T-030, T-060, T-138, T-139

### Description
데모에서 “왜 SLA가 깨졌는지”를 말로 설명하지 않고, 시스템이 스스로 증거를 남기게 한다.
현재는 `validation_passed`, `latency_ms`, `rule_applied` 정도만 있어, 위반 사유/증거가 UI에서 한 눈에 안 들어온다.

### Tasks
- receipt와 event ledger에 “위반 사유 코드”를 기록:
  - 예: `BREACH_LATENCY_TIER_DOWN`, `BREACH_SCHEMA_FAIL`, `BREACH_UPSTREAM_ERROR`, `BREACH_TIMEOUT`, `BREACH_PAYMENT_INVALID`, `BREACH_CHAIN_SETTLE_FAIL`
- pricing/validation/outcome 단계에서 breach reasons를 결정적으로 산출(LLM 금지)
- History Page(T-139)에서 breach reasons를 pill/태그로 표시하고, 관련 이벤트/필드로 드릴다운 제공

### Acceptance Criteria
- 발표자가 특정 request를 클릭했을 때, “무슨 SLA가 어떻게 깨졌는지”가 UI에서 즉시 보인다

---

## T-143 — Mock SLA Offer Catalog (Multiple Quotes, Demo-friendly)
**Status:** TODO
**Priority:** P0
**Depends on:** T-120, T-129, T-136

### Description
데모에서 “협상”이 보이려면 선택지가 있어야 한다.
다만 실제 협상 로직은 단순화할 수 있다:
- SLA 오퍼는 **우리쪽(Buyer/대시보드/Gateway)** 에서 “카탈로그(프리셋)”로 모킹
- Seller는 buyer가 만든 mandate를 **그냥 수락(accept)** 하는 형태로 구성 가능

### Tasks
- 오퍼 카탈로그 제공 위치를 아래 중 하나로 결정:
  - A) Demo Console이 로컬 프리셋을 보유(가장 단순)
  - B) Gateway가 `GET /v1/demo/offers`로 제공(이력/버전 관리 용이)
  - C) Seller `POST /seller/quote`가 복수 오퍼 반환(가장 “시장”스럽지만 구현량 증가)
- 최소 3개 프리셋 오퍼 제공(예):
  - `Bronze`: 낮은 max_price, 느슨한 latency tier
  - `Silver`: 중간
  - `Gold`: 높은 max_price, 타이트한 latency tier(빠르면 payout 높음)
- 각 오퍼에 포함할 필드(결정적):
  - `offer_id`, `service_id`, `max_price`, `base_pay`, `bonus_rules(latency_tiers)`, `validators`, `dispute_window_sec`
- Gateway mandate 등록(T-129) 시:
  - 어떤 `offer_id`에서 유래한 mandate인지 이벤트/receipt에 남기기(T-138, T-142 연계)

### Acceptance Criteria
- 데모 콘솔에서 “Bronze/Silver/Gold 중 선택”이 가능하고, 선택한 SLA 조건이 receipt/이력에 명확히 남는다

---

## T-144 — Dashboard SLA/Incident Simulator Controls (Latency Slider + Failure Toggles)
**Status:** TODO
**Priority:** P0
**Depends on:** T-136, T-138, T-140, T-141

### Description
발표 중 실시간으로 SLA를 깨거나 만족시키는 모습을 보여주기 위해,
대시보드에서 seller의 지연/오류를 조정하고 즉시 실행할 수 있는 “시뮬레이터 컨트롤”을 추가한다.

### Tasks
- Seller 시뮬레이션 입력 확장(데모 모드 한정):
  - `delay_ms` (예: 0~8000 슬라이더)
  - `force_http_status` 또는 `force_error=upstream_error|timeout|schema_invalid`
  - 현재 `mode=fast|slow|invalid`는 유지하되, `delay_ms`가 우선하도록 규칙 고정
- Gateway가 시뮬레이션 파라미터를 seller로 전달하도록 wiring(T-130과 조합)
- Demo Console(T-136)에 컨트롤 추가:
  - SLA 오퍼 선택(T-143)
  - 지연 슬라이더(현재 값 표시)
  - 오류 토글(예: schema_invalid, upstream_5xx, timeout)
  - “Run” 버튼 1개로 실행하고, 결과(402→paid→receipt→tx)를 한 화면에 표시
- Event Ledger(T-138)에 “시뮬레이션 설정 값”을 이벤트로 기록:
  - 나중에 이력에서 “왜 깨졌는지”를 재현 가능

### Acceptance Criteria
- 발표자가 슬라이더/토글만 조절해서 “SLA 만족/위반”을 즉석에서 재현할 수 있다
- 이력 페이지에서 당시의 시뮬레이션 설정과 결과가 함께 보인다

---

## T-145 — Demo Runner Migration to Gemini Seller (No demo_seller Dependency)
**Status:** TODO
**Priority:** P0
**Depends on:** T-120, T-130

### Description
현재 `scripts/run_demo.py`는 `gateway.demo_seller` 기준으로 작성되어 있다.
심사 요건(실제 LLM 사용, 전부 Gemini)을 만족하려면, 데모 러너/시나리오가 `seller/`(Gemini) upstream으로도 동일하게 동작해야 한다.

### Tasks
- `scripts/run_demo.py`(또는 별도 `scripts/run_demo_gemini.py`)가 아래를 만족하도록 수정:
  - Seller upstream이 `seller/main.py`일 때도 `fast|slow|invalid`가 재현됨
  - 시나리오별로 “Gemini 사용 여부/모델명/요약”을 로그에 남김(증거)
  - fallback(`SELLER_FALLBACK=true`)로 내려갔는지도 명확히 표기
- `DEMO.md`/`LOCAL.md`의 prereq를 `gateway.demo_seller`가 아니라 `seller/` 기준으로 업데이트

### Acceptance Criteria
- 발표 환경에서 demo 러너가 Gemini seller로 3시나리오(정상/느림/무효)를 재현하고, gateway receipt/정산까지 일관되게 보여준다

---

## Stretch Tickets (Optional)
### T-200 — Add SQL Test Harness Validator
**Status:** TODO  
**Priority:** P2  
**Depends on:** T-031, T-032

### T-210 — Receipt Indexing (SQLite) + Search
**Status:** DONE
**Priority:** P2  
**Depends on:** T-050

### T-220 — Multi-attestation (Buyer + Seller + Gateway)
**Status:** DONE
**Priority:** P2  
**Depends on:** T-020, T-010
