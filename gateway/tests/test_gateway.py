"""Tests for gateway core endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app.main import app
from gateway.app.mandates import mandate_store
from gateway.app.receipt import receipt_store
from gateway.app.x402 import create_payment_token


@pytest.fixture(autouse=True)
def clear_stores():
    receipt_store._cache.clear()
    mandate_store._mandates.clear()
    yield
    receipt_store._cache.clear()
    mandate_store._mandates.clear()


client = TestClient(app)


def _payment_header(buyer: str = "0xBUYER", max_price: str = "100000") -> dict[str, str]:
    """Create headers with a valid X-PAYMENT for testing."""
    nonce = "test-nonce"
    token = create_payment_token(path="/v1/call", max_price=max_price, nonce=nonce)
    header_val = json.dumps({
        "token": token, "nonce": nonce, "max_price": max_price, "buyer": buyer,
    })
    return {"X-PAYMENT": header_val}


def test_health():
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_call_proxy_success():
    """Test that /v1/call proxies to seller and returns metrics + receipt."""
    seller_response = {"invoice_id": "INV-1", "amount": 100, "currency": "USD",
                       "line_items": [{"description": "x", "quantity": 1, "unit_price": 100}]}

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = seller_response
        mock_response.content = json.dumps(seller_response).encode()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post("/v1/call", json={"payload": "test"}, headers=_payment_header())

    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["seller_response"] == seller_response
    assert "metrics" in data
    assert "latency_ms" in data["metrics"]
    assert data["validation_passed"] is True
    assert data["receipt_hash"].startswith("0x")


def test_call_without_payment_returns_402():
    resp = client.post("/v1/call", json={"payload": "test"})
    assert resp.status_code == 402


def test_receipt_not_found():
    resp = client.get("/v1/receipts/nonexistent")
    assert resp.status_code == 404


def test_receipt_storage_and_retrieval():
    """Test receipt is stored and retrievable."""
    seller_response = {"invoice_id": "INV-2", "amount": 50, "currency": "EUR",
                       "line_items": [{"description": "y", "quantity": 2, "unit_price": 25}]}

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = seller_response
        mock_response.content = json.dumps(seller_response).encode()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post("/v1/call", json={"test": True}, headers=_payment_header())
        request_id = resp.json()["request_id"]

    resp2 = client.get(f"/v1/receipts/{request_id}")
    assert resp2.status_code == 200
    receipt = resp2.json()
    assert receipt["request_id"] == request_id
    assert receipt["version"] == "1.0"


def test_list_receipts():
    resp = client.get("/v1/receipts?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# --- Mandate endpoint tests ---


def test_register_mandate():
    mandate = {
        "max_price": "100000",
        "base_pay": "60000",
        "bonus_rules": {"type": "latency_tiers", "tiers": [{"lte_ms": 2000, "payout": "100000"}]},
        "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
    }
    resp = client.post("/v1/mandates", json=mandate)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mandate_id"].startswith("0x")
    assert data["max_price"] == "100000"


def test_get_mandate():
    mandate = {"max_price": "100000", "validators": []}
    resp = client.post("/v1/mandates", json=mandate)
    mid = resp.json()["mandate_id"]
    resp2 = client.get(f"/v1/mandates/{mid}")
    assert resp2.status_code == 200
    assert resp2.json()["mandate_id"] == mid


def test_get_mandate_not_found():
    resp = client.get("/v1/mandates/0xnonexistent")
    assert resp.status_code == 404


def test_list_mandates():
    client.post("/v1/mandates", json={"max_price": "100000", "validators": []})
    resp = client.get("/v1/mandates")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_call_with_mandate_id():
    """Test /v1/call with a registered mandate_id."""
    mandate = {
        "max_price": "100000",
        "base_pay": "60000",
        "bonus_rules": {
            "type": "latency_tiers",
            "tiers": [
                {"lte_ms": 2000, "payout": "100000"},
                {"lte_ms": 5000, "payout": "80000"},
                {"lte_ms": 999999999, "payout": "60000"},
            ],
        },
        "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
    }
    reg = client.post("/v1/mandates", json=mandate)
    mid = reg.json()["mandate_id"]

    seller_response = {"invoice_id": "INV-M", "amount": 100, "currency": "USD",
                       "line_items": [{"description": "x", "quantity": 1, "unit_price": 100}]}

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = seller_response
        mock_response.content = json.dumps(seller_response).encode()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/v1/call",
            json={"mandate_id": mid},
            headers=_payment_header(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mandate_id"] == mid


def test_call_with_unknown_mandate_returns_400():
    """Test /v1/call rejects unknown mandate_id."""
    resp = client.post(
        "/v1/call",
        json={"mandate_id": "0xunknown"},
        headers=_payment_header(),
    )
    assert resp.status_code == 400
    assert "Unknown mandate_id" in resp.json()["detail"]


def test_call_forwards_mode_to_seller():
    """Test that /v1/call forwards mode as query param to seller."""
    seller_response = {"invoice_id": "INV-M", "amount": 100, "currency": "USD",
                       "line_items": [{"description": "x", "quantity": 1, "unit_price": 100}]}

    captured_url = []

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()

        async def capture_post(url, **kwargs):
            captured_url.append(url)
            mock_response = MagicMock()
            mock_response.json.return_value = seller_response
            mock_response.content = json.dumps(seller_response).encode()
            mock_response.status_code = 200
            return mock_response

        mock_client.post = capture_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/v1/call?mode=slow",
            json={"some": "data"},
            headers=_payment_header(),
        )

    assert resp.status_code == 200
    assert len(captured_url) == 1
    assert "mode=slow" in captured_url[0]


def test_demo_run_endpoint_exists():
    """POST /v1/demo/run is accessible when DEMO_MODE=true."""
    resp = client.post("/v1/demo/run", json={"modes": ["fast"]})
    # Endpoint exists (not 404/405) and demo mode is enabled (not 403)
    assert resp.status_code not in (404, 405, 403)


def test_call_mode_from_body():
    """Test mode can come from request body."""
    seller_response = {"invoice_id": "INV-B", "amount": 50, "currency": "EUR",
                       "line_items": [{"description": "y", "quantity": 1, "unit_price": 50}]}

    captured_url = []

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()

        async def capture_post(url, **kwargs):
            captured_url.append(url)
            mock_response = MagicMock()
            mock_response.json.return_value = seller_response
            mock_response.content = json.dumps(seller_response).encode()
            mock_response.status_code = 200
            return mock_response

        mock_client.post = capture_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/v1/call",
            json={"mode": "invalid"},
            headers=_payment_header(),
        )

    assert resp.status_code == 200
    assert "mode=invalid" in captured_url[0]
