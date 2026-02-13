"""Tests for BITE v2 encrypted conditional settlement."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from gateway.app.bite_v2 import (
    BiteV2Engine,
    ConditionResult,
    bite_engine,
    evaluate_budget_condition,
    evaluate_sla_condition,
)
from gateway.app.events import event_store
from gateway.app.main import app

client = TestClient(app)


# ── Condition evaluator unit tests ───────────────────────────────────────────


def test_sla_condition_pass():
    """SLA condition passes when all checks pass."""
    result = evaluate_sla_condition(
        validation_passed=True,
        latency_ms=1500,
        max_latency_ms=5000,
        success=True,
    )
    assert result.passed is True
    assert result.condition_type == "sla_validation"
    assert all(c["passed"] for c in result.checks)


def test_sla_condition_fail_validation():
    """SLA condition fails when validation fails."""
    result = evaluate_sla_condition(
        validation_passed=False,
        latency_ms=1500,
        max_latency_ms=5000,
        success=True,
    )
    assert result.passed is False
    assert "schema_validation" in result.reason_code


def test_sla_condition_fail_latency():
    """SLA condition fails when latency exceeds SLA."""
    result = evaluate_sla_condition(
        validation_passed=True,
        latency_ms=10000,
        max_latency_ms=5000,
        success=True,
    )
    assert result.passed is False
    assert "latency" in result.reason_code


def test_sla_condition_fail_success():
    """SLA condition fails when success is false."""
    result = evaluate_sla_condition(
        validation_passed=True,
        latency_ms=1500,
        success=False,
    )
    assert result.passed is False


def test_budget_condition_pass():
    """Budget condition passes when within budget."""
    result = evaluate_budget_condition(
        price=50000,
        budget_remaining=200000,
        max_step_price=100000,
    )
    assert result.passed is True


def test_budget_condition_fail_over_budget():
    """Budget condition fails when over budget."""
    result = evaluate_budget_condition(
        price=50000,
        budget_remaining=30000,
    )
    assert result.passed is False
    assert "within_budget" in result.reason_code


def test_budget_condition_fail_step_limit():
    """Budget condition fails when exceeding step limit."""
    result = evaluate_budget_condition(
        price=150000,
        budget_remaining=500000,
        max_step_price=100000,
    )
    assert result.passed is False
    assert "within_step_limit" in result.reason_code


# ── BITE v2 Engine unit tests ────────────────────────────────────────────────


def test_engine_encrypt():
    """Engine encrypts terms and returns payload."""
    engine = BiteV2Engine(secret="test-secret")
    terms = {"max_price": "100000", "latency_tiers": [2000, 5000]}

    payload = engine.encrypt_terms(terms=terms)
    assert payload.payload_id.startswith("bite_")
    assert payload.status == "ENCRYPTED"
    assert payload.encrypted_data
    assert payload.encrypted_hash
    assert "max_price" in payload.encrypted_fields


def test_engine_decrypt_condition_met():
    """Engine decrypts when condition passes."""
    engine = BiteV2Engine(secret="test-secret")
    terms = {"max_price": "100000", "buyer_policy": "aggressive"}
    payload = engine.encrypt_terms(terms=terms)

    condition = ConditionResult(
        passed=True, condition_type="sla_validation", checks=[]
    )
    updated, decrypted = engine.evaluate_and_decrypt(
        payload.payload_id, condition, triggered_by="test"
    )
    assert updated.status == "DECRYPTED"
    assert decrypted is not None
    assert decrypted["max_price"] == "100000"
    assert decrypted["buyer_policy"] == "aggressive"
    assert updated.decrypted_at is not None


def test_engine_no_decrypt_condition_failed():
    """Engine does NOT decrypt when condition fails."""
    engine = BiteV2Engine(secret="test-secret")
    terms = {"max_price": "100000"}
    payload = engine.encrypt_terms(terms=terms)

    condition = ConditionResult(
        passed=False,
        condition_type="sla_validation",
        checks=[{"name": "validation", "passed": False}],
        reason_code="CONDITION_FAILED:schema_validation",
    )
    updated, decrypted = engine.evaluate_and_decrypt(
        payload.payload_id, condition
    )
    assert updated.status == "CONDITION_FAILED"
    assert decrypted is None
    assert "schema_validation" in updated.reason_code


def test_engine_mark_settled():
    """Engine marks payload as settled after decrypt."""
    engine = BiteV2Engine(secret="test-secret")
    payload = engine.encrypt_terms(terms={"max_price": "100000"})
    condition = ConditionResult(passed=True, condition_type="sla_validation", checks=[])
    engine.evaluate_and_decrypt(payload.payload_id, condition)

    settled = engine.mark_settled(payload.payload_id)
    assert settled is not None
    assert settled.status == "SETTLED"
    assert settled.settled_at is not None


def test_engine_full_lifecycle():
    """Full lifecycle: encrypt → evaluate → decrypt → settle."""
    engine = BiteV2Engine(secret="lifecycle-test")
    terms = {
        "max_price": "100000",
        "latency_tiers": [2000, 5000],
        "buyer_policy": "standard",
    }

    # 1. Encrypt
    payload = engine.encrypt_terms(terms=terms)
    assert payload.status == "ENCRYPTED"

    # 2. Condition check → pass → decrypt
    condition = evaluate_sla_condition(
        validation_passed=True, latency_ms=1000, success=True
    )
    updated, decrypted = engine.evaluate_and_decrypt(payload.payload_id, condition)
    assert updated.status == "DECRYPTED"
    assert decrypted["max_price"] == "100000"

    # 3. Settle
    settled = engine.mark_settled(payload.payload_id)
    assert settled.status == "SETTLED"


def test_engine_failure_lifecycle():
    """Failure lifecycle: encrypt → condition fails → no decrypt → no settle."""
    engine = BiteV2Engine(secret="fail-test")
    terms = {"max_price": "100000"}

    # 1. Encrypt
    payload = engine.encrypt_terms(terms=terms)
    assert payload.status == "ENCRYPTED"

    # 2. Condition check → fail → no decrypt
    condition = evaluate_sla_condition(
        validation_passed=False, latency_ms=1000, success=True
    )
    updated, decrypted = engine.evaluate_and_decrypt(payload.payload_id, condition)
    assert updated.status == "CONDITION_FAILED"
    assert decrypted is None

    # 3. Cannot settle
    settled = engine.mark_settled(payload.payload_id)
    # mark_settled only works on DECRYPTED payloads
    assert settled.status == "CONDITION_FAILED"  # unchanged


# ── API integration tests ────────────────────────────────────────────────────


def test_api_encrypt():
    """POST /v1/bite/encrypt creates encrypted payload."""
    bite_engine.clear()
    resp = client.post("/v1/bite/encrypt", json={
        "terms": {"max_price": "100000", "buyer_policy": "conservative"},
        "condition_type": "sla_validation",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ENCRYPTED"
    assert data["payload_id"].startswith("bite_")
    assert data["encrypted_hash"]


def test_api_evaluate_pass():
    """POST /v1/bite/evaluate decrypts when condition met."""
    bite_engine.clear()
    event_store.clear()

    # Encrypt
    resp = client.post("/v1/bite/encrypt", json={
        "terms": {"max_price": "100000"},
        "condition_type": "sla_validation",
    })
    payload_id = resp.json()["payload_id"]

    # Evaluate — condition met
    resp = client.post(f"/v1/bite/evaluate/{payload_id}", json={
        "validation_passed": True,
        "latency_ms": 1500,
        "success": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DECRYPTED"
    assert data["condition_passed"] is True
    assert data["decrypted_terms"]["max_price"] == "100000"

    # Check events
    events = event_store.query(kind="bite_v2")
    kinds = [e.kind for e in events]
    assert "bite_v2.encrypted" in kinds
    assert "bite_v2.decrypted" in kinds


def test_api_evaluate_fail():
    """POST /v1/bite/evaluate does NOT decrypt when condition fails."""
    bite_engine.clear()
    event_store.clear()

    # Encrypt
    resp = client.post("/v1/bite/encrypt", json={
        "terms": {"max_price": "100000"},
        "condition_type": "sla_validation",
    })
    payload_id = resp.json()["payload_id"]

    # Evaluate — condition fails
    resp = client.post(f"/v1/bite/evaluate/{payload_id}", json={
        "validation_passed": False,
        "latency_ms": 1500,
        "success": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CONDITION_FAILED"
    assert data["condition_passed"] is False
    assert "decrypted_terms" not in data
    assert data["reason_code"]

    # Check events
    events = event_store.query(kind="bite_v2")
    kinds = [e.kind for e in events]
    assert "bite_v2.condition_failed" in kinds


def test_api_settle():
    """POST /v1/bite/settle marks payload as settled."""
    bite_engine.clear()

    # Encrypt + evaluate pass
    resp = client.post("/v1/bite/encrypt", json={"terms": {"max_price": "100000"}})
    payload_id = resp.json()["payload_id"]
    client.post(f"/v1/bite/evaluate/{payload_id}", json={
        "validation_passed": True, "latency_ms": 1000, "success": True,
    })

    # Settle
    resp = client.post(f"/v1/bite/settle/{payload_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SETTLED"


def test_api_list_payloads():
    """GET /v1/bite/payloads returns encrypted payloads."""
    bite_engine.clear()
    client.post("/v1/bite/encrypt", json={"terms": {"max_price": "100000"}})
    resp = client.get("/v1/bite/payloads")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_api_get_payload():
    """GET /v1/bite/payloads/{id} returns payload details."""
    bite_engine.clear()
    resp = client.post("/v1/bite/encrypt", json={"terms": {"max_price": "100000"}})
    payload_id = resp.json()["payload_id"]

    resp = client.get(f"/v1/bite/payloads/{payload_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payload_id"] == payload_id
    assert data["encrypted_hash"]
