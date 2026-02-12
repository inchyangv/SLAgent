"""Tests for gateway core endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app.main import app
from gateway.app.receipt import receipt_store


@pytest.fixture(autouse=True)
def clear_receipts():
    receipt_store._receipts.clear()
    yield
    receipt_store._receipts.clear()


client = TestClient(app)


def test_health():
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_call_proxy_success():
    """Test that /v1/call proxies to seller and returns metrics + receipt."""
    seller_response = {"result": "hello", "mode": "fast"}

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = seller_response
        mock_response.content = json.dumps(seller_response).encode()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post("/v1/call", json={"payload": "test"})

    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["seller_response"] == seller_response
    assert "metrics" in data
    assert "latency_ms" in data["metrics"]
    assert data["validation_passed"] is True
    assert data["receipt_hash"].startswith("0x")


def test_call_invalid_json():
    resp = client.post("/v1/call", content=b"not json", headers={"content-type": "application/json"})
    assert resp.status_code == 400


def test_receipt_not_found():
    resp = client.get("/v1/receipts/nonexistent")
    assert resp.status_code == 404


def test_receipt_storage_and_retrieval():
    """Test receipt is stored and retrievable."""
    seller_response = {"result": "ok"}

    with patch("gateway.app.main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = seller_response
        mock_response.content = json.dumps(seller_response).encode()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.post("/v1/call", json={"test": True})
        request_id = resp.json()["request_id"]

    # Retrieve
    resp2 = client.get(f"/v1/receipts/{request_id}")
    assert resp2.status_code == 200
    receipt = resp2.json()
    assert receipt["request_id"] == request_id
    assert receipt["version"] == "1.0"


def test_list_receipts():
    resp = client.get("/v1/receipts?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
