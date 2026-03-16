# API — SLA Mandate & Receipt Schemas

## Core Interfaces

- `POST /v1/mandates`
- `POST /v1/call`
- `GET /v1/receipts`
- `GET /v1/balances`
- `POST /v1/disputes/open`
- `POST /v1/disputes/resolve`

Deposit-first request body additions:

- `request_id`
- `buyer`
- `deposit_tx_hash`

Gateway response highlights:

- `receipt_hash`
- `deposit_tx_hash`
- `settle_tx_hash`
- `payout`
- `refund`

## Optional Surfaces

- `gateway/app/a2a/` exposes A2A/AP2 envelope endpoints for protocol demos.
- `wdk-service/` exposes wallet create/import/balance/approve/deposit/sign routes.

---

## 1. SLA Mandate Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SLA Mandate",
  "type": "object",
  "required": [
    "version", "chain_id", "settlement_contract", "payment_token",
    "seller", "max_price", "base_pay", "bonus_rules",
    "timeout_ms", "validators", "dispute", "created_at", "expires_at"
  ],
  "properties": {
    "version": { "type": "string", "const": "1.0" },
    "mandate_id": { "type": "string", "description": "Computed: keccak256 of canonical payload" },
    "chain_id": { "type": "integer" },
    "settlement_contract": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "payment_token": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "seller": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "buyer": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "max_price": { "type": "string", "pattern": "^[0-9]+$" },
    "base_pay": { "type": "string", "pattern": "^[0-9]+$" },
    "bonus_rules": {
      "type": "object",
      "required": ["type", "tiers"],
      "properties": {
        "type": { "type": "string", "enum": ["latency_tiers"] },
        "tiers": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["lte_ms", "payout"],
            "properties": {
              "lte_ms": { "type": "integer", "minimum": 0 },
              "payout": { "type": "string", "pattern": "^[0-9]+$" }
            }
          }
        }
      }
    },
    "timeout_ms": { "type": "integer", "minimum": 1 },
    "validators": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type"],
        "properties": {
          "type": { "type": "string" },
          "schema_id": { "type": "string" }
        }
      }
    },
    "dispute": {
      "type": "object",
      "required": ["window_seconds", "bond_amount"],
      "properties": {
        "window_seconds": { "type": "integer" },
        "bond_amount": { "type": "string", "pattern": "^[0-9]+$" },
        "resolver": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" }
      }
    },
    "created_at": { "type": "string", "format": "date-time" },
    "expires_at": { "type": "string", "format": "date-time" },
    "seller_signature": { "type": "string" },
    "buyer_signature": { "type": "string" }
  }
}
```

## 2. Performance Receipt Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Performance Receipt",
  "type": "object",
  "required": [
    "version", "mandate_id", "request_id", "buyer", "seller", "gateway",
    "timestamps", "metrics", "outcome", "validation", "pricing", "hashes"
  ],
  "properties": {
    "version": { "type": "string", "const": "1.0" },
    "mandate_id": { "type": "string" },
    "request_id": { "type": "string" },
    "buyer": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "seller": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "gateway": { "type": "string", "pattern": "^0x[0-9a-fA-F]{40}$" },
    "timestamps": {
      "type": "object",
      "required": ["t_request_received", "t_response_done"],
      "properties": {
        "t_request_received": { "type": "string", "format": "date-time" },
        "t_first_token": { "type": "string", "format": "date-time" },
        "t_response_done": { "type": "string", "format": "date-time" }
      }
    },
    "metrics": {
      "type": "object",
      "required": ["latency_ms"],
      "properties": {
        "ttft_ms": { "type": "integer", "minimum": 0 },
        "latency_ms": { "type": "integer", "minimum": 0 }
      }
    },
    "outcome": {
      "type": "object",
      "required": ["success"],
      "properties": {
        "success": { "type": "boolean" },
        "error_code": { "type": ["string", "null"] }
      }
    },
    "validation": {
      "type": "object",
      "required": ["overall_pass", "results"],
      "properties": {
        "overall_pass": { "type": "boolean" },
        "results": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["type", "pass"],
            "properties": {
              "type": { "type": "string" },
              "schema_id": { "type": "string" },
              "pass": { "type": "boolean" },
              "details": {}
            }
          }
        }
      }
    },
    "pricing": {
      "type": "object",
      "required": ["max_price", "computed_payout", "computed_refund", "rule_applied"],
      "properties": {
        "max_price": { "type": "string", "pattern": "^[0-9]+$" },
        "computed_payout": { "type": "string", "pattern": "^[0-9]+$" },
        "computed_refund": { "type": "string", "pattern": "^[0-9]+$" },
        "rule_applied": { "type": "string" }
      }
    },
    "hashes": {
      "type": "object",
      "required": ["request_hash", "response_hash", "receipt_hash"],
      "properties": {
        "request_hash": { "type": "string" },
        "response_hash": { "type": "string" },
        "receipt_hash": { "type": "string" }
      }
    },
    "signatures": {
      "type": "object",
      "properties": {
        "gateway_signature": { "type": "string" }
      }
    }
  }
}
```
