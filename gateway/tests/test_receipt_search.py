"""Tests for receipt indexing and search functionality."""

import tempfile
from pathlib import Path

from gateway.app.models import Metrics, PricingResult, Receipt
from gateway.app.receipt import ReceiptStore


def _make_receipt(
    request_id: str,
    buyer: str = "0xBUYER",
    seller: str = "0xSELLER",
    payout: int = 100000,
    refund: int = 0,
    latency_ms: int = 1000,
    validation_pass: bool = True,
    rule_applied: str = "latency_tier_lte_2000",
) -> Receipt:
    return Receipt(
        request_id=request_id,
        buyer=buyer,
        seller=seller,
        metrics=Metrics(latency_ms=latency_ms),
        validation={"overall_pass": validation_pass, "results": []},
        pricing=PricingResult(
            max_price=str(payout + refund),
            computed_payout=str(payout),
            computed_refund=str(refund),
            rule_applied=rule_applied,
        ),
    )


# ── In-memory search ────────────────────────────────────────────────────────


def test_search_by_buyer_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", buyer="0xALICE"))
    store.save(_make_receipt("req_2", buyer="0xBOB"))
    store.save(_make_receipt("req_3", buyer="0xALICE"))

    results = store.search(buyer="0xALICE")
    assert len(results) == 2
    assert all(r.buyer == "0xALICE" for r in results)


def test_search_by_seller_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", seller="0xSELLER_A"))
    store.save(_make_receipt("req_2", seller="0xSELLER_B"))

    results = store.search(seller="0xSELLER_A")
    assert len(results) == 1


def test_search_by_min_payout_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", payout=100000, refund=0))
    store.save(_make_receipt("req_2", payout=60000, refund=40000))
    store.save(_make_receipt("req_3", payout=0, refund=100000))

    results = store.search(min_payout=80000)
    assert len(results) == 1
    assert results[0].request_id == "req_1"


def test_search_by_max_latency_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", latency_ms=500))
    store.save(_make_receipt("req_2", latency_ms=3000))
    store.save(_make_receipt("req_3", latency_ms=8000))

    results = store.search(max_latency_ms=2000)
    assert len(results) == 1
    assert results[0].request_id == "req_1"


def test_search_by_validation_pass_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", validation_pass=True))
    store.save(_make_receipt("req_2", validation_pass=False))

    results = store.search(validation_pass=True)
    assert len(results) == 1
    assert results[0].request_id == "req_1"


def test_search_combined_filters_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", buyer="0xA", payout=100000))
    store.save(_make_receipt("req_2", buyer="0xA", payout=60000, refund=40000))
    store.save(_make_receipt("req_3", buyer="0xB", payout=100000))

    results = store.search(buyer="0xA", min_payout=80000)
    assert len(results) == 1
    assert results[0].request_id == "req_1"


def test_search_pagination_memory():
    store = ReceiptStore()
    for i in range(10):
        store.save(_make_receipt(f"req_{i}"))

    page1 = store.search(limit=3, offset=0)
    page2 = store.search(limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 3
    assert page1[0].request_id != page2[0].request_id


def test_search_no_results_memory():
    store = ReceiptStore()
    store.save(_make_receipt("req_1", buyer="0xA"))
    results = store.search(buyer="0xNONEXISTENT")
    assert len(results) == 0


# ── SQLite search ────────────────────────────────────────────────────────────


def test_search_by_buyer_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = ReceiptStore(db_path=db_path)
        store.save(_make_receipt("req_1", buyer="0xALICE"))
        store.save(_make_receipt("req_2", buyer="0xBOB"))
        store.save(_make_receipt("req_3", buyer="0xALICE"))

        results = store.search(buyer="0xALICE")
        assert len(results) == 2


def test_search_combined_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = ReceiptStore(db_path=db_path)
        store.save(_make_receipt("req_1", buyer="0xA", latency_ms=500, payout=100000))
        store.save(_make_receipt("req_2", buyer="0xA", latency_ms=3000, payout=80000, refund=20000))
        store.save(_make_receipt("req_3", buyer="0xB", latency_ms=500, payout=100000))

        results = store.search(buyer="0xA", max_latency_ms=2000)
        assert len(results) == 1
        assert results[0].request_id == "req_1"


def test_search_validation_pass_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = ReceiptStore(db_path=db_path)
        store.save(_make_receipt("req_1", validation_pass=True))
        store.save(_make_receipt("req_2", validation_pass=False))

        passed = store.search(validation_pass=True)
        failed = store.search(validation_pass=False)
        assert len(passed) == 1
        assert len(failed) == 1


def test_sqlite_indexes_persist():
    """Verify SQLite DB has expected indexes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = ReceiptStore(db_path=db_path)

        cursor = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='receipts'"
        )
        indexes = {row[0] for row in cursor}
        assert "idx_receipts_buyer" in indexes
        assert "idx_receipts_seller" in indexes
        assert "idx_receipts_payout" in indexes
        assert "idx_receipts_latency" in indexes
        assert "idx_receipts_validation" in indexes
        assert "idx_receipts_created" in indexes


# ── API endpoint test ────────────────────────────────────────────────────────


def test_search_endpoint():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    client = TestClient(app)
    resp = client.get("/v1/receipts/search")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "count" in data
    assert "limit" in data
    assert "offset" in data
