# CI/CD Guide

This repository uses split deployment targets:

- Frontend (`dashboard/`) -> Vercel
- Backend services (`gateway`, `seller`, `wdk-service`) -> Railway
- Contracts (`contracts/`) -> manual deploy only

## Workflows

- `.github/workflows/ci.yml`  
  Lint/test only.
- `.github/workflows/deploy-vercel.yml`  
  Deploys frontend to Vercel on `main` push (when `dashboard/**` changes) or manual trigger.
- `.github/workflows/deploy-railway.yml`  
  Deploys backend services to Railway on `main` push (backend-related paths) or manual trigger.
- `.github/workflows/deploy-contracts-manual.yml`  
  Manual only. `workflow_dispatch` with optional broadcast.

## GitHub Secrets and Variables

### Vercel

Secrets:
- `VERCEL_TOKEN`

Variables:
- `VERCEL_ORG_ID`
- `VERCEL_DASHBOARD_PROJECT_ID`

### Railway

Secrets:
- `RAILWAY_TOKEN`

Variables:
- `RAILWAY_PROJECT_ID`
- `RAILWAY_ENVIRONMENT` (optional, defaults to `production`)
- `RAILWAY_SERVICE_GATEWAY`
- `RAILWAY_SERVICE_SELLER`
- `RAILWAY_SERVICE_WDK`

### Contracts (manual workflow)

Secrets:
- `CHAIN_RPC_URL`
- `CONTRACT_DEPLOYER_PRIVATE_KEY`
- `GATEWAY_ADDRESS` (optional)
- `RESOLVER_ADDRESS` (optional)
- `TOKEN_ADDRESS` (optional)

Variables:
- `DISPUTE_WINDOW_SECONDS` (optional)
- `BOND_AMOUNT` (optional)
- `MINT_TO_GATEWAY` (optional)
- `APPROVE_MAX` (optional, `true`/`false`)
- `OPTIMIZER_RUNS` (optional, defaults to `1`)

Notes:
- Contract workflow uses `--optimize --via-ir` by default to reduce Sepolia deploy gas.

## Railway Service Configuration (Recommended)

Use one Railway project with three services and deploy repository root source.

Gateway service:
- Build Command: `pip install -e .`
- Start Command: `uvicorn gateway.app.main:app --host 0.0.0.0 --port $PORT`

Seller service:
- Build Command: `pip install -e .`
- Start Command: `uvicorn seller.main:app --host 0.0.0.0 --port $PORT`

WDK service:
- Build Command: `cd wdk-service && npm ci`
- Start Command: `cd wdk-service && node src/server.mjs`

Notes:
- `wdk-service` imports ABI from `shared/abi/settlement.json`, so deploying repo root is safer.
- Add runtime environment variables per service in Railway (same names as `.env.example` / `.env`).

### Runtime Env (Railway) - Minimum for WDK flow

Set these in Railway service variables:

- Shared chain/token:
  - `CHAIN_ID=11155111`
  - `CHAIN_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com`
  - `PAYMENT_TOKEN_ADDRESS=<SEPOLIA_USDT_ADDRESS>`
  - `SETTLEMENT_CONTRACT_ADDRESS=<SETTLEMENT_ADDRESS>`
- WDK sidecar service:
  - `WDK_PORT=3100`
  - `WDK_CHAIN_NAME=ethereum`
  - `WDK_EVM_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com`
- Buyer/Gateway services (to use WDK path):
  - `WDK_SERVICE_URL=<your wdk-service public URL>`
  - One seed source: `DEMO_MNEMONIC` or `WDK_SEED_PHRASE` (or role-specific `<ROLE>_WDK_SEED_PHRASE`)
  - `BUYER_WDK_ACCOUNT_INDEX=0`
  - `GATEWAY_WDK_ACCOUNT_INDEX=2`

## Owner Migration Checklist

After repository owner transfer, verify:

1. Vercel project Git repository points to `inchyangv/SLAgent`.
2. Railway service repo trigger points to `inchyangv/SLAgent`.
3. GitHub Actions secrets/variables still exist in the new repo.
4. Trigger one manual run each:
   - `Deploy Frontend (Vercel)`
   - `Deploy Backend (Railway)`
5. Confirm production URLs and service health endpoints.
