# 데모 가이드 — SLA-Pay v2

이 문서는 실제 데모 진행 순서대로 적어둔 "진행 스크립트"입니다.

핵심 목표:
- x402 스타일의 `402 → paid request` 흐름을 보여준다
- 성능 기반 정산(`max_price`에서 자동 환불) 결과를 보여준다
- SKALE 테스트넷에 컨트랙트를 배포하고, 실제 `tx_hash`를 보여준다
- Seller는 **Google Gemini**를 사용한 “실제 LLM 서비스”여야 한다

## 데모 구성(한 줄 요약)

Buyer(스크립트/에이전트) → Gateway(`/v1/call`) → Seller(LLM: Gemini) → Receipt 생성/검증/가격결정 → SKALE 온체인 정산

## 에이전트 역할(반드시 이렇게 설명)

| 역할 | 코드 경로 | LLM 사용 | 핵심 책임 |
|------|----------|---------|----------|
| **Buyer Agent** | `buyer_agent/main.py`, `buyer_agent/client.py` | Gemini (협상) | 요구사항 정리/협상, 402 결제, 결과 검증(결정적), dispute |
| **Seller Agent/Service** | `seller/main.py`, `seller/gemini_client.py` | Gemini (작업 수행) | capabilities/quote 제공, 실제 작업 수행(LLM), 스키마 준수 출력 |
| **Gateway** | `gateway/app/main.py`, `gateway/app/pricing.py`, `gateway/app/validators/` | 사용 안 함 | 측정/검증(결정적), pricing(결정적), receipt 발급, 온체인 정산 제출 |
| **Resolver** | `scripts/resolve_dispute.py` | 사용 안 함 | dispute 해결, 최종 payout 결정 |

주의: Gateway의 검증/가격결정/정산은 LLM이 하면 재현성이 깨지므로 "결정적 로직"으로 유지합니다.
상세 역할 정의: `docs/ARCHITECTURE.md` → "Agent Roles & Trust Boundaries" 참조.

## 0. 준비물

- Python 3.11+
- Foundry (`forge`, `cast`)
- SKALE 해커톤 체인(BITE v2 Sandbox 2) RPC 접근
- Seller 서비스(LLM Gemini 사용) 실행 주소

## 1. 컨트랙트 배포 (SKALE BITE v2 Sandbox 2)

네트워크(해커톤 문서 기준):
- Chain ID: `103698795`
- RPC: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Explorer: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- (참고) USDC: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`

중요(배포 실패 방지):
- 이 체인은 EVM 버전이 **Istanbul 이하**여야 배포가 됩니다.
- 이 레포는 `contracts/foundry.toml`에 `evm_version = "istanbul"`로 고정되어 있습니다.

지갑 네트워크 추가(수동):
- Network Name: `SKALE BITE v2 Sandbox 2`
- RPC URL: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Chain ID: `103698795`
- Currency Symbol: `sFUEL`
- Block Explorer URL: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`

Faucet/자금 준비:
- 이 체인의 가스는 `sFUEL`입니다. `sFUEL`(gas) 또는 `USDC`가 필요하면 SKALE Builders Telegram에서 요청해야 합니다:
  - SKALE Builders Telegram: `https://t.me/+dDdvu5T6BOEzZDEx`
  - 채널에서 @TheGreatAxios 를 태그해서 `sFUEL`/`USDC` 지원을 요청
- (x402/정산 토큰) 이번 데모는 **기존 USDC**를 사용합니다(6 decimals).

배포는 가장 단순하게 EOA 하나를 `deployer = gateway = resolver`로 씁니다.

```bash
cd contracts
export RPC_URL="https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox"
export PRIVATE_KEY="0x..."
export TOKEN_ADDRESS="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"  # USDC (predeployed)

forge script script/DeploySlaPayV2.s.sol:DeploySlaPayV2 \
  --rpc-url "$RPC_URL" \
  --broadcast \
  -vvvv
```

출력으로 다음 2개 주소를 확보합니다:
- `Token` (USDC)
- `SLASettlement`

## 2. Gateway 환경변수 세팅 (라이브 체인)

Gateway는 `.env` 자동 로딩이 아니라, 실행 쉘에서 `export`로 주입합니다.

```bash
source .venv/bin/activate

export PAYMENT_MODE="hmac"   # 데모 안정성 우선(키 없이 가능). x402 모드는 아래 참고
export CHAIN_ID="103698795"
export CHAIN_RPC_URL="https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox"
export PAYMENT_TOKEN_ADDRESS="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"  # USDC
export SETTLEMENT_CONTRACT_ADDRESS="0x..."      # SLASettlement
export GATEWAY_PRIVATE_KEY="0x..."              # 배포에 사용한 PRIVATE_KEY와 동일 권장

export SELLER_UPSTREAM_URL="http://localhost:8001"  # Gemini seller URL
export SELLER_ADDRESS="0x2222222222222222222222222222222222222222"

uvicorn gateway.app.main:app --port 8000
```

주의:
- 온체인 정산을 하려면 `SELLER_ADDRESS`는 **반드시 유효한 EVM 주소**여야 합니다.

## 3. Seller(Gemini) 실행

이 레포의 `gateway/demo_seller`는 더미 JSON이라서 LLM을 쓰지 않습니다.
데모에서는 Gemini를 사용하는 Seller를 띄우고, `SELLER_UPSTREAM_URL`을 그 주소로 맞춥니다.

Seller는 `POST /seller/call`을 제공하고, 응답 JSON은 `invoice_v1`을 만족해야 합니다:
- 스키마: `gateway/app/validators/schemas/invoice_v1.json`

## 4. 데모 실행(3 시나리오)

```bash
source .venv/bin/activate

export GATEWAY_URL="http://localhost:8000"
export BUYER_ADDRESS="0x1111111111111111111111111111111111111111"
export SELLER_ADDRESS="0x2222222222222222222222222222222222222222"

python scripts/run_demo.py
```

기대 결과:
- 각 시나리오에서 첫 요청은 `402 Payment Required`
- paid 요청은 `payout/refund/receipt_hash/tx_hash`를 반환
- `tx_hash`가 실제 해시로 찍히면 “SKALE 온체인 정산” 성공

노트(중요):
- 현재 컨트랙트는 `deposit()` 선행이 필요한 escrow 구조입니다.
- gateway가 `deposit → settle`을 자동으로 연결하지 못한 상태면 라이브 체인에서 settle tx가 revert될 수 있습니다(티켓: `TICKET.md`의 `T-123`).

## 5. x402 모드(옵션)

Gateway는 `PAYMENT_MODE=x402`도 지원합니다.
이 모드는 `X-PAYMENT`에 EIP-712 서명된 Authorization을 넣고, gateway가 서명 검증까지 수행합니다.

현재 MVP의 온체인 자금 흐름은 gateway escrow 기반이라, “결제 authorization”과 “온체인 자금 이동”은 분리되어 있습니다.

사용 예:
```bash
export PAYMENT_MODE="x402"
export BUYER_ADDRESS="0x..."
export BUYER_PRIVATE_KEY="0x..."
export PAYMENT_TOKEN_ADDRESS="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"
export CHAIN_ID="103698795"
# USDC EIP-712 domain
export SLA_TOKEN_NAME="USDC"
export SLA_TOKEN_VERSION=""
```

그 상태로 `python scripts/run_demo.py`를 실행하면 됩니다.

## 대시보드

`dashboard/index.html`을 열어서 receipt ledger를 확인합니다.

브라우저가 `file://` fetch를 막으면:
```bash
cd dashboard
python3 -m http.server 5173
```

그리고 `http://localhost:5173/index.html`로 접속합니다.
