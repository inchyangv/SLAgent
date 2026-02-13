# 로컬 실행 가이드 — SLAgent-402

목표: 로컬에서 Gateway/Seller를 띄우고, `402 → paid request → receipt` 흐름을 빠르게 재현합니다.

중요:
- 해커톤 데모 기준으로 Seller는 **Google Gemini**를 사용하는 실제 LLM이어야 합니다.
- 다만 개발/리허설 중에는 `SELLER_FALLBACK=true`로 LLM 없이도 동작합니다.

---

## 환경변수(.env) 한 군데서 관리

이 레포는 **레포 루트 `/.env` 파일 1개**로 Gateway/Seller/스크립트 설정을 관리합니다(자동 로딩).

```bash
cp .env.example .env
```

로컬에서 “일단 돌아가게” 하려면:
- `PAYMENT_MODE=hmac` 유지
- `SETTLEMENT_CONTRACT_ADDRESS`, `GATEWAY_PRIVATE_KEY`는 비워도 됨 (온체인 tx는 mock 처리)

---

## 준비물

- Python 3.11+
- Foundry (`forge`, `cast`)

선택:
- `jq`

---

## Python 세팅

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 컨트랙트 빌드/테스트(선택)

```bash
cd contracts
forge build
forge test -v
```

---

## 로컬 실행 (체인 없이)

Terminal 1: Seller
```bash
source .venv/bin/activate
# Gemini 키가 없으면 fallback로:
# export SELLER_FALLBACK=true
uvicorn seller.main:app --port 8001
```

Terminal 2: Gateway
```bash
source .venv/bin/activate
uvicorn gateway.app.main:app --port 8000
```

웹 콘솔:
- `http://localhost:8000/dashboard/console.html`

CLI 시나리오 러너:
```bash
source .venv/bin/activate
python scripts/run_demo.py
```

---

## SKALE 테스트넷으로 실행 (Live Chain)

체인: SKALE Hackathon — BITE v2 Sandbox 2
- Chain ID: `103698795`
- RPC: `https://base-sepolia-testnet.skalenodes.com/v1/bite-v2-sandbox`
- Explorer: `https://base-sepolia-testnet-explorer.skalenodes.com:10032`
- USDC: `0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8`

중요(배포 실패 방지):
- 이 체인은 EVM 버전이 **Istanbul 이하**여야 배포가 됩니다.
- 이 레포는 `contracts/foundry.toml`에서 `evm_version = "istanbul"`로 맞춰둔 상태입니다.

### 1) Faucet/자금 준비

필요:
- `sFUEL` (가스)
- `USDC` (현재 구현은 gateway EOA가 deposit payer)

SKALE Builders Telegram: `https://t.me/+dDdvu5T6BOEzZDEx` 에서
@TheGreatAxios 를 태그해 `sFUEL`/`USDC` 지원 요청.

### 2) 컨트랙트 배포

`forge`는 쉘 env를 보므로 `.env`를 export로 로드해서 실행합니다:

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

배포 후 `.env`에 `SETTLEMENT_CONTRACT_ADDRESS`를 채웁니다.

### 3) 서비스 실행 + 데모

Seller:
```bash
source .venv/bin/activate
uvicorn seller.main:app --port 8001
```

Gateway:
```bash
source .venv/bin/activate
uvicorn gateway.app.main:app --port 8000
```

웹 콘솔:
- `http://localhost:8000/dashboard/console.html`

노트(중요, 현재 구현):
- 요청마다 `deposit_tx_hash`와 `settle_tx_hash`가 생성됩니다.
- **deposit payer는 gateway EOA**이므로, `GATEWAY_PRIVATE_KEY` 주소에 USDC가 있어야 합니다.
- deployer==gateway이면 배포 스크립트가 approve를 자동으로 잡아줄 수 있습니다.

### Allowance(approve) 트러블슈팅

approve가 안 되어 deposit이 실패하면(또는 token allowance 에러가 나면) gateway EOA에서 settlement에 approve를 줍니다.

```bash
set -a
source .env
set +a

cast send --rpc-url "$RPC_URL" --private-key "$PRIVATE_KEY" \
  "$TOKEN_ADDRESS" "approve(address,uint256)" "$SETTLEMENT_CONTRACT_ADDRESS" \
  "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
```

---

## PAYMENT_MODE 옵션

- `PAYMENT_MODE=hmac` (기본): 키 없이 데모 가능
- `PAYMENT_MODE=x402`: `X-PAYMENT`에 EIP-712 서명을 넣고 gateway가 검증

x402 모드에서 필요한 값은 `.env`에 채우면 됩니다:
- `BUYER_PRIVATE_KEY=...`
- `SLA_TOKEN_NAME=USDC`
- `SLA_TOKEN_VERSION=` (빈 문자열)

