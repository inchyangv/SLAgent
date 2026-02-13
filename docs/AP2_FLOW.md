# AP2 Intent → Authorization → Settlement Pattern

SLAgent-402 implements the AP2 (Agent Payment Protocol) pattern for audit-ready
settlement authorization. All steps use A2A envelopes via `POST /a2a/message`.

## Flow

```
Buyer Agent          Gateway              Contract
     |                  |                    |
     |-- intent.create-->|                    |
     |<- intent.created -|                    |
     |                  |                    |
     |-- intent.authorize->|                  |
     |<- intent.authorize -|                  |
     |                  |                    |
     |-- settlement.execute->|                |
     |                  |--- settle() ------->|
     |<- settlement.execute -|                |
     |                  |                    |
     |-- receipt.issue-->|                    |
     |<- receipt.issue  -|                    |
```

## State Machine

```
CREATED → AUTHORIZED → SETTLED → RECEIPT_ISSUED
CREATED → REJECTED (terminal)
AUTHORIZED → EXPIRED (terminal, if past expires_at)
```

**Key rule:** `settlement.execute` is blocked (HTTP 403) unless a valid,
non-expired authorization exists for the intent.

## Message Types

### 1. intent.create

Buyer proposes a settlement intent.

```json
{
  "a2a_version": "1.0",
  "message_id": "msg-uuid",
  "message_type": "slagent-402.intent.create",
  "sender": "buyer-agent",
  "receiver": "gateway",
  "correlation_id": "corr-uuid",
  "timestamp": "2026-02-14T12:00:00+00:00",
  "payload": {
    "mandate_id": "0xabc123...",
    "buyer": "0x1111...1111",
    "seller": "0x2222...2222",
    "max_price": "100000"
  }
}
```

**Response:** `slagent-402.intent.created` with `intent_id` and `status=CREATED`.

### 2. intent.authorize

Authorizer grants permission to proceed with settlement.

```json
{
  "message_type": "slagent-402.intent.authorize",
  "sender": "buyer-agent",
  "receiver": "gateway",
  "correlation_id": "corr-uuid",
  "payload": {
    "intent_id": "intent_abc123",
    "authorizer": "0x1111...1111",
    "policy_id": "0xabc123...",
    "expires_at": "1739539200"
  }
}
```

**Response:** `slagent-402.intent.authorize` with `authorization_id`.

### 3. settlement.execute

Execute settlement (requires valid authorization).

```json
{
  "message_type": "slagent-402.settlement.execute",
  "sender": "buyer-agent",
  "receiver": "gateway",
  "correlation_id": "corr-uuid",
  "payload": {
    "settlement_id": "settle_xyz789",
    "intent_id": "intent_abc123",
    "authorization_id": "auth_def456"
  }
}
```

**Success:** `slagent-402.settlement.execute` with settlement details.

**Failure (no auth):** HTTP 403, `slagent-402.settlement.blocked` with reason.

### 4. receipt.issue

Issue final receipt with authorization audit trail.

```json
{
  "message_type": "slagent-402.receipt.issue",
  "sender": "gateway",
  "receiver": "buyer-agent",
  "correlation_id": "corr-uuid",
  "payload": {
    "intent_id": "intent_abc123",
    "request_id": "req_001"
  }
}
```

**Response:** `slagent-402.receipt.issue` with `authorized_by`, `authorized_at`, `policy_id`.

## Failure Path: Authorization Expired

```
1. Buyer sends intent.create → intent_id returned
2. Buyer sends intent.authorize with expires_at=past → authorization_id returned
3. Buyer sends settlement.execute with expired auth → HTTP 403, BLOCKED
4. Event ledger records: authorization.settlement_blocked with reason
```

## Event Ledger Entries

| Event Kind | Actor | Data |
|---|---|---|
| `authorization.intent_created` | buyer | intent_id, buyer, seller, max_price |
| `authorization.granted` | authorizer | authorization_id, intent_id, policy_id, expires_at |
| `authorization.rejected` | buyer | intent_id, reason |
| `authorization.settlement_blocked` | buyer | intent_id, authorization_id, reason |
| `authorization.settlement_executed` | gateway | settlement_id, authorized_by, authorized_at, policy_id |
| `authorization.receipt_issued` | gateway | receipt_id, intent_id, authorized_by, policy_id |

## REST Query Endpoints

- `GET /a2a/intents` — list all intents
- `GET /a2a/intents/{intent_id}` — intent + authorization details
- `GET /a2a/authorizations` — list all authorizations
- `GET /v1/events?kind=authorization` — audit trail
