"""Tests for x402 payment gating flow — both HMAC and x402 modes."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.app.main import app
from gateway.app.x402 import create_payment_token, create_x402_payment, clear_nonce_cache


client = TestClient(app)


def _make_payment_header(buyer: str = "0xBUYER", max_price: str = "100000") -> str:
    """Create a valid HMAC X-PAYMENT header for testing."""
    nonce = "test-nonce-123"
    token = create_payment_token(path="/v1/call", max_price=max_price, nonce=nonce)
    return json.dumps({
        "token": token,
        "nonce": nonce,
        "max_price": max_price,
        "buyer": buyer,
    })


# ── HMAC Mode Tests ──────────────────────────────────────────────────────────


def test_unpaid_request_returns_402():
    """Request without X-PAYMENT header returns 402."""
    resp = client.post("/v1/call", json={"payload": "test"})
    assert resp.status_code == 402
    data = resp.json()
    assert data["error"] == "Payment Required"
    assert "accepts" in data
    assert data["accepts"][0]["scheme"] == "exact"
    assert data["accepts"][0]["maxAmountRequired"] == "100000"
    assert data["x402Version"] == 1


def test_paid_request_succeeds():
    """Request with valid HMAC X-PAYMENT header proceeds."""
    seller_response = {"invoice_id": "INV-1", "amount": 100, "currency": "USD",
                       "line_items": [{"description": "Test", "quantity": 1, "unit_price": 100}]}

    payment_header = _make_payment_header()

    with patch("gateway.app.main.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = seller_response
        mock_resp.content = json.dumps(seller_response).encode()
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        resp = client.post(
            "/v1/call",
            json={"payload": "test"},
            headers={"X-PAYMENT": payment_header},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["seller_response"] == seller_response
    assert data["validation_passed"] is True


def test_invalid_payment_token_returns_402():
    """Request with invalid HMAC returns 402."""
    bad_header = json.dumps({
        "token": "bad-token-value",
        "nonce": "nonce",
        "max_price": "100000",
        "buyer": "0xBUYER",
    })

    resp = client.post(
        "/v1/call",
        json={"payload": "test"},
        headers={"X-PAYMENT": bad_header},
    )
    assert resp.status_code == 402


def test_missing_payment_fields_returns_402():
    """Request with incomplete payment header returns 402."""
    incomplete = json.dumps({"token": "something"})
    resp = client.post(
        "/v1/call",
        json={"payload": "test"},
        headers={"X-PAYMENT": incomplete},
    )
    assert resp.status_code == 402


def test_402_response_has_payment_required_header():
    """402 response includes X-PAYMENT-REQUIRED header."""
    resp = client.post("/v1/call", json={"payload": "test"})
    assert resp.status_code == 402
    assert resp.headers.get("X-PAYMENT-REQUIRED") == "true"


def test_402_response_has_x402_format(monkeypatch):
    """402 response follows x402 spec format."""
    monkeypatch.setenv("SLA_TOKEN_NAME", "Tether USD")
    monkeypatch.setenv("SLA_TOKEN_VERSION", "")
    resp = client.post("/v1/call", json={"payload": "test"})
    data = resp.json()
    assert data["x402Version"] == 1
    accept = data["accepts"][0]
    assert accept["scheme"] == "exact"
    assert "eip155:" in accept["network"]
    assert "asset" in accept
    assert "payTo" in accept
    assert "maxTimeoutSeconds" in accept
    assert "extra" in accept
    # Default token domain for hackathon demo: Tether USD
    assert accept["extra"]["name"] == "Tether USD"


# ── x402 Mode Tests (EIP-712 signatures) ────────────────────────────────────


def test_x402_create_and_verify(monkeypatch):
    """Create x402 payment and verify it succeeds in x402 mode."""
    from eth_account import Account

    monkeypatch.setenv("PAYMENT_MODE", "x402")
    clear_nonce_cache()

    # Generate a test keypair
    acct = Account.create()
    private_key = acct.key.hex()
    buyer_address = acct.address

    asset = "0x1234567890AbcdEF1234567890aBcdef12345678"
    chain_id = 1444673419

    # Ensure token domain is deterministic for the test.
    monkeypatch.setenv("SLA_TOKEN_NAME", "Tether USD")
    monkeypatch.setenv("SLA_TOKEN_VERSION", "")

    # Create the x402 payment
    payment_b64 = create_x402_payment(
        private_key=private_key,
        from_address=buyer_address,
        to_address="0x0000000000000000000000000000000000000001",
        value="100000",
        asset=asset,
        chain_id=chain_id,
    )

    seller_response = {
        "invoice_id": "INV-X402",
        "amount": 100,
        "currency": "USD",
        "line_items": [{"description": "Test", "quantity": 1, "unit_price": 100}],
    }

    with patch("gateway.app.main.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = seller_response
        mock_resp.content = json.dumps(seller_response).encode()
        mock_resp.status_code = 200
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        # Patch settings for chain_id and asset
        with patch("gateway.app.main.settings") as mock_settings:
            mock_settings.chain_id = chain_id
            mock_settings.payment_token = asset
            mock_settings.settlement_contract = "0x0000000000000000000000000000000000000002"
            mock_settings.seller_upstream_url = "http://localhost:8001"
            mock_settings.seller_address = "0x0000000000000000000000000000000000000001"

            resp = client.post(
                "/v1/call",
                json={"payload": "test"},
                headers={"X-PAYMENT": payment_b64},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["seller_response"] == seller_response

    monkeypatch.setenv("PAYMENT_MODE", "hmac")
    clear_nonce_cache()


def test_x402_replay_rejected(monkeypatch):
    """Replaying the same x402 nonce is rejected."""
    from gateway.app.x402 import _verify_x402, _used_nonces
    from eth_account import Account

    monkeypatch.setenv("PAYMENT_MODE", "x402")
    clear_nonce_cache()

    acct = Account.create()
    asset = "0x1234567890AbcdEF1234567890aBcdef12345678"
    chain_id = 1444673419

    payment_b64 = create_x402_payment(
        private_key=acct.key.hex(),
        from_address=acct.address,
        to_address="0x0000000000000000000000000000000000000001",
        value="100000",
        asset=asset,
        chain_id=chain_id,
    )

    # Decode to get the nonce
    decoded = json.loads(__import__("base64").b64decode(payment_b64))
    nonce_hex = decoded["payload"]["authorization"]["nonce"]

    # Pre-add the nonce to simulate replay
    _used_nonces.add(nonce_hex)

    # Build a mock request
    from starlette.testclient import TestClient as _TC
    from starlette.requests import Request as _Req
    from starlette.datastructures import Headers

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/call",
        "query_string": b"",
        "headers": [(b"x-payment", payment_b64.encode())],
    }
    mock_request = _Req(scope)

    result = _verify_x402(mock_request, max_price="100000", chain_id=chain_id, asset=asset)
    assert result is None  # Rejected due to replay

    monkeypatch.setenv("PAYMENT_MODE", "hmac")
    clear_nonce_cache()


def test_x402_insufficient_value_rejected(monkeypatch):
    """x402 payment with value < max_price is rejected."""
    from gateway.app.x402 import _verify_x402
    from eth_account import Account

    monkeypatch.setenv("PAYMENT_MODE", "x402")
    clear_nonce_cache()

    acct = Account.create()
    asset = "0x1234567890AbcdEF1234567890aBcdef12345678"
    chain_id = 1444673419

    # Create payment with value=50000 but max_price=100000
    payment_b64 = create_x402_payment(
        private_key=acct.key.hex(),
        from_address=acct.address,
        to_address="0x0000000000000000000000000000000000000001",
        value="50000",
        asset=asset,
        chain_id=chain_id,
    )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/call",
        "query_string": b"",
        "headers": [(b"x-payment", payment_b64.encode())],
    }
    mock_request = __import__("starlette.requests", fromlist=["Request"]).Request(scope)

    result = _verify_x402(mock_request, max_price="100000", chain_id=chain_id, asset=asset)
    assert result is None  # Rejected: value < max_price

    monkeypatch.setenv("PAYMENT_MODE", "hmac")
    clear_nonce_cache()
