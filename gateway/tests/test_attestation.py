"""Tests for multi-attestation (Buyer + Seller + Gateway)."""

from eth_account import Account

from gateway.app.attestation import (
    AttestationStore,
    attestation_store,
    sign_receipt_hash,
    verify_receipt_signature,
)

# Test keys (DO NOT use in production)
_BUYER_KEY = "0x" + "b" * 64
_SELLER_KEY = "0x" + "5" * 64
_GATEWAY_KEY = "0x" + "a" * 64

_BUYER_ADDR = Account.from_key(_BUYER_KEY).address
_SELLER_ADDR = Account.from_key(_SELLER_KEY).address
_GATEWAY_ADDR = Account.from_key(_GATEWAY_KEY).address

_RECEIPT_HASH = "0x" + "ab" * 32


# ── Sign / Verify ───────────────────────────────────────────────────────────


def test_sign_and_verify():
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    assert sig.startswith("0x")
    signer = verify_receipt_signature(_RECEIPT_HASH, sig)
    assert signer == _BUYER_ADDR


def test_different_keys_different_sigs():
    sig_buyer = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    sig_seller = sign_receipt_hash(_RECEIPT_HASH, _SELLER_KEY)
    assert sig_buyer != sig_seller


def test_verify_wrong_hash_returns_different_address():
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    wrong_hash = "0x" + "cd" * 32
    signer = verify_receipt_signature(wrong_hash, sig)
    assert signer != _BUYER_ADDR


def test_verify_invalid_signature():
    signer = verify_receipt_signature(_RECEIPT_HASH, "0x00")
    assert signer is None


def test_sign_deterministic():
    sig1 = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    sig2 = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    assert sig1 == sig2


# ── AttestationStore ─────────────────────────────────────────────────────────


def test_add_attestation():
    store = AttestationStore()
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)

    result = store.add_attestation(
        request_id="req_001",
        receipt_hash=_RECEIPT_HASH,
        role="buyer",
        signature=sig,
        expected_address=_BUYER_ADDR,
    )
    assert result["verified"] is True
    assert result["signer"] == _BUYER_ADDR
    assert result["role"] == "buyer"


def test_add_attestation_wrong_address():
    store = AttestationStore()
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)

    result = store.add_attestation(
        request_id="req_001",
        receipt_hash=_RECEIPT_HASH,
        role="buyer",
        signature=sig,
        expected_address=_SELLER_ADDR,  # wrong address
    )
    assert result["verified"] is False


def test_get_attestations_empty():
    store = AttestationStore()
    status = store.get_attestations("req_nonexistent")
    assert status["count"] == 0
    assert status["complete"] is False
    assert status["all_verified"] is True  # vacuously true


def test_full_multi_attestation():
    store = AttestationStore()

    # All three parties sign
    for role, key, addr in [
        ("buyer", _BUYER_KEY, _BUYER_ADDR),
        ("seller", _SELLER_KEY, _SELLER_ADDR),
        ("gateway", _GATEWAY_KEY, _GATEWAY_ADDR),
    ]:
        sig = sign_receipt_hash(_RECEIPT_HASH, key)
        store.add_attestation(
            request_id="req_001",
            receipt_hash=_RECEIPT_HASH,
            role=role,
            signature=sig,
            expected_address=addr,
        )

    status = store.get_attestations("req_001")
    assert status["count"] == 3
    assert status["complete"] is True
    assert status["all_verified"] is True
    assert set(status["parties_signed"]) == {"buyer", "seller", "gateway"}


def test_has_attestation():
    store = AttestationStore()
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    store.add_attestation(
        request_id="req_001",
        receipt_hash=_RECEIPT_HASH,
        role="buyer",
        signature=sig,
    )

    assert store.has_attestation("req_001", "buyer") is True
    assert store.has_attestation("req_001", "seller") is False


# ── API endpoints ────────────────────────────────────────────────────────────


def test_attestation_endpoint_no_receipt():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/receipts/nonexistent/attest",
        json={"role": "buyer", "signature": "0x00"},
    )
    assert resp.status_code == 404


def test_attestation_endpoint_bad_role():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/receipts/nonexistent/attest",
        json={"role": "hacker", "signature": "0x00"},
    )
    # 404 because receipt doesn't exist (checked first)
    assert resp.status_code == 404


def test_get_attestations_endpoint():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    client = TestClient(app)
    resp = client.get("/v1/receipts/nonexistent/attestations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert "attestations" in data


# ── Integration: receipt list/detail includes attestation ────────────────────


def test_receipt_detail_includes_attestations():
    """GET /v1/receipts/{id} includes attestation status."""
    from fastapi.testclient import TestClient
    from gateway.app.main import app
    from gateway.app.receipt import receipt_store
    from gateway.app.models import Receipt

    # Create a test receipt
    receipt = Receipt(
        request_id="req_attest_001",
        hashes={"receipt_hash": _RECEIPT_HASH},
    )
    receipt_store.save(receipt)

    # Add an attestation
    sig = sign_receipt_hash(_RECEIPT_HASH, _BUYER_KEY)
    attestation_store.add_attestation(
        request_id="req_attest_001",
        receipt_hash=_RECEIPT_HASH,
        role="buyer",
        signature=sig,
        expected_address=_BUYER_ADDR,
    )

    client = TestClient(app)
    resp = client.get("/v1/receipts/req_attest_001")
    assert resp.status_code == 200
    data = resp.json()
    assert "attestations" in data
    assert data["attestations"]["count"] == 1
    assert "buyer" in data["attestations"]["parties_signed"]


def test_receipt_list_includes_attestations():
    """GET /v1/receipts includes attestation status per receipt."""
    from fastapi.testclient import TestClient
    from gateway.app.main import app
    from gateway.app.receipt import receipt_store
    from gateway.app.models import Receipt

    # Create a test receipt
    receipt = Receipt(
        request_id="req_attest_list_001",
        hashes={"receipt_hash": _RECEIPT_HASH},
    )
    receipt_store.save(receipt)

    client = TestClient(app)
    resp = client.get("/v1/receipts?limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Find our receipt
    found = [r for r in data if r.get("request_id") == "req_attest_list_001"]
    assert len(found) > 0
    assert "attestations" in found[0]


def test_e2e_multi_attestation_via_api():
    """E2E: all 3 parties attest a receipt via API endpoints."""
    from fastapi.testclient import TestClient
    from gateway.app.main import app
    from gateway.app.receipt import receipt_store
    from gateway.app.models import Receipt

    receipt = Receipt(
        request_id="req_e2e_attest",
        hashes={"receipt_hash": _RECEIPT_HASH},
    )
    receipt_store.save(receipt)

    client = TestClient(app)

    for role, key, addr in [
        ("buyer", _BUYER_KEY, _BUYER_ADDR),
        ("seller", _SELLER_KEY, _SELLER_ADDR),
        ("gateway", _GATEWAY_KEY, _GATEWAY_ADDR),
    ]:
        sig = sign_receipt_hash(_RECEIPT_HASH, key)
        resp = client.post(
            "/v1/receipts/req_e2e_attest/attest",
            json={"role": role, "signature": sig, "address": addr},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True

    # Verify complete status
    resp = client.get("/v1/receipts/req_e2e_attest/attestations")
    assert resp.status_code == 200
    status = resp.json()
    assert status["count"] == 3
    assert status["complete"] is True
    assert status["all_verified"] is True
    assert set(status["parties_signed"]) == {"buyer", "seller", "gateway"}

    # Verify receipt detail includes attestations
    resp = client.get("/v1/receipts/req_e2e_attest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["attestations"]["complete"] is True
