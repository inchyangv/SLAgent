# 데모 가이드 — SLAgent-402

이 문서는 발표/심사장에서 그대로 따라 할 수 있는 데모 진행 스크립트입니다.

핵심 목표:
- x402 스타일의 `402 → paid request` 경험을 보여준다
- Seller가 **Google Gemini**로 실제 작업(Invoice 생성)을 수행함을 증거로 보여준다
- Gateway가 SLA를 **결정적으로** 측정/검증/가격결정하고 receipt + event timeline을 남긴다
- SKALE 테스트넷(BITE v2 Sandbox 2)에서 `deposit → settle` 트랜잭션 해시를 보여준다

## 데모 구성(한 줄)

Buyer(웹 콘솔/스크립트) → Gateway(`/v1/call`) → Seller(Gemini) → receipt/events → SKALE 온체인 정산

## 에이전트 역할(발표용)

| 역할 | 코드 경로 | LLM 사용 | 핵심 책임 |
|------|----------|---------|----------|
| Buyer(웹/스크립트) | `dashboard/console.html`, `scripts/run_demo.py` | (현재는 사용 안 함) | SLA 오퍼 선택/mandate 등록, 402 결제, 결과 확인 |
| Buyer Agent(옵션) | `buyer_agent/*` | (현재는 사용 안 함) | (옵션) 자동 실행 + receipt invariant 검증 + attestation |
| Seller Service | `seller/main.py` | **Gemini** | 실제 작업 수행(생성), SLA 시뮬레이션(지연/오류/무효/타임아웃), mandate 수락 |
| Gateway | `gateway/app/main.py` | 사용 안 함 | 측정/검증(결정적), pricing(결정적), receipt/events, 온체인 tx 제출 |
| Settlement Contract | `contracts/src/SLASettlement.sol` | 사용 안 함 | escrow `deposit()`, 조건 확정 `settle()`, 분쟁/최종화 |

주의: Gateway의 검증/가격결정/온체인 제출은 LLM이 하면 재현성이 깨지므로 **결정적 로직**으로 유지합니다.

---

## 0. 체인/토큰(고정 값)

체인: SKALE Hackathon — BITE v2 Sandbox 2
- Chain ID: `103698795`
- RPC: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Explorer: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- Gas token: `sFUEL`

토큰: predeployed USDC (6 decimals)
- USDC 주소: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- x402(EIP-712) 도메인:
  - `SLA_TOKEN_NAME=USDC`
  - `SLA_TOKEN_VERSION=""` (빈 문자열)

중요(배포 실패 방지):
- 이 체인은 EVM 버전이 **Istanbul 이하**여야 배포가 됩니다.
- 이 레포는 `contracts/foundry.toml`에서 `evm_version = "istanbul"`로 맞춰둔 상태입니다.

---

## 1. 환경변수(.env) 한 군데서 관리

이 레포는 **레포 루트 `/.env` 파일 1개**로 Gateway/Seller/스크립트 설정을 관리합니다(자동 로딩).

```bash
cp .env.example .env
```

`.env`에서 반드시 채울 값:
- `PRIVATE_KEY` (컨트랙트 배포용)
- `GATEWAY_PRIVATE_KEY` (gateway 온체인 tx signer)
- `SETTLEMENT_CONTRACT_ADDRESS` (배포 후 채움)
- `GEMINI_API_KEY` (Seller가 실제 Gemini 호출하려면 필요)

같은 지갑(EOA)로 묶어도 되는 것(데모 단순화):
- `PRIVATE_KEY` = `GATEWAY_PRIVATE_KEY` (권장: 배포 스크립트가 approve까지 잡아주기 쉬움)
- Resolver는 배포 시 `RESOLVER_ADDRESS`를 Gateway 주소로 동일하게 둬도 됨

중요(현재 구현 제약):
- 요청마다 `deposit()` tx의 **payer는 현재 gateway EOA**입니다. 즉 `GATEWAY_PRIVATE_KEY` 주소에 USDC가 있어야 합니다.

---

## 2. Faucet/자금 준비

필요:
- `sFUEL` (가스)
- `USDC` (현재 구현에서는 gateway EOA가 deposit에 사용)

가장 확실한 방법:
- SKALE Builders Telegram: `https://t.me/+dDdvu5T6BOEzZDEx`
- 채널에서 @TheGreatAxios 를 태그해서 `sFUEL`/`USDC` 지원 요청

---

## 3. 컨트랙트 배포 (SKALE BITE v2 Sandbox 2)

`forge`/`cast`는 쉘 env를 보므로, `.env`를 export로 로드해서 씁니다:

```bash
set -a
source .env
set +a

cd contracts
forge script script/DeploySlaPayV2.s.sol:DeploySlaPayV2 \
  --rpc-url "$RPC_URL" \
  --broadcast \
  -vvvv
```

출력에서 `SLASettlement` 주소를 복사해서 `.env`의 `SETTLEMENT_CONTRACT_ADDRESS`에 채웁니다.

---

## 4. 서비스 실행

### 4-1) Seller(Gemini)

```bash
source .venv/bin/activate
uvicorn seller.main:app --port 8001
```

주요 엔드포인트:
- `GET /seller/capabilities`
- `POST /seller/mandates/accept` (buyer 제안 mandate 수락)
- `POST /seller/call?mode=fast|slow|invalid|error|timeout&delay_ms=...`

LLM 사용 증거(데모용):
- 응답 헤더 `X-LLM-Provider`, `X-LLM-Model`, `X-LLM-Used`, `X-LLM-Mode`

### 4-2) Gateway

```bash
source .venv/bin/activate
uvicorn gateway.app.main:app --port 8000
```

대시보드(same-origin):
- Demo Console: `http://localhost:8000/dashboard/console.html`
- Receipt Ledger: `http://localhost:8000/dashboard/index.html`

---

## 5. 데모 실행(웹 콘솔, 추천)

1. `http://localhost:8000/dashboard/console.html` 접속
2. `Refresh All` 클릭
3. `Seller Capabilities`가 Gemini로 뜨는지 확인
4. `SLA Offer Catalog`에서 Bronze/Silver/Gold 중 하나 선택 후 `Negotiate`
5. 시뮬레이터 조작:
   - 지연 슬라이더(`delay_ms`)
   - 실패 토글(Invalid/Error/Timeout)
6. `Run Demo` 클릭
7. 아래를 한 화면에서 설명:
   - `402 → paid request` 흐름
   - breach reasons(왜 SLA가 깨졌는지)
   - receipt hash
   - `deposit_tx_hash`, `settle_tx_hash` (Explorer에서 확인)

---

## 6. 데모 실행(CLI 옵션)

간단 시나리오 러너:
```bash
source .venv/bin/activate
python scripts/run_demo.py
```

Buyer Agent(옵션, attestation까지 보고 싶을 때):
```bash
source .venv/bin/activate
python -m buyer_agent.main
```

---

## 7. x402 모드(옵션)

현재 `scripts/run_demo.py`는 `PAYMENT_MODE=x402`를 지원합니다.
다만 웹 콘솔의 `/v1/demo/run`은 내부적으로 Buyer Agent(HMAC)를 사용하므로, x402 데모는 CLI로 보여주는 것을 권장합니다.

`.env` 예:
- `PAYMENT_MODE=x402`
- `BUYER_PRIVATE_KEY=...`
- `PAYMENT_TOKEN_ADDRESS=0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`
- `SLA_TOKEN_NAME=USDC`
- `SLA_TOKEN_VERSION=`

노트:
- HTTP 레벨의 x402(402→paid)은 “결제 증명/게이팅”이고,
- 실제 escrow 자금 이동은 현재 `deposit()` 트랜잭션으로 연결되어 있습니다.

---

## 8. 발표용 API 치트시트

- Receipts: `GET /v1/receipts`
- Events: `GET /v1/events`
- Offer presets: `GET /v1/demo/offers`
- Demo run: `POST /v1/demo/run`

