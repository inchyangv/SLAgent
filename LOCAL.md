# 로컬 실행 가이드 — SLA-Pay v2

목표: 로컬에서 Gateway/Seller를 띄우고, 데모 스크립트로 `402 → paid request → receipt/정산` 흐름을 재현합니다.

중요: 해커톤 데모 기준으로 Seller는 **Google Gemini**를 사용하는 실제 LLM이어야 합니다.
이 레포의 `gateway/demo_seller`는 더미이므로, 데모에서는 별도 Gemini Seller를 띄우고 `SELLER_UPSTREAM_URL`로 연결하세요.

추가로, "에이전트 해커톤" 관점에서 Buyer도 LLM(Gemini)을 사용해 협상/의사결정을 하는 Buyer Agent가 필요합니다.
현재 레포는 buyer를 `scripts/run_demo.py`로 시뮬레이션하고 있으니, Buyer Agent는 `TICKET.md`의 `T-121`로 구현 범위를 잡아둡니다.

## 준비물

- Python 3.11+
- Foundry (`forge`, `cast`) (Solidity)

선택:
- `jq` (curl 출력 보기 편하게)

## Python 세팅

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

테스트:

```bash
.venv/bin/python -m pytest gateway/tests/ facilitator/tests/ -v
```

## 컨트랙트 빌드/테스트

```bash
cd contracts
forge build
forge test -v
```

## 로컬 실행 (Mock Chain)

Seller + Gateway를 각각 띄웁니다.

```bash
# Terminal 1
source .venv/bin/activate
uvicorn gateway.demo_seller.main:app --port 8001  # 더미 seller(LLM 아님)

# Terminal 2
source .venv/bin/activate
uvicorn gateway.app.main:app --port 8000
```

3가지 시나리오 실행:

```bash
source .venv/bin/activate
python scripts/run_demo.py
```

## SKALE 테스트넷으로 실행 (Live Chain)

### 1) SKALE BITE v2 Sandbox 2에 배포

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
- 가스는 `sFUEL`입니다. `sFUEL`(gas) 또는 `USDC`가 필요하면 SKALE Builders Telegram에서 요청해야 합니다:
  - SKALE Builders Telegram: `https://t.me/+dDdvu5T6BOEzZDEx`
  - 채널에서 @TheGreatAxios 를 태그해서 `sFUEL`/`USDC` 지원을 요청
- 데모는 **기존 USDC(6 decimals)** 를 사용합니다.

데모는 가장 단순하게 EOA 하나를 `deployer = gateway = resolver`로 쓰는 걸 추천합니다.

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

출력에서 아래 주소를 복사합니다:
- `Token` (USDC)
- `SLASettlement`

노트:
- 기존 USDC를 사용하므로 `mint()` 같은 건 없습니다. USDC는 Faucet(텔레그램 요청)로 받아야 합니다.
- 배포 스크립트는 `deployer == gateway`일 때 settlement 컨트랙트로 approve를 자동으로 잡아줄 수 있습니다(USDC도 ERC20 approve는 동일).

### 2) Gateway 환경변수 설정

이 코드베이스는 `.env` 자동 로딩이 아니라, 실행 쉘에서 `export ...`로 환경변수를 주입하는 방식입니다.

```bash
source .venv/bin/activate

export PAYMENT_MODE="hmac"  # 데모 안정성 우선. x402 모드는 아래 참고
export CHAIN_ID="103698795"
export CHAIN_RPC_URL="https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox"
export SETTLEMENT_CONTRACT_ADDRESS="0x..."
export PAYMENT_TOKEN_ADDRESS="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"  # USDC
export GATEWAY_PRIVATE_KEY="0x..."

export SELLER_UPSTREAM_URL="http://localhost:8001"  # Gemini seller URL
export SELLER_ADDRESS="0x2222222222222222222222222222222222222222"

uvicorn gateway.app.main:app --port 8000
```

### 3) Seller + 데모 스크립트 실행

```bash
# Terminal 1
source .venv/bin/activate
uvicorn gateway.demo_seller.main:app --port 8001  # 더미 seller(LLM 아님). 데모는 Gemini seller로 교체 권장

# Terminal 3
source .venv/bin/activate
export BUYER_ADDRESS="0x1111111111111111111111111111111111111111"
export SELLER_ADDRESS="0x2222222222222222222222222222222222222222"
python scripts/run_demo.py
```

정상 설정이면 paid request마다 실제 `tx_hash`가 내려옵니다.

노트(중요):
- 현재 컨트랙트는 `deposit()` 선행이 필요한 escrow 구조입니다.
- gateway가 `deposit → settle`을 자동으로 연결하지 못한 상태면 라이브 체인에서 settle tx가 revert될 수 있습니다(티켓: `TICKET.md`의 `T-123`).

### Allowance(approve) 트러블슈팅

allowance 관련 에러가 나면 **gateway EOA**에서 settlement 컨트랙트로 approve를 줘야 합니다.

```bash
export RPC_URL="https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox"
export PRIVATE_KEY="0x..."
export TOKEN="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"       # USDC
export SETTLEMENT="0x..."  # SLASettlement

cast send --rpc-url "$RPC_URL" --private-key "$PRIVATE_KEY" \
  "$TOKEN" "approve(address,uint256)" "$SETTLEMENT" "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
```

## 대시보드

가장 빠른 방법: `dashboard/index.html`을 브라우저로 엽니다.

브라우저가 `file://`에서 fetch를 막으면 간단히 서빙해서 봅니다.

```bash
cd dashboard
python3 -m http.server 5173
```

그리고 `http://localhost:5173/index.html`로 접속합니다.

## PAYMENT_MODE 옵션

Gateway x402 게이팅은 2가지 모드를 지원합니다:

1. `PAYMENT_MODE=hmac` (기본): 키 없이 동작하는 로컬 데모 모드
2. `PAYMENT_MODE=x402`: EIP-712 서명을 포함한 `X-PAYMENT` 헤더를 검증하는 모드

`PAYMENT_MODE=x402`로 데모 스크립트를 돌리려면:
```bash
export PAYMENT_MODE="x402"
export BUYER_ADDRESS="0x..."
export BUYER_PRIVATE_KEY="0x..."
export PAYMENT_TOKEN_ADDRESS="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"
export SLA_TOKEN_NAME="USDC"
export SLA_TOKEN_VERSION=""
```
