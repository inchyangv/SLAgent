# Demo Guide — SLA-Pay v2

## x402 Payment Flow

### Step 1: Unpaid request → 402

```bash
curl -X POST http://localhost:8000/v1/call \
  -H "Content-Type: application/json" \
  -d '{"payload": "hello"}'
```

Response (402):
```json
{
  "error": "Payment Required",
  "accepts": [{
    "scheme": "x402",
    "maxAmountRequired": "100000",
    "token": "0x...",
    "nonce": "...",
    ...
  }]
}
```

### Step 2: Create payment token

For MVP demo, use the HMAC-based payment token:

```python
from gateway.app.x402 import create_payment_token
import json

token = create_payment_token(path="/v1/call", max_price="100000", nonce="my-nonce")
header = json.dumps({
    "token": token,
    "nonce": "my-nonce",
    "max_price": "100000",
    "buyer": "0xYOUR_ADDRESS"
})
```

### Step 3: Paid request → Success

```bash
curl -X POST http://localhost:8000/v1/call \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: {\"token\":\"<hmac>\",\"nonce\":\"<nonce>\",\"max_price\":\"100000\",\"buyer\":\"0xADDR\"}" \
  -d '{"mode": "fast"}'
```

Response (200):
```json
{
  "request_id": "req_...",
  "seller_response": {...},
  "metrics": {"ttft_ms": 100, "latency_ms": 500},
  "validation_passed": true,
  "payout": "100000",
  "refund": "0",
  "receipt_hash": "0x..."
}
```

## Running Locally

```bash
# Terminal 1: Start seller (demo)
uvicorn gateway.demo_seller.main:app --port 8001

# Terminal 2: Start gateway
uvicorn gateway.app.main:app --port 8000

# Terminal 3: Run demo script
python scripts/run_demo.py
```

## Three Scenarios

| Scenario | Mode | Payout | Refund | Rule |
|----------|------|--------|--------|------|
| Fast + valid | fast | $0.10 (100000) | $0.00 | latency_tier_lte_2000 |
| Slow + valid | slow | $0.06 (60000) | $0.04 (40000) | latency_tier_lte_999999999 |
| Invalid output | invalid | $0.00 | $0.10 (100000) | validation_failed |
