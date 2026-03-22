# SLAgent-402 — 프로젝트 해설 & 데모 가이드

> **한 줄 요약:** AI 에이전트가 다른 에이전트 API를 살 때, "결과가 좋으면 full pay, 나쁘면 자동 환불"을 온체인에서 실현한다.

---

## 1. 이게 무슨 프로젝트인가?

### 문제: AI API 시장은 "선불 고정가" 구조다

AI 에이전트가 다른 에이전트 API를 구매할 때, 지금의 시장은 항상 같은 금액을 낸다.
- 응답이 빠르든 느리든 → 같은 돈
- 출력이 유효하든 불량이든 → 같은 돈
- 호출이 성공하든 실패하든 → 같은 돈 (또는 복잡한 분쟁 절차)

이 구조는 **Seller에게 품질 유인이 없고**, **Buyer에게 리스크가 집중**되어 있다.
에이전트가 자율적으로 수천 번 호출하는 미래라면 이 비용은 치명적이다.

### 해결: "증명으로 결제한다" (Pay by Proof)

SLAgent-402는 이 문제를 세 가지 원칙으로 푼다.

| 원칙 | 구현 |
|------|------|
| 선불 잠금, 성과 후 분배 | Buyer가 `max_price`를 escrow에 deposit → SLA 결과에 따라 Seller 지급 + Buyer 환불 자동 분배 |
| 결정론적 SLA 판정 | 지연(ms), JSON 스키마 검증 등 객관적 지표만으로 payout 계산 |
| 온체인 불변 증거 | Receipt hash, 서명, tx_hash가 블록체인에 기록 → 감사 가능 |

```
Buyer Agent
    │
    ├─ 1. WDK Wallet로 max_price deposit()
    ├─ 2. x402 결제 → Gateway (/v1/call)
    │
    └─ Gateway
           ├─ 3. Seller 호출 + 지연/응답 측정
           ├─ 4. JSON 스키마 검증
           ├─ 5. SLA Tier 기준 payout 계산
           ├─ 6. Performance Receipt 생성 & 서명
           └─ 7. SLASettlement.settle() 온체인 실행
                    ├─ Seller: payout 수령
                    └─ Buyer: (max_price - payout) 환불
```

### 결제 모델 예시

| SLA 결과 | 지급 | 환불 |
|----------|------|------|
| 성공 + 지연 ≤ 2s | 100,000 µUSDT (full) | 0 |
| 성공 + 2s < 지연 ≤ 5s | 80,000 µUSDT | 20,000 µUSDT |
| 성공 + 지연 > 5s | 60,000 µUSDT (base) | 40,000 µUSDT |
| 실패 또는 스키마 불통과 | 0 | 100,000 µUSDT (full refund) |

---

## 2. 해커톤과 어떻게 맞는가?

### 해커톤 소개

**Hackathon Galáctica: WDK Edition 1** (Tether, 2026.02.25 ~ 03.22)

> "AI agents are no longer just tools — but they are also not social experiments.
> In this hackathon, we explore **agents as economic infrastructure**."

이 해커톤의 핵심 명제는:
- 에이전트가 지갑을 갖고
- 자율적으로 돈을 움직이고
- 온체인에서 가치를 정산한다

SLAgent-402는 이 세 명제를 **정확히** 구현한다.

### 트랙 적합성

#### 🤖 Agent Wallets (WDK / Openclaw) 트랙 ← **메인 타겟**

| 요구사항 | SLAgent-402의 구현 |
|----------|-------------------|
| WDK 지갑 통합 | `@tetherto/wdk` + `@tetherto/wdk-wallet-evm` Node.js sidecar |
| 에이전트가 지갑 보유 | Buyer/Seller/Gateway 각각 독립 EOA (DEMO_MNEMONIC으로 파생) |
| 자율적 자산 이동 | Buyer Agent가 자동으로 approve + deposit 실행 |
| 온체인 정산 | SLASettlement 컨트랙트 (SKALE BITE v2 Sandbox) |

#### 🌊 Autonomous DeFi Agent 트랙 (보조)

- 에스크로 → 조건부 정산은 전통적 DeFi 패턴의 에이전트 버전
- Buyer 에이전트가 인간 개입 없이 예산 관리 + 결제 판단
- 분쟁 메커니즘(openDispute/resolveDispute)으로 trustless 보장

---

## 3. 왜 의미가 있는가 (심사 기준별)

### ① 기술적 정확성 (Technical Correctness)

**핵심:** 모든 payout 결정이 코드로 결정되고 온체인에서 검증 가능하다.

- Receipt의 `breach_reasons`가 ENUM으로 정의됨 (`BREACH_LATENCY_TIER_DOWN`, `BREACH_SCHEMA_FAIL` 등)
- `payout ≤ max_price` 불변식이 컨트랙트 레벨에서 강제됨
- Gateway 서명 → Buyer/Seller/Gateway 3자 attestation까지 지원
- x402 HTTP 결제 표준 사용 → 결제 채널 표준화
- WDK sidecar를 통한 키 격리 + Bearer 인증

### ② 에이전트 자율성 (Degree of Agent Autonomy)

**핵심:** 사람이 개입하지 않아도 전체 사이클이 돌아간다.

```
Buyer Agent 자율 루프:
  Seller 탐색 → SLA 협상 → Gemini로 mandate 조건 검토
  → WDK 지갑으로 deposit → Gateway 호출
  → Receipt 검증 → 3자 attestation 제출
  → (필요 시) Dispute 제기
```

- `AutopilotWidget`이 설정 주기로 자동 실행
- Gemini LLM이 SLA 판정 + 협상 조건 제안
- 에이전트가 예산 한도 내에서 스스로 tier 선택

### ③ 경제적 타당성 (Economic Soundness)

**핵심:** 선불 고정가 구조의 비효율을 정확히 제거한다.

- Seller 입장: 빠르고 정확하면 더 받는다 → 품질 유인
- Buyer 입장: 성과가 없으면 환불 → 리스크 최소화
- 분쟁 보증금(bond) 제도로 악의적 분쟁 억제
- 마이크로 결제 (100,000 µUSDT ≈ $0.10)에서도 가스비 없이 작동 (SKALE = gas-free)

### ④ 실세계 적용 가능성 (Real-world Applicability)

**핵심:** AI API 마켓플레이스의 실질적 결제 인프라.

지금 AI 에이전트 생태계에는 아래 인프라가 없다:
- "내가 부른 LLM이 SLA를 지켰는지" 증명하는 방법
- SLA 위반 시 자동 환불을 실행하는 온체인 메커니즘
- 에이전트 간 신뢰 없이 거래하는 결제 표준

SLAgent-402는 이 세 가지를 하나의 레이어로 제공한다.
**어떤 AI API 앞에든 Gateway를 붙이면 SLA 보증 결제가 된다.**

---

## 4. 기술 스택 한눈에 보기

```
┌─────────────────────────────────────────────────────────┐
│                    Buyer Agent (Python)                   │
│   Gemini 협상 → WDK approve+deposit → /v1/call 호출      │
└──────────────────────┬──────────────────────────────────┘
                       │  x402 결제 + deposit_tx_hash
┌──────────────────────▼──────────────────────────────────┐
│              SLAgent-402 Gateway (FastAPI)                │
│   측정(TTFT/latency) → 검증(JSON Schema) → Receipt 발행  │
│   Event Ledger → SLA 판정 (Deterministic + Gemini judge) │
└──────────────────────┬──────────────────────────────────┘
          ┌────────────┴────────────┐
          ▼                         ▼
┌─────────────────┐     ┌──────────────────────────┐
│  Seller Agent   │     │  SLASettlement.sol        │
│  (Gemini LLM    │     │  SKALE BITE v2 Sandbox    │
│   fast/slow/    │     │  deposit → settle →       │
│   invalid 모드) │     │  Settled 이벤트 emit       │
└─────────────────┘     └──────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────┐
│              WDK Sidecar (Node.js, port 3100)           │
│   @tetherto/wdk + wdk-wallet-evm                        │
│   sign / approve / deposit / balance                    │
└────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────┐
│              Dashboard (React + Vite)                   │
│   Autopilot · Receipts · Event Timeline                 │
│   SLA Simulator · History 페이지 · Dispute 패널          │
└────────────────────────────────────────────────────────┘
```

| 컴포넌트 | 기술 |
|----------|------|
| 스마트 컨트랙트 | Solidity (Foundry), SKALE BITE v2 Sandbox 2 |
| Gateway | Python, FastAPI, web3.py, eth-account |
| Buyer Agent | Python, httpx async, Gemini SDK |
| Seller Agent | Python, FastAPI, Gemini 2.0 Flash |
| WDK Sidecar | Node.js, `@tetherto/wdk`, ethers v6 |
| 결제 표준 | x402 (HTTP 402 Payment Required) |
| 대시보드 | React + Vite + TanStack Query + Recharts |
| 검증기 | JSON Schema (jsonschema) |

---

## 5. 실행 방법

### 사전 요구사항

```bash
# Python 의존성
pip install -e ".[dev]"

# Node.js (WDK sidecar)
cd wdk-service && npm install && cd ..

# .env 파일
cp .env.example .env
# → GEMINI_API_KEY, SETTLEMENT_CONTRACT_ADDRESS 등 입력
```

### 최소 실행 (로컬 Seller, 온체인 없음)

```bash
# Seller
uvicorn seller.main:app --port 8001

# Gateway
uvicorn gateway.app.main:app --port 8000

# 브라우저
open http://localhost:8000/dashboard/
```

### 풀 데모 (WDK + 온체인)

```bash
# WDK sidecar 시작
cd wdk-service && node src/server.mjs &

# 원커맨드 데모 (배포 → 실행 → 증빙)
python scripts/demo_one_command.py
```

---

## 6. 데모 동선 (7~10분)

### Step A. 환경 확인 (1분)
1. `http://localhost:8000/dashboard/` 접속
2. 상단 `Config` → Gateway URL / Seller URL 확인
3. `Refresh All` → `Seller Capabilities`에서 Gemini 연결 상태 확인

**멘트:** "실제 Gemini Seller, x402 결제, SKALE 온체인 정산이 연결된 상태입니다."

### Step B. Happy Path — 정상 지급 (2분)
1. 프리셋 `Happy Path` 선택
2. `SLA Evaluator` → `Start Autopilot`
3. 2~3틱 후 확인:
   - `SLA Status: PASS`, `Payout: 100,000`, `Refund: 0`
   - `Negotiation History`에서 Gemini 협상 이력
   - `Event Timeline`에서 `payment.*` → `validation.*` → `chain.*` 순서 확인

**멘트:** "Buyer가 lock한 돈에서 SLA 결과에 따라 자동으로 분배됩니다."

### Step C. Slow SLA — 지연으로 감액 (2분)
1. 프리셋 `Slow SLA` 전환
2. 다음 틱에서 `Payout: 80,000`, `Refund: 20,000` 확인
3. `breach_reasons: BREACH_LATENCY_TIER_DOWN` 확인

**멘트:** "2초 초과 5초 이하 구간으로 tier가 내려가고 자동 감액됩니다."

### Step D. SLA Simulator — 실시간 조작 (2분)
1. `SLA Simulator` 패널에서 `delay_ms` 슬라이더를 7000ms로 이동
2. `Run Scenario` 버튼
3. `Payout: 60,000` (base only) 확인
4. `Force Schema Fail` 토글 ON → `Payout: 0`, `Refund: 100,000` 확인

**멘트:** "SLA가 깨지는 순간을 실시간으로 재현할 수 있습니다."

### Step E. History 페이지 — 타임라인 재생 (1~2분)
1. 상단 네비게이션 → `History`
2. 최근 `request_id` 선택
3. `Receipt` 카드에서 breach reasons pill, attestation 개수, tx_hash 링크 확인
4. `Event Timeline`에서 협상 → 402 → 실행 → 검증 → 정산 전체 흐름 재생

**멘트:** "한 호출의 생애 전체가 증거로 기록되고 재생 가능합니다."

### Step F. 온체인 증빙 (30초)
- Receipt의 `tx_hash` 링크 → SKALE Explorer에서 `Settled` 이벤트 확인

---

## 7. 트랙 추가 데모 (구현됨)

### 🔧 Agentic Tool Usage on x402
- Buyer Agent가 유료 툴 2단계를 연쇄 호출 (각 단계 402 → pay → retry)
- WDK 지갑으로 step별 deposit + 예산 추적 로그
- `buyer_agent/tools.py`

### 📨 Best Integration of AP2 (Google A2A)
- intent → authorization → settlement → receipt 전 단계를 A2A/AP2 envelope로 감쌈
- 인증 실패 시나리오 포함 (`gateway/app/a2a/`)

### 🔒 Encrypted Agents (BITE v2)
- 조건/가격/정책을 AES-GCM 암호화로 봉인
- 성공 시에만 복호화 + 정산 (실패 경로는 암호화 유지)
- `gateway/app/bite_v2.py`

---

## 8. 차별점 요약

| 기존 AI API 결제 | SLAgent-402 |
|-----------------|-------------|
| 선불 고정가 | SLA 결과에 따른 차등 후불 |
| 신뢰 기반 SLA | 결정론적 검증 (스키마, 지연 측정) |
| 분쟁 수동 처리 | 온체인 dispute + 보증금 슬래싱 |
| 중앙 결제 | x402 표준 + 온체인 escrow |
| 아무 증거 없음 | Receipt hash 온체인 기록 + 3자 서명 |

> **"Don't pay upfront. Pay by proof."**
