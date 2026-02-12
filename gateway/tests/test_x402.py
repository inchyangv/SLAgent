"""Tests for x402 payment gating flow."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.app.main import app
from gateway.app.receipt import receipt_store
from gateway.app.x402 import create_payment_token


client = TestClient(app)


def _make_payment_header(buyer: str = "0xBUYER", max_price: str = "100000") -> str:
    """Create a valid X-PAYMENT header for testing."""
    nonce = "test-nonce-123"
    token = create_payment_token(path="/v1/call", max_price=max_price, nonce=nonce)
    return json.dumps({
        "token": token,
        "nonce": nonce,
        "max_price": max_price,
        "buyer": buyer,
    })


def test_unpaid_request_returns_402():
    """Request without X-PAYMENT header returns 402."""
    resp = client.post("/v1/call", json={"payload": "test"})
    assert resp.status_code == 402
    data = resp.json()
    assert data["error"] == "Payment Required"
    assert "accepts" in data
    assert data["accepts"][0]["scheme"] == "x402"
    assert data["accepts"][0]["maxAmountRequired"] == "100000"


def test_paid_request_succeeds():
    """Request with valid X-PAYMENT header proceeds."""
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
