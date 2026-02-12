# API — SLA Mandate & Receipt Schemas

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

## 3. Hashing Rules

### Canonical JSON Serialization

1. **Sort keys alphabetically** at every nesting level.
2. **No whitespace** (compact JSON: `separators=(',', ':')` in Python).
3. **UTF-8 encoding**.
4. **String amounts**: all token amounts are strings of decimal digits (no leading zeros except `"0"`).

### Mandate ID Computation

```
mandate_id = keccak256(canonical_json(mandate_payload_without_signatures_and_id))
```

Fields excluded from hashing:
- `mandate_id` (computed)
- `seller_signature`
- `buyer_signature`

### Receipt Hash Computation

```
receipt_hash = keccak256(canonical_json(receipt_payload_without_hashes_and_signatures))
```

Fields excluded from hashing:
- `hashes` (contains the computed hash)
- `signatures`

## 4. Test Vectors

See `gateway/app/hashing.py` and `gateway/tests/test_hashing.py` for reference
implementation and test vectors.
