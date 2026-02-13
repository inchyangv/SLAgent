"""Tests for event ledger."""

from gateway.app.events import Event, EventStore, event_store


# ── EventStore unit tests ────────────────────────────────────────────────────


def test_record_event():
    store = EventStore()
    event = store.record(kind="test.event", actor="gateway", data={"key": "value"})
    assert event.kind == "test.event"
    assert event.actor == "gateway"
    assert event.data == {"key": "value"}
    assert event.event_id != ""
    assert event.ts > 0


def test_query_by_request_id():
    store = EventStore()
    store.record(kind="a", actor="gw", request_id="req1")
    store.record(kind="b", actor="gw", request_id="req2")
    store.record(kind="c", actor="gw", request_id="req1")
    results = store.query(request_id="req1")
    assert len(results) == 2
    assert all(e.request_id == "req1" for e in results)


def test_query_by_mandate_id():
    store = EventStore()
    store.record(kind="a", actor="gw", mandate_id="m1")
    store.record(kind="b", actor="gw", mandate_id="m2")
    results = store.query(mandate_id="m1")
    assert len(results) == 1


def test_query_by_kind_prefix():
    store = EventStore()
    store.record(kind="payment.402_issued", actor="gw")
    store.record(kind="payment.verified", actor="gw")
    store.record(kind="execution.done", actor="gw")
    results = store.query(kind="payment")
    assert len(results) == 2


def test_query_by_actor():
    store = EventStore()
    store.record(kind="a", actor="buyer")
    store.record(kind="b", actor="seller")
    store.record(kind="c", actor="buyer")
    results = store.query(actor="buyer")
    assert len(results) == 2


def test_query_limit():
    store = EventStore()
    for i in range(10):
        store.record(kind=f"e{i}", actor="gw")
    results = store.query(limit=3)
    assert len(results) == 3


def test_list_recent():
    store = EventStore()
    for i in range(5):
        store.record(kind=f"e{i}", actor="gw")
    recent = store.list_recent(limit=3)
    assert len(recent) == 3


def test_export_jsonl():
    store = EventStore()
    store.record(kind="test", actor="gw", data={"x": 1})
    jsonl = store.export_jsonl()
    assert "test" in jsonl
    assert '"x": 1' in jsonl


def test_event_to_dict():
    event = Event(event_id="e1", ts=1700000000.0, kind="test", actor="gw")
    d = event.to_dict()
    assert d["event_id"] == "e1"
    assert "ts_iso" in d


def test_count():
    store = EventStore()
    assert store.count() == 0
    store.record(kind="a", actor="gw")
    assert store.count() == 1


# ── API endpoint tests ──────────────────────────────────────────────────────


def test_events_endpoint():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    event_store.clear()
    event_store.record(kind="test.api", actor="gateway", request_id="req_api_001")

    client = TestClient(app)
    resp = client.get("/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(e["kind"] == "test.api" for e in data["events"])


def test_events_filter_by_request_id():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    event_store.clear()
    event_store.record(kind="a", actor="gw", request_id="req_filter_1")
    event_store.record(kind="b", actor="gw", request_id="req_filter_2")

    client = TestClient(app)
    resp = client.get("/v1/events?request_id=req_filter_1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["events"][0]["request_id"] == "req_filter_1"


def test_events_export():
    from fastapi.testclient import TestClient
    from gateway.app.main import app

    event_store.clear()
    event_store.record(kind="export.test", actor="gw")

    client = TestClient(app)
    resp = client.get("/v1/events/export")
    assert resp.status_code == 200
    assert "export.test" in resp.text
