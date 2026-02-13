"""Tests for A2A/AP2 protocol message layer and AP2 intent/authorization flow."""

import time

from fastapi.testclient import TestClient

from gateway.app.a2a.authorization import AuthorizationError, AuthorizationStore, auth_store
from gateway.app.a2a.envelope import (
    create_envelope,
    dispute_open_msg,
    intent_authorize,
    intent_create,
    mandate_request,
    mandate_response,
    parse_envelope,
    receipt_ack,
    receipt_issue,
    receipt_submission,
    settlement_execute,
)
from gateway.app.events import event_store
from gateway.app.main import app

client = TestClient(app)


# ── Envelope Unit Tests ──────────────────────────────────────────────────────


def test_create_envelope_has_required_fields():
    env = create_envelope(
        message_type="test.type",
        sender="agent-a",
        receiver="agent-b",
        payload={"key": "value"},
    )
    assert env["a2a_version"] == "1.0"
    assert env["message_type"] == "test.type"
    assert env["sender"] == "agent-a"
    assert env["receiver"] == "agent-b"
    assert env["payload"] == {"key": "value"}
    assert "message_id" in env
    assert "timestamp" in env
    assert "correlation_id" in env


def test_parse_envelope():
    env = create_envelope(
        message_type="test.type",
        sender="a",
        receiver="b",
        payload={"data": 1},
        correlation_id="corr-123",
    )
    msg_type, payload, corr_id = parse_envelope(env)
    assert msg_type == "test.type"
    assert payload == {"data": 1}
    assert corr_id == "corr-123"


def test_mandate_request_envelope():
    msg = mandate_request(
        sender="buyer",
        receiver="gateway",
        mandate={"max_price": "100000"},
    )
    assert msg["message_type"] == "slagent-402.mandate.request"
    assert msg["payload"]["mandate"]["max_price"] == "100000"


def test_mandate_response_envelope():
    msg = mandate_response(
        sender="gateway",
        receiver="buyer",
        correlation_id="corr-1",
        accepted=True,
        mandate_id="0xabc",
    )
    assert msg["message_type"] == "slagent-402.mandate.response"
    assert msg["payload"]["accepted"] is True


def test_receipt_submission_envelope():
    msg = receipt_submission(
        sender="gateway",
        receiver="buyer",
        receipt={"request_id": "req_001"},
    )
    assert msg["message_type"] == "slagent-402.receipt.submission"


def test_receipt_ack_envelope():
    msg = receipt_ack(
        sender="buyer",
        receiver="gateway",
        correlation_id="corr-2",
        accepted=True,
        request_id="req_001",
    )
    assert msg["message_type"] == "slagent-402.receipt.ack"


def test_dispute_open_envelope():
    msg = dispute_open_msg(
        sender="buyer",
        receiver="gateway",
        request_id="req_001",
        reason="Payout incorrect",
    )
    assert msg["message_type"] == "slagent-402.dispute.open"


# ── AP2 Envelope Constructors ────────────────────────────────────────────────


def test_intent_create_envelope():
    msg = intent_create(
        sender="buyer",
        receiver="gateway",
        intent_id="intent_001",
        mandate_id="0xmandate",
        buyer="0xbuyer",
        seller="0xseller",
        max_price="100000",
    )
    assert msg["message_type"] == "slagent-402.intent.create"
    assert msg["payload"]["intent_id"] == "intent_001"
    assert msg["payload"]["max_price"] == "100000"


def test_intent_authorize_envelope():
    msg = intent_authorize(
        sender="buyer",
        receiver="gateway",
        correlation_id="corr-1",
        intent_id="intent_001",
        authorization_id="auth_001",
        authorizer="0xbuyer",
        policy_id="0xmandate",
    )
    assert msg["message_type"] == "slagent-402.intent.authorize"
    assert msg["payload"]["authorization_id"] == "auth_001"


def test_settlement_execute_envelope():
    msg = settlement_execute(
        sender="gateway",
        receiver="buyer",
        correlation_id="corr-1",
        settlement_id="settle_001",
        intent_id="intent_001",
        authorization_id="auth_001",
    )
    assert msg["message_type"] == "slagent-402.settlement.execute"
    assert msg["payload"]["settlement_id"] == "settle_001"


def test_receipt_issue_envelope():
    msg = receipt_issue(
        sender="gateway",
        receiver="buyer",
        correlation_id="corr-1",
        receipt_id="receipt_001",
        request_id="req_001",
        authorized_by="0xbuyer",
        authorized_at="1739539200",
        policy_id="0xmandate",
    )
    assert msg["message_type"] == "slagent-402.receipt.issue"
    assert msg["payload"]["authorized_by"] == "0xbuyer"


# ── A2A Endpoint Tests (existing) ────────────────────────────────────────────


def test_a2a_mandate_request():
    msg = mandate_request(
        sender="buyer-agent",
        receiver="gateway",
        mandate={"max_price": "100000", "base_pay": "60000"},
    )
    resp = client.post("/a2a/message", json=msg)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_type"] == "slagent-402.mandate.response"
    assert data["payload"]["accepted"] is True


def test_a2a_dispute_open():
    msg = dispute_open_msg(
        sender="buyer-agent",
        receiver="gateway",
        request_id="req_test_001",
    )
    resp = client.post("/a2a/message", json=msg)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_type"] == "slagent-402.dispute.opened"
    assert data["payload"]["status"] == "DISPUTED"


def test_a2a_unknown_type():
    msg = create_envelope(
        message_type="unknown.type",
        sender="test",
        receiver="gateway",
        payload={},
    )
    resp = client.post("/a2a/message", json=msg)
    assert resp.status_code == 400
    data = resp.json()
    assert data["message_type"] == "slagent-402.error"


# ── Authorization Store Unit Tests ───────────────────────────────────────────


def test_auth_store_create_intent():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc",
        buyer="0xbuyer",
        seller="0xseller",
        max_price="100000",
        created_by="buyer-agent",
    )
    assert intent.intent_id.startswith("intent_")
    assert intent.status == "CREATED"
    assert intent.mandate_id == "0xabc"


def test_auth_store_authorize_intent():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    auth = store.authorize_intent(
        intent_id=intent.intent_id,
        authorizer="0xbuyer",
        policy_id="0xabc",
    )
    assert auth.authorization_id.startswith("auth_")
    assert auth.status == "ACTIVE"
    assert intent.status == "AUTHORIZED"


def test_auth_store_reject_intent():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    rejected = store.reject_intent(intent.intent_id, "too expensive")
    assert rejected.status == "REJECTED"


def test_auth_store_validate_settlement_success():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    auth = store.authorize_intent(
        intent_id=intent.intent_id, authorizer="0xb",
    )
    ok, reason = store.validate_for_settlement(intent.intent_id, auth.authorization_id)
    assert ok is True
    assert reason == "OK"


def test_auth_store_settlement_blocked_no_auth():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    ok, reason = store.validate_for_settlement(intent.intent_id, "auth_nonexistent")
    assert ok is False
    assert "CREATED" in reason  # intent still in CREATED state


def test_auth_store_settlement_blocked_expired():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    auth = store.authorize_intent(
        intent_id=intent.intent_id,
        authorizer="0xb",
        expires_at=time.time() - 100,  # already expired
    )
    ok, reason = store.validate_for_settlement(intent.intent_id, auth.authorization_id)
    assert ok is False
    assert "expired" in reason.lower()


def test_auth_store_mark_settled():
    store = AuthorizationStore()
    intent = store.create_intent(
        mandate_id="0xabc", buyer="0xb", seller="0xs", max_price="100000",
    )
    auth = store.authorize_intent(intent_id=intent.intent_id, authorizer="0xb")
    store.mark_settled(intent.intent_id, auth.authorization_id)
    assert intent.status == "SETTLED"
    assert auth.status == "CONSUMED"


# ── AP2 Integration Tests (full flow via /a2a/message) ────────────────────────


def _create_intent_via_api() -> dict:
    """Helper: create intent and return response payload."""
    msg = create_envelope(
        message_type="slagent-402.intent.create",
        sender="buyer-agent",
        receiver="gateway",
        payload={
            "mandate_id": "0xtest_mandate",
            "buyer": "0xbuyer",
            "seller": "0xseller",
            "max_price": "100000",
        },
    )
    resp = client.post("/a2a/message", json=msg)
    assert resp.status_code == 200
    return resp.json()


def test_ap2_intent_create():
    auth_store.clear()
    data = _create_intent_via_api()
    assert data["message_type"] == "slagent-402.intent.created"
    assert data["payload"]["status"] == "CREATED"
    assert data["payload"]["intent_id"].startswith("intent_")


def test_ap2_full_flow_success():
    """Full AP2 flow: intent → authorize → settle → receipt."""
    auth_store.clear()
    event_store.clear()

    # 1. Create intent
    data = _create_intent_via_api()
    intent_id = data["payload"]["intent_id"]
    corr_id = data["correlation_id"]

    # 2. Authorize intent
    auth_msg = create_envelope(
        message_type="slagent-402.intent.authorize",
        sender="buyer-agent",
        receiver="gateway",
        correlation_id=corr_id,
        payload={
            "intent_id": intent_id,
            "authorizer": "0xbuyer",
            "policy_id": "0xtest_mandate",
        },
    )
    resp = client.post("/a2a/message", json=auth_msg)
    assert resp.status_code == 200
    auth_data = resp.json()
    assert auth_data["message_type"] == "slagent-402.intent.authorize"
    authorization_id = auth_data["payload"]["authorization_id"]

    # 3. Execute settlement
    settle_msg = create_envelope(
        message_type="slagent-402.settlement.execute",
        sender="buyer-agent",
        receiver="gateway",
        correlation_id=corr_id,
        payload={
            "intent_id": intent_id,
            "authorization_id": authorization_id,
        },
    )
    resp = client.post("/a2a/message", json=settle_msg)
    assert resp.status_code == 200
    settle_data = resp.json()
    assert settle_data["message_type"] == "slagent-402.settlement.execute"

    # 4. Issue receipt
    receipt_msg = create_envelope(
        message_type="slagent-402.receipt.issue",
        sender="buyer-agent",
        receiver="gateway",
        correlation_id=corr_id,
        payload={
            "intent_id": intent_id,
            "request_id": "req_ap2_test",
        },
    )
    resp = client.post("/a2a/message", json=receipt_msg)
    assert resp.status_code == 200
    receipt_data = resp.json()
    assert receipt_data["message_type"] == "slagent-402.receipt.issue"
    assert receipt_data["payload"]["authorized_by"] == "0xbuyer"
    assert receipt_data["payload"]["policy_id"] == "0xtest_mandate"

    # Verify event ledger
    events = event_store.query(kind="authorization")
    kinds = [e.kind for e in events]
    assert "authorization.intent_created" in kinds
    assert "authorization.granted" in kinds
    assert "authorization.settlement_executed" in kinds
    assert "authorization.receipt_issued" in kinds


def test_ap2_settlement_blocked_without_auth():
    """Settlement blocked when no authorization exists."""
    auth_store.clear()

    # Create intent but don't authorize
    data = _create_intent_via_api()
    intent_id = data["payload"]["intent_id"]

    # Try to settle without authorization
    settle_msg = create_envelope(
        message_type="slagent-402.settlement.execute",
        sender="buyer-agent",
        receiver="gateway",
        payload={
            "intent_id": intent_id,
            "authorization_id": "auth_nonexistent",
        },
    )
    resp = client.post("/a2a/message", json=settle_msg)
    assert resp.status_code == 403
    data = resp.json()
    assert data["message_type"] == "slagent-402.settlement.blocked"
    assert data["payload"]["status"] == "BLOCKED"


def test_ap2_settlement_blocked_expired_auth():
    """Settlement blocked when authorization has expired."""
    auth_store.clear()

    # Create intent
    data = _create_intent_via_api()
    intent_id = data["payload"]["intent_id"]

    # Authorize with already-expired time
    auth_msg = create_envelope(
        message_type="slagent-402.intent.authorize",
        sender="buyer-agent",
        receiver="gateway",
        payload={
            "intent_id": intent_id,
            "authorizer": "0xbuyer",
            "expires_at": str(time.time() - 100),  # already expired
        },
    )
    resp = client.post("/a2a/message", json=auth_msg)
    assert resp.status_code == 200
    authorization_id = resp.json()["payload"]["authorization_id"]

    # Try to settle with expired auth
    settle_msg = create_envelope(
        message_type="slagent-402.settlement.execute",
        sender="buyer-agent",
        receiver="gateway",
        payload={
            "intent_id": intent_id,
            "authorization_id": authorization_id,
        },
    )
    resp = client.post("/a2a/message", json=settle_msg)
    assert resp.status_code == 403
    data = resp.json()
    assert data["message_type"] == "slagent-402.settlement.blocked"
    assert "expired" in data["payload"]["reason"].lower()


def test_ap2_intent_reject():
    """Intent can be rejected."""
    auth_store.clear()

    data = _create_intent_via_api()
    intent_id = data["payload"]["intent_id"]

    reject_msg = create_envelope(
        message_type="slagent-402.intent.reject",
        sender="buyer-agent",
        receiver="gateway",
        payload={
            "intent_id": intent_id,
            "reason": "Terms unacceptable",
        },
    )
    resp = client.post("/a2a/message", json=reject_msg)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_type"] == "slagent-402.intent.rejected"
    assert data["payload"]["status"] == "REJECTED"


def test_ap2_list_intents():
    """REST endpoint lists intents."""
    auth_store.clear()
    _create_intent_via_api()
    resp = client.get("/a2a/intents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_ap2_get_intent_detail():
    """REST endpoint returns intent with authorization."""
    auth_store.clear()
    data = _create_intent_via_api()
    intent_id = data["payload"]["intent_id"]

    resp = client.get(f"/a2a/intents/{intent_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["intent_id"] == intent_id
