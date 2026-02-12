"""Tests for A2A/AP2 protocol message layer."""

from fastapi.testclient import TestClient

from gateway.app.a2a.envelope import (
    create_envelope,
    dispute_open_msg,
    mandate_request,
    mandate_response,
    parse_envelope,
    receipt_ack,
    receipt_submission,
)
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
    assert msg["message_type"] == "sla-pay.mandate.request"
    assert msg["payload"]["mandate"]["max_price"] == "100000"


def test_mandate_response_envelope():
    msg = mandate_response(
        sender="gateway",
        receiver="buyer",
        correlation_id="corr-1",
        accepted=True,
        mandate_id="0xabc",
    )
    assert msg["message_type"] == "sla-pay.mandate.response"
    assert msg["payload"]["accepted"] is True


def test_receipt_submission_envelope():
    msg = receipt_submission(
        sender="gateway",
        receiver="buyer",
        receipt={"request_id": "req_001"},
    )
    assert msg["message_type"] == "sla-pay.receipt.submission"


def test_receipt_ack_envelope():
    msg = receipt_ack(
        sender="buyer",
        receiver="gateway",
        correlation_id="corr-2",
        accepted=True,
        request_id="req_001",
    )
    assert msg["message_type"] == "sla-pay.receipt.ack"


def test_dispute_open_envelope():
    msg = dispute_open_msg(
        sender="buyer",
        receiver="gateway",
        request_id="req_001",
        reason="Payout incorrect",
    )
    assert msg["message_type"] == "sla-pay.dispute.open"


# ── A2A Endpoint Tests ───────────────────────────────────────────────────────


def test_a2a_mandate_request():
    msg = mandate_request(
        sender="buyer-agent",
        receiver="gateway",
        mandate={"max_price": "100000", "base_pay": "60000"},
    )
    resp = client.post("/a2a/message", json=msg)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_type"] == "sla-pay.mandate.response"
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
    assert data["message_type"] == "sla-pay.dispute.opened"
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
    assert data["message_type"] == "sla-pay.error"
