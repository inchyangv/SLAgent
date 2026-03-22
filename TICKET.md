# SLAgent-402 — Execution Tickets
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

# Completed Milestones (M0–M4 + Track Add-ons)

아래 티켓들은 모두 **DONE**. 상세 내용은 `git log`과 각 파일에서 확인.

## M0 — Foundation

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-000 | Repo Bootstrap & Standards | contracts/, gateway/, dashboard/, CI, pyproject.toml |
| T-001 | Choose Chain + Token Strategy | SKALE Sepolia, SLAT ERC20 (6 decimals) |

## M1 — Core Contracts

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-010 | Settlement Contract (Split + Refund) | contracts/src/SLASettlement.sol, 9 tests |
| T-011 | Dispute Contract (Escrow + Delay) | PENDING→DISPUTED→FINALIZED, 18 tests |

## M1.5 — Schemas & Gateway

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-020 | SLA Mandate & Receipt Schemas | docs/API.md, gateway/app/hashing.py, 7 test vectors |
| T-030 | Gateway Skeleton (FastAPI) | /v1/call, /v1/health, /v1/receipts, TTFT/latency |
| T-031 | Deterministic Validator: JSON Schema | validators/json_schema.py, invoice_v1, 8 tests |
| T-032 | Pricing Engine (Base + Bonus) | gateway/app/pricing.py, latency tiers |

## M2 — Payment & Settlement Integration

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-040 | x402 Payment Gating | 402 challenge flow |
| T-041 | Facilitator Service (Self-hosted) | facilitator/settlement.py |
| T-050 | Settlement Integration: Gateway → Contract | gateway/app/settlement_client.py |

## M3 — Demo & Polish

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-060 | Seller Service (Demo Endpoint) | seller/main.py, fast/slow/invalid |
| T-070 | Dashboard (Minimal) | dashboard/ React app |
| T-080 | Dispute UX & Resolver Script | scripts/resolve_dispute.py |
| T-090 | End-to-End Demo Script | scripts/run_demo.py, 3 scenarios |
| T-100 | Security Notes & Threat Model | docs/SECURITY.md |
| T-110 | Packaging & Submission Checklist | DORAHACKS.md |

## M4 — Agent Architecture & Real Integration

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-119 | Agent Role Model Alignment | buyer_agent/, seller/, gateway roles |
| T-120 | Gemini Seller Agent Service | seller/main.py (Gemini LLM) |
| T-121 | Buyer Agent (Autonomous) | buyer_agent/client.py |
| T-122 | Real x402 Integration | HMAC → real x402 |
| T-123 | Fix On-chain Funds Flow | Buyer pays, not gateway |
| T-124 | Separate Seller Identity | URL vs address split |
| T-125 | Real On-chain Disputes | gateway + CLI dispute |
| T-126 | Receipt Persistence (SQLite) | receipt DB |
| T-127 | Google A2A/AP2 Message Layer | A2A envelope support |
| T-128 | ERC-8004 Hook | orchestration hook |
| T-129 | Mandate Negotiation + Enforcement | quote → accept → mandate |
| T-130 | Seller Execution Request Contract | param passing fix |
| T-131 | Receipt Timing Accuracy | TTFT + timestamps |
| T-132 | Align Contract Interface vs Gateway ABI | deposit() mismatch fix |

## Track Add-ons (DONE)

| Ticket | Title | Key Artifacts |
|--------|-------|---------------|
| T-146 | x402 Agentic Tool Chain | buyer_agent/tools.py, wdk_wallet.py, 2+ paid steps |
| T-147 | AP2 Intent → Authorization → Settlement | A2A/AP2 envelopes, auth failure demo |
| T-148 | BITE v2 Encrypted Conditional Settlement | gateway/app/bite_v2.py, AES-GCM |

## Stretch (DONE)

| Ticket | Title |
|--------|-------|
| T-210 | Receipt Indexing (SQLite) + Search |
| T-220 | Multi-attestation (Buyer + Seller + Gateway) |

---

# Milestone 5 — Demo Console & Simulation

해커톤 심사용 데모 콘솔, 시뮬레이션, 발표 UX 완성.

---

## T-133 — Receipt Multi-attestation (Buyer + Seller + Gateway) Demo Integration
**Status:** DONE
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
- Dashboard에 "3자 서명 완료/검증 결과"를 표시
- A2A 경로 사용 시 receipt.ack 메시지가 attestation으로 이어지도록 연결

### Acceptance Criteria
- [ ] 데모에서 한 request에 대해 buyer/seller/gateway 3자 서명이 모두 기록되고 검증된다

### Commit Message
`feat(receipt): integrate buyer/seller/gateway multi-attestation into demo flow`

---

## T-134 — Single-Secret Demo Mode (One Env Secret, Auto Signing)
**Status:** DONE
**Priority:** P0
**Depends on:** T-119, T-120, T-121, T-133

### Description
데모 안정성과 "agent가 실제로 서명한다"를 동시에 만족시키기 위해,
비밀값을 **하나만**(환경변수 1개) 주고도 buyer/seller/gateway 역할별 서명과 요청을 자동화한다.

권장: `DEMO_MNEMONIC` (하나의 시드에서 역할별 EOA를 파생: 역할 분리가 명확하고 데모에 더 적합)

### Tasks
- 공통 env 추가:
  - `DEMO_SECRET_MODE=private_key|mnemonic`
  - `DEMO_PRIVATE_KEY` 또는 `DEMO_MNEMONIC`
- 역할별 키/주소 기본값 자동 세팅:
  - `BUYER_PRIVATE_KEY`, `SELLER_PRIVATE_KEY`, `GATEWAY_PRIVATE_KEY`, `RESOLVER_PRIVATE_KEY`
  - `BUYER_ADDRESS`, `SELLER_ADDRESS`, `GATEWAY_ADDRESS`, `RESOLVER_ADDRESS`
  - 명시적으로 role env가 설정되면 그 값을 우선
- 데모 스크립트/에이전트에서 `DEMO_*`가 있으면 자동으로 파생/주입해 동작
- 보안/데모 경고 문구: "해커톤 데모용, 절대 메인키로 쓰지 말 것"

### Acceptance Criteria
- [ ] 데모 실행 시 환경변수 시크릿이 1개로 줄어든다
- [ ] Buyer/Seller/Gateway가 서명한 아티팩트가 자동으로 생성/제출된다

### Commit Message
`feat(demo): single-secret mode with auto role-key derivation`

---

## T-135 — One-Command Demo Orchestration (Deploy → Run → Prove)
**Status:** DONE
**Priority:** P1
**Depends on:** T-134, T-129, T-133

### Description
심사/발표에서 흔들리지 않도록 "한 번에 재현되는" 데모 오케스트레이션을 제공한다.

### Tasks
- `scripts/demo_one_command.sh` 또는 `python scripts/demo_one_command.py`:
  - SKALE Sepolia 배포(Foundry) + 주소 파싱
  - Gateway/Seller/Buyer Agent 순서대로 실행 (포트 충돌/헬스체크)
  - 3개 시나리오 실행 + receipt/tx_hash 출력
  - receipt 3자 서명(attestation)까지 자동 제출
  - (옵션) dispute open/resolve/finalize 플로우
- 출력 포맷을 발표 친화적으로 고정

### Acceptance Criteria
- [ ] 새 환경에서 1개 커맨드로 데모 재현 가능 (실패 시 단계 명확히 출력)

### Commit Message
`feat(demo): one-command orchestration script`

---

## T-136 — Demo Console Web Page (Negotiation + Monitoring)
**Status:** DONE
**Priority:** P0
**Depends on:** T-119, T-120, T-129, T-133

### Description
데모에서 "협상(negotiation)"과 "모니터링(monitoring)"을 한 화면에서 보여주는 단일 웹 페이지.

### Tasks
- 페이지 구성(1장):
  - Seller: capabilities 조회 결과
  - Negotiation: quote 요청 및 최종 mandate
  - Gateway: mandate 등록/조회/상태
  - Execution: 시나리오 실행 트리거 + 진행상태
  - Receipts: 테이블, detail, attestation 상태, tx_hash 링크
  - Disputes: open/resolve/finalize 버튼과 상태
- 네트워크 설정: UI 상단에 Gateway URL, Seller URL 입력
- 발표 친화 출력

### Acceptance Criteria
- [ ] 브라우저에서 페이지 하나로 협상 결과와 실시간 receipt/정산 상태 확인 가능

### Commit Message
`feat(dashboard): demo console with negotiation + monitoring`

---

## T-137 — Demo Run API (Server-side Buyer Agent Orchestration)
**Status:** DONE
**Priority:** P0
**Depends on:** T-121, T-134

### Description
브라우저에 private key를 노출하지 않으면서도 "버튼 한 번으로 실행"을 위해
gateway에 데모 전용 orchestration API를 추가한다.

### Tasks
- `/v1/demo/run` 엔드포인트:
  - 입력: mode(s), seller url, mandate id(optional)
  - 동작: buyer agent flow 실행, receipt 생성, attestation 제출
  - 출력: 단계별 로그 + 결과
- 진행상태: polling 또는 SSE(`/v1/demo/stream`)
- 보안: `DEMO_MODE=true`일 때만 활성화

### Acceptance Criteria
- [ ] Demo Console에서 버튼 클릭으로 시나리오 실행, secrets는 서버(env)에서만 사용

### Commit Message
`feat(gateway): add demo run API for browser-triggered scenarios`

---

## T-138 — Event Ledger (Negotiation + SLA Evidence Timeline)
**Status:** DONE
**Priority:** P0
**Depends on:** T-119, T-120, T-121, T-129

### Description
협상과 실행 중 발생한 사건들을 append-only 이벤트로 남겨 "타임라인"을 구성한다.

이벤트 종류:
- negotiation: capabilities, quote, mandate accept/reject
- payment: 402, payment verified
- execution: seller request/response, error/timeout
- validation: schema pass/fail
- pricing: tier applied, payout/refund
- receipt: receipt_hash, gateway signature
- chain: settlement/dispute/finalize tx
- attestations: buyer/seller/gateway attested

### Tasks
- 이벤트 모델: `event_id`, `ts`, `kind`, `request_id?`, `mandate_id?`, `actor`, `data`
- 저장소: SQLite (기본) + in-memory fallback
- API: `GET /v1/events?request_id=...&mandate_id=...&limit=...`, `GET /v1/events/export` (JSONL)
- gateway/seller/buyer agent에 이벤트 기록 훅 추가

### Acceptance Criteria
- [ ] 한 번의 데모 실행에 대해 협상→402→실행→검증→정산→서명 타임라인이 이벤트로 복원 가능

### Commit Message
`feat(gateway): add event ledger for negotiation and SLA timeline`

---

## T-139 — History Page (SLA + Negotiation + Incidents)
**Status:** DONE
**Priority:** P0
**Depends on:** T-136, T-138

### Description
데모 웹 페이지에서 협상 내역, SLA 항목, 발생 사건을 한 눈에 조회.

### Tasks
- `dashboard/`에 "History/Timeline" 섹션:
  - request_id/mandate_id 검색
  - 이벤트 타임라인 렌더
  - receipt/attestation/tx 링크
- 프리셋 필터: "SLA violation only"

### Acceptance Criteria
- [ ] 특정 request_id 입력 시, 협상부터 정산까지 1페이지에서 재생

### Commit Message
`feat(dashboard): add history page with SLA timeline`

---

## T-140 — SLA Violation Simulation Pack
**Status:** DONE
**Priority:** P0
**Depends on:** T-119, T-120, T-129

### Description
심사에서 "SLA가 깨졌을 때"를 반드시 보여줘야 한다. 위반 케이스를 명시적으로 시뮬레이션.

### Simulation Cases
- latency breach (tier 하락): `mode=slow`
- correctness breach (validator fail): `mode=invalid`
- upstream failure: seller 다운 / 5xx
- timeout breach: seller timeout 초과
- payment failure: unpaid/invalid/replay
- chain failure: invalid sig / revert / rpc down

### Tasks
- Seller에 `mode=slow|invalid|error|timeout` + `delay_ms` 정밀 제어
- Gateway에 시뮬레이션 훅(데모 모드 한정): `DEMO_FORCE_*` 환경변수
- Demo scripts에 위반 케이스 시나리오 포함

### Acceptance Criteria
- [ ] 최소 3개의 SLA 미충족 케이스를 버튼/커맨드로 재현 가능

### Commit Message
`feat(demo): add SLA violation simulation pack`

---

## T-141 — Demo Console Connectivity (CORS or Same-origin Hosting)
**Status:** DONE
**Priority:** P0
**Depends on:** T-136

### Description
데모 콘솔이 gateway/seller API를 호출할 때 CORS에 걸리지 않도록 연결 방식 고정.

### Tasks
- 아래 중 하나:
  - A) gateway가 dashboard/를 static 서빙 (same-origin)
  - B) gateway에 CORS 허용 (데모 모드 한정)
  - C) demo 콘솔을 gateway dev server에서 함께 서빙
- DEMO.md/LOCAL.md에 "데모 콘솔 여는 방법" 1줄 고정

### Acceptance Criteria
- [ ] 크롬 시크릿/새 머신에서도 데모 콘솔이 API 호출 실패 없이 동작

### Commit Message
`fix(gateway): resolve CORS for demo console connectivity`

---

## T-142 — SLA Breach Reasons (Explainable SLA Evaluation)
**Status:** DONE
**Priority:** P1
**Depends on:** T-030, T-060, T-138, T-139

### Description
"왜 SLA가 깨졌는지"를 시스템이 증거로 남기도록. 위반 사유 코드를 receipt/event에 기록.

### Tasks
- receipt와 event ledger에 위반 사유 코드 기록:
  - `BREACH_LATENCY_TIER_DOWN`, `BREACH_SCHEMA_FAIL`, `BREACH_UPSTREAM_ERROR`, `BREACH_TIMEOUT`, `BREACH_PAYMENT_INVALID`, `BREACH_CHAIN_SETTLE_FAIL`
- pricing/validation/outcome 단계에서 breach reasons를 결정적으로 산출 (LLM 금지)
- History Page에서 breach reasons를 pill/태그로 표시 + 드릴다운

### Acceptance Criteria
- [ ] 특정 request 클릭 시, "무슨 SLA가 어떻게 깨졌는지" UI에서 즉시 확인

### Commit Message
`feat(gateway): add explainable SLA breach reason codes`

---

## T-143 — Mock SLA Offer Catalog (Multiple Quotes, Demo-friendly)
**Status:** DONE
**Priority:** P0
**Depends on:** T-120, T-129, T-136

### Description
데모에서 "협상"이 보이려면 선택지가 있어야 한다.
SLA 오퍼를 카탈로그(프리셋)로 모킹, Seller는 buyer mandate를 수락하는 형태.

### Tasks
- 오퍼 카탈로그 위치 결정 (Demo Console 로컬 프리셋 / Gateway API / Seller quote)
- 최소 3개 프리셋:
  - `Bronze`: 낮은 max_price, 느슨한 latency tier
  - `Silver`: 중간
  - `Gold`: 높은 max_price, 타이트한 latency tier
- 각 오퍼 필드: `offer_id`, `service_id`, `max_price`, `base_pay`, `bonus_rules`, `validators`, `dispute_window_sec`
- mandate에 `offer_id` 유래 기록

### Acceptance Criteria
- [ ] 데모 콘솔에서 Bronze/Silver/Gold 중 선택, SLA 조건이 receipt/이력에 명확히 남음

### Commit Message
`feat(gateway): add mock SLA offer catalog with Bronze/Silver/Gold presets`

---

## T-144 — Dashboard SLA/Incident Simulator Controls (Latency Slider + Failure Toggles)
**Status:** DONE
**Priority:** P0
**Depends on:** T-136, T-138, T-140, T-141

### Description
발표 중 실시간으로 SLA를 깨거나 만족시키는 모습을 위해, 대시보드에 시뮬레이터 컨트롤 추가.

### Tasks
- Seller 시뮬레이션 입력: `delay_ms` 슬라이더 (0~8000), `force_error` 토글
- Gateway가 시뮬레이션 파라미터를 seller로 전달
- Demo Console에 컨트롤: SLA 오퍼 선택 + 지연 슬라이더 + 오류 토글 + Run 버튼
- Event Ledger에 시뮬레이션 설정값 기록

### Acceptance Criteria
- [ ] 슬라이더/토글로 SLA 만족/위반을 즉석 재현
- [ ] 이력에서 당시 시뮬레이션 설정과 결과가 함께 보임

### Commit Message
`feat(dashboard): add SLA simulator controls with latency slider`

---

## T-145 — Demo Runner Migration to Gemini Seller (No demo_seller Dependency)
**Status:** DONE
**Priority:** P0
**Depends on:** T-120, T-130

### Description
`scripts/run_demo.py`가 `seller/`(Gemini) upstream으로도 동일하게 동작하도록 마이그레이션.

### Tasks
- `scripts/run_demo.py` 수정:
  - Seller upstream이 `seller/main.py`일 때도 `fast|slow|invalid` 재현
  - Gemini 사용 여부/모델명 로그
  - fallback 표기
- DEMO.md/LOCAL.md prereq를 `seller/` 기준으로 업데이트

### Acceptance Criteria
- [ ] Gemini seller로 3시나리오(정상/느림/무효) 재현, receipt/정산까지 일관

### Commit Message
`feat(demo): migrate demo runner to Gemini seller`

---

# Milestone 6 — WDK Module Hardening

WDK sidecar(Node.js) + Python 클라이언트 + 통합 레이어 전반의 보안·신뢰성·운영성 개선.
기존 기능은 유지하면서 프로덕션-레디 수준으로 끌어올린다.

**영향 범위:**
- `wdk-service/src/server.mjs` — Node.js sidecar
- `buyer_agent/wdk_wallet.py` — Python HTTP 클라이언트
- `gateway/app/settlement_client.py` — gateway 정산 서명
- `buyer_agent/client.py` — buyer deposit 경로
- `buyer_agent/tools.py` — tool chain executor

---

## T-150 — WDK Seed Phrase Exposure 차단
**Status:** TODO
**Priority:** P0
**Depends on:** none

### Description
WDK 서비스와 Python 클라이언트에서 seed phrase가 로그·응답·repr에 노출되는 경로를 모두 차단한다.

### Tasks
- `wdk-service/src/server.mjs`: `/wallet/create` 응답에서 `seedPhrase` 필드 제거
- `wdk-service/src/server.mjs`: `/health` 응답에서 `rpcUrl` 필드 제거 (내부 인프라 정보 유출 방지)
- `buyer_agent/wdk_wallet.py`: `WDKWallet.__repr__` 오버라이드 — seed_phrase를 `***` 마스킹
- `buyer_agent/wdk_wallet.py`: `__str__` 도 동일 처리
- seed phrase가 포함된 객체가 logger·traceback에 찍히는 경로 점검

### Acceptance Criteria
- [ ] `/wallet/create` 응답에 seedPhrase 없음
- [ ] `/health` 응답에 rpcUrl 없음
- [ ] `repr(wallet)`, `str(wallet)` 에 seed phrase 미노출
- [ ] 기존 테스트 전부 통과

### Commit Message
`fix(wdk): remove seed phrase exposure from API responses and repr`

---

## T-151 — WDK Service API 인증 (Bearer Token)
**Status:** TODO
**Priority:** P0
**Depends on:** T-150

### Description
WDK sidecar에 Bearer token 기반 인증을 추가해 무인가 호출을 차단한다.

### Tasks
- `server.mjs`: 환경변수 `WDK_AUTH_TOKEN`이 설정되면 모든 요청에 `Authorization: Bearer <token>` 헤더 검증 미들웨어 추가
- `WDK_AUTH_TOKEN` 미설정 시 인증 미적용 (하위 호환)
- `wdk_wallet.py`: `_request()` 에서 `WDK_AUTH_TOKEN` 환경변수 읽어 Authorization 헤더 첨부
- `/health`는 인증 없이 접근 가능 (liveness probe)

### Acceptance Criteria
- [ ] `WDK_AUTH_TOKEN` 설정 시, 토큰 없는 요청은 401 반환
- [ ] 올바른 토큰 포함 시 정상 동작
- [ ] `/health`는 토큰 없이도 200 응답
- [ ] `WDK_AUTH_TOKEN` 미설정 시 기존 동작과 동일
- [ ] 기존 테스트 전부 통과

### Commit Message
`feat(wdk): add Bearer token authentication to WDK sidecar`

---

## T-152 — WDK Service Nonce Manager (동시 tx 충돌 방지)
**Status:** TODO
**Priority:** P0
**Depends on:** none

### Description
WDK 서비스에서 동시 트랜잭션 전송 시 nonce 충돌을 방지하는 per-wallet mutex + pending nonce tracker를 구현한다.

### Tasks
- `server.mjs`: wallet별 nonce 관리 객체 추가
  - `pendingNonce` Map: address → 마지막 사용 nonce
  - nonce 할당 시 `Math.max(chain_pending_nonce, local_pending + 1)`
- wallet별 mutex (간단한 promise 기반 lock)로 approve → deposit 같은 연속 호출이 순서 보장되도록
- tx 실패 시 nonce 카운터 롤백
- `/wallet/approve`, `/wallet/deposit`, `/wallet/transfer` 엔드포인트에 적용

### Acceptance Criteria
- [ ] 동일 wallet에서 approve + deposit 연속 호출 시 nonce 충돌 없음
- [ ] 동시 2개 deposit 요청 시 각각 다른 nonce 사용
- [ ] tx 실패 시 다음 요청에서 nonce 복구
- [ ] 기존 테스트 전부 통과

### Commit Message
`feat(wdk): add per-wallet nonce manager to prevent tx collisions`

---

## T-153 — WDKWallet Async Client + Connection Pooling
**Status:** TODO
**Priority:** P0
**Depends on:** none

### Description
Python WDK 클라이언트를 async로 전환하고 커넥션 풀링을 적용해 이벤트루프 블로킹과 TCP 오버헤드를 제거한다.

### Tasks
- `wdk_wallet.py`: `_request()` 를 `async def _request()` 로 변환
  - `httpx.AsyncClient` 인스턴스를 재사용 (lazy init, close 메서드 제공)
- 모든 퍼블릭 메서드 async 전환
- 동기 호출이 필요한 곳을 위한 `_request_sync()` 폴백 유지
- 호출자 수정: `client.py`, `settlement_client.py`, `tools.py`의 WDK 호출을 await으로 변환
- 커넥션 풀 사이즈: `WDK_POOL_SIZE` 환경변수 (기본 10)

### Acceptance Criteria
- [ ] WDK 호출이 이벤트루프를 블로킹하지 않음
- [ ] httpx.AsyncClient가 요청 간 재사용됨
- [ ] 기존 기능 동일 동작
- [ ] 기존 테스트 async로 업데이트 후 전부 통과

### Commit Message
`refactor(wdk): convert WDKWallet to async with connection pooling`

---

## T-154 — WDK Retry + Circuit Breaker
**Status:** TODO
**Priority:** P1
**Depends on:** T-153

### Description
WDK 클라이언트에 재시도 로직과 circuit breaker 패턴을 적용해 일시적 장애에 대한 복원력을 높인다.

### Tasks
- `wdk_wallet.py`: `_request()` 에 retry 로직 추가
  - 재시도 대상: `httpx.ConnectError`, `httpx.TimeoutException`, HTTP 502/503/504
  - 최대 2회 재시도, 지수 백오프 (0.5s, 1s)
  - 비재시도 대상: 400, 401, 404 등 클라이언트 에러
- circuit breaker 상태 머신:
  - CLOSED → 연속 3회 실패 시 OPEN
  - OPEN → 즉시 `WDKServiceError` 반환, 30초 후 HALF_OPEN
  - HALF_OPEN → 1회 시도, 성공 시 CLOSED, 실패 시 OPEN
- `from_env()` 에서 WDK가 None일 때 warning 로그 추가

### Acceptance Criteria
- [ ] 일시적 타임아웃 시 재시도 후 성공
- [ ] 연속 3회 실패 시 circuit open, WDK 호출 스킵하고 바로 fallback
- [ ] circuit 복구 후 정상 동작
- [ ] `from_env()` None 리턴 시 로그에 이유 출력
- [ ] 기존 테스트 통과

### Commit Message
`feat(wdk): add retry with exponential backoff and circuit breaker`

---

## T-155 — Deposit ABI 단일화 (shared)
**Status:** TODO
**Priority:** P1
**Depends on:** none

### Description
deposit() ABI가 `server.mjs`, `settlement_client.py`, `client.py` 3곳에 중복 정의. 단일 소스로 통합한다.

### Tasks
- `shared/abi/settlement.json` 파일 생성: 전체 Settlement ABI
- `gateway/app/settlement_client.py`: `SETTLEMENT_ABI` 상수 제거, shared에서 로드
- `buyer_agent/client.py`: 로컬 `abi` 변수 제거, shared에서 로드
- `wdk-service/src/server.mjs`: `depositInterface`를 shared ABI에서 로드
- 유틸: `shared/load_abi.py` (Python용)

### Acceptance Criteria
- [ ] deposit ABI 정의가 코드상 1곳에만 존재
- [ ] 3개 컴포넌트 모두 동일 소스에서 ABI 로드
- [ ] 기존 테스트 전부 통과

### Commit Message
`refactor(wdk): unify settlement ABI into shared/abi/settlement.json`

---

## T-156 — Approve → Deposit 원자성 + 재시도 전략
**Status:** TODO
**Priority:** P1
**Depends on:** T-152

### Description
approve 성공 후 deposit 실패 시 allowance만 남고 deposit이 안 되는 문제를 해결.

### Tasks
- `server.mjs`: `/wallet/approve-and-deposit` 복합 엔드포인트 추가
  - approve → tx receipt 대기 → deposit 순차 실행
  - deposit 실패 시 최대 2회 재시도
  - 전체 실패 시 에러 응답에 `approve_tx_hash` 포함
- `wdk_wallet.py`: `approve_and_deposit()` 메서드 추가
- `client.py`, `tools.py`의 approve → deposit 시퀀스를 새 메서드로 교체
- 기존 개별 엔드포인트는 유지 (하위 호환)

### Acceptance Criteria
- [ ] approve 성공 + deposit 실패 시 deposit 재시도
- [ ] 최종 실패 시 approve_tx_hash가 에러에 포함
- [ ] 정상 경로에서 기존과 동일 동작
- [ ] 기존 테스트 통과 + 새 테스트 추가

### Commit Message
`feat(wdk): add atomic approve-and-deposit endpoint with retry`

---

## T-157 — WDK sign-message vs sign-bytes 서명 경로 통일
**Status:** TODO
**Priority:** P1
**Depends on:** none

### Description
`sign-message`는 WDK `account.sign()`을, `sign-bytes`는 ethers.Wallet을 직접 생성해 `signMessage()`를 호출.
서명 경로가 다르면 포맷 불일치 가능.

### Tasks
- `server.mjs`: `sign-bytes`가 WDK native signing을 우선 사용하도록 변경
  - 미지원 시 ethers fallback 유지하되, 응답에 `signing_method: "ethers_fallback"` 필드 추가
- 두 엔드포인트의 서명 포맷 일관성 검증 테스트 추가

### Acceptance Criteria
- [ ] 동일 메시지에 대해 두 엔드포인트가 같은 결과 (또는 차이 문서화)
- [ ] private key 직접 접근이 WDK native로 대체됨 (가능한 경우)
- [ ] 기존 테스트 통과

### Commit Message
`fix(wdk): unify signing paths between sign-message and sign-bytes`

---

## T-158 — WDK Service Observability (Logging + Metrics)
**Status:** TODO
**Priority:** P1
**Depends on:** none

### Description
WDK 서비스에 구조화된 요청 로깅과 기본 메트릭 추가. 현재는 서버 시작 console.log 하나뿐.

### Tasks
- `server.mjs`: 요청 로깅 미들웨어
  - method, path, status, duration_ms, wallet_address
  - seed phrase / private key 절대 로그 미포함
- `server.mjs`: `/metrics` 엔드포인트
  - `wdk_requests_total{method, path, status}` 카운터
  - `wdk_request_duration_ms{method, path}` 히스토그램
  - `wdk_wallets_loaded` 게이지
- `wdk_wallet.py`: 각 WDK 호출의 duration_ms를 logger에 출력

### Acceptance Criteria
- [ ] 모든 WDK API 호출이 구조화된 로그에 기록됨
- [ ] `/metrics` 엔드포인트가 기본 카운터/게이지 반환
- [ ] 로그에 seed phrase/private key 미포함
- [ ] Python 클라이언트에서 WDK 호출 타이밍 로그 출력

### Commit Message
`feat(wdk): add structured request logging and /metrics endpoint`

---

## T-159 — WDK Service Graceful Shutdown + withTimeout 타이머 누수 수정
**Status:** TODO
**Priority:** P1
**Depends on:** none

### Description
프로세스 종료 시 진행 중 요청 정리 + withTimeout 타이머 누수 수정.

### Tasks
- `server.mjs`: SIGTERM/SIGINT 핸들러
  - 새 요청 거부 (503)
  - 진행 중 요청 완료 대기 (최대 10초)
  - 서버 종료
- `server.mjs`: `withTimeout()` 수정 — 성공 시 `clearTimeout` 호출

### Acceptance Criteria
- [ ] SIGTERM 수신 시 진행 중 요청 완료 후 종료
- [ ] withTimeout 성공 시 타이머 클린업 확인
- [ ] 기존 테스트 통과

### Commit Message
`fix(wdk): add graceful shutdown and fix withTimeout timer leak`

---

## T-160 — WDK Transaction Receipt 대기 옵션
**Status:** TODO
**Priority:** P1
**Depends on:** T-152

### Description
approve/deposit/transfer가 tx hash만 반환하고 confirmation을 안 기다림. receipt 대기 옵션 추가.

### Tasks
- `server.mjs`: 요청 body에 `waitForReceipt` 옵션 (기본 false)
  - `true` 시 `provider.waitForTransaction()` 후 receipt 정보 반환
  - receipt 필드: `status`, `blockNumber`, `gasUsed`
- `wdk_wallet.py`: `wait_for_receipt: bool = False` 파라미터 추가

### Acceptance Criteria
- [ ] `waitForReceipt=true` 시 tx 확정 후 receipt 포함 응답
- [ ] `waitForReceipt=false` 시 기존 동작과 동일
- [ ] receipt status 0 (실패) 시 에러 응답
- [ ] 기존 테스트 통과

### Commit Message
`feat(wdk): add waitForReceipt option for tx confirmation`

---

## T-161 — WDK RPC Provider Resilience (Retry + Fallback)
**Status:** TODO
**Priority:** P2
**Depends on:** none

### Description
단일 RPC provider 장애 시 전체 서비스 다운. fallback URL 추가.

### Tasks
- `server.mjs`: `WDK_EVM_RPC_URL_FALLBACK` 환경변수
- RPC 호출 실패 시 fallback URL로 재시도 (최대 1회)
- health check에서 primary/fallback 상태 모두 표시

### Acceptance Criteria
- [ ] primary RPC 장애 시 fallback으로 자동 전환
- [ ] health에서 primary/fallback 각각 상태 확인 가능
- [ ] 기존 테스트 통과

### Commit Message
`feat(wdk): add RPC provider fallback for resilience`

---

## T-162 — WDK Settlement Client Fallback 리팩토링
**Status:** TODO
**Priority:** P2
**Depends on:** T-153

### Description
`settlement_client.py`의 WDK → local key fallback이 3중 try/except로 가독성 최악. 리팩토링.

### Tasks
- `settle_request()` 서명 로직을 `_sign_settlement()` 헬퍼로 추출
  - 시도 순서: WDK → local key → raise
  - 중첩 try/except 제거
- `_get_gateway_wdk_wallet()` 에 threading.Lock 추가 (싱글톤 thread safety)
- `ensure_wallet_loaded()` 가 `sign_bytes()` 후에 불필요하게 호출되는 부분 제거

### Acceptance Criteria
- [ ] settle_request() 서명 로직이 단일 헬퍼에 집중
- [ ] 중첩 try/except 3단 → 1단으로 축소
- [ ] 싱글톤 초기화 thread-safe
- [ ] 기존 테스트 통과

### Commit Message
`refactor(wdk): simplify settlement signing fallback logic`

---

## T-163 — WDK Health Check Integration (Startup Probe)
**Status:** DONE
**Priority:** P2
**Depends on:** none

### Description
어떤 컴포넌트도 시작 시 WDK 서비스 health를 확인하지 않음. 첫 요청에서야 발견.

### Tasks
- `wdk_wallet.py`: `health()` 메서드 추가 — `GET /health` 호출
- `buyer_agent/client.py`: `BuyerAgent.__init__`에서 WDK health check (실패 시 warning, fallback 전환)
- `gateway/app/settlement_client.py`: gateway 시작 시 WDK health check
- FastAPI startup 이벤트에 WDK readiness 로그

### Acceptance Criteria
- [ ] WDK 서비스 미기동 시 시작 로그에 warning 출력
- [ ] health check 실패해도 애플리케이션 시작됨 (graceful degradation)
- [ ] WDK 기동 중이면 connected + 체인/블록 정보 로그
- [ ] 기존 테스트 통과

### Commit Message
`feat(wdk): add startup health check for WDK sidecar`

---

## T-164 — WDK Service 테스트 스위트 (Node.js)
**Status:** DONE
**Priority:** P2
**Depends on:** T-152, T-159

### Description
WDK Node.js 서비스 자체에 대한 테스트가 전무. 유닛 + 통합 테스트 추가.

### Tasks
- `wdk-service/tests/` 디렉토리 생성, vitest 또는 jest
- 유닛 테스트:
  - `normalizeValue()` 다양한 입력
  - `badRequest()` 에러 포맷
  - `getWalletRecord()` 미등록 wallet
  - `withTimeout()` 정상/타임아웃
- API 통합 테스트 (supertest):
  - POST /wallet/create, /wallet/import, /wallet/sign-message, /wallet/sign-bytes
  - GET /wallet/:address/balance
  - 인증 실패 케이스
- package.json에 `test` 스크립트

### Acceptance Criteria
- [ ] 최소 10개 테스트 케이스
- [ ] `npm test`로 실행 가능
- [ ] CI에 WDK 서비스 테스트 추가

### Commit Message
`test(wdk): add Node.js test suite for WDK sidecar service`

---

## T-165 — WDK Fallback 경로 통합 테스트
**Status:** TODO
**Priority:** P2
**Depends on:** T-153, T-154

### Description
WDK 실패 → local key signing fallback 경로 테스트가 없음.

### Tasks
- `gateway/tests/test_settlement_client_fallback.py`:
  - WDK sign_bytes 실패 → local key signing 정상
  - WDK 완전 불가 → local key 정상
  - 둘 다 실패 → 적절한 에러
- `buyer_agent/tests/test_client_fallback.py`:
  - WDK deposit 실패 → local key deposit 성공
  - WDK 타임아웃 → fallback
- 동시성 테스트: 3개 요청 동시 settle

### Acceptance Criteria
- [ ] WDK → local key fallback 경로 테스트 커버리지 100%
- [ ] 동시 서명 요청 시 race condition 없음
- [ ] 기존 테스트 통과

### Commit Message
`test(wdk): add integration tests for WDK-to-local-key fallback paths`

---

## T-166 — WDK In-Memory Wallet 복구 (Service Restart Resilience)
**Status:** TODO
**Priority:** P2
**Depends on:** T-153

### Description
WDK 서비스 재시작 시 `wallets` Map 초기화 → Python 클라이언트 cached `_address`와 불일치.

### Tasks
- `wdk_wallet.py`: WDK 호출 시 "wallet not loaded" 에러 감지 → 자동 re-import 후 재시도 (최대 1회)
- `_address` 캐시 무효화: WDK 서비스 에러 시 `_address = None` 리셋

### Acceptance Criteria
- [ ] WDK 서비스 재시작 후 Python 클라이언트가 자동 복구
- [ ] 재시도는 최대 1회 (무한 루프 방지)
- [ ] 기존 테스트 통과

### Commit Message
`fix(wdk): auto-recover wallet on WDK service restart`

---

# Stretch Tickets (Optional)

### T-200 — Add SQL Test Harness Validator
**Status:** TODO
**Priority:** P2
**Depends on:** T-031, T-032
