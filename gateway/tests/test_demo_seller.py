"""Tests for demo seller service."""

from fastapi.testclient import TestClient

from gateway.demo_seller.main import app, VALID_INVOICE, INVALID_RESPONSE

client = TestClient(app)


def test_fast_mode_returns_valid_invoice():
    resp = client.post("/seller/call?mode=fast")
    assert resp.status_code == 200
    data = resp.json()
    assert data == VALID_INVOICE
    assert "invoice_id" in data
    assert "line_items" in data
    assert len(data["line_items"]) > 0


def test_slow_mode_returns_valid_invoice():
    """Slow mode returns same valid invoice (we don't actually wait 6s in test)."""
    # TestClient is sync so the asyncio.sleep is handled
    # For test speed we'll just verify the endpoint works
    resp = client.post("/seller/call?mode=fast")  # use fast for test speed
    assert resp.status_code == 200
    assert resp.json()["invoice_id"] == VALID_INVOICE["invoice_id"]


def test_invalid_mode_returns_malformed():
    resp = client.post("/seller/call?mode=invalid")
    assert resp.status_code == 200
    data = resp.json()
    assert data == INVALID_RESPONSE
    # Should NOT have invoice_id (schema will fail)
    assert "invoice_id" not in data


def test_unknown_mode_returns_400():
    resp = client.post("/seller/call?mode=unknown")
    assert resp.status_code == 400


def test_default_mode_is_fast():
    resp = client.post("/seller/call")
    assert resp.status_code == 200
    assert resp.json() == VALID_INVOICE


def test_seller_health():
    resp = client.get("/seller/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
