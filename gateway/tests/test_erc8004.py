"""Tests for ERC-8004 orchestration adapter (mock mode)."""

from gateway.app.erc8004 import ERC8004Adapter


def _make_adapter() -> ERC8004Adapter:
    """Create a fresh mock-mode adapter for testing."""
    adapter = ERC8004Adapter()
    assert adapter.mock_mode is True
    return adapter


# ── Agent Registration ──────────────────────────────────────────────────────


def test_register_agent():
    adapter = _make_adapter()
    result = adapter.register_agent("https://seller.example.com/agent.json")
    assert result["mode"] == "mock"
    assert result["agent_id"] == 1


def test_register_multiple_agents():
    adapter = _make_adapter()
    r1 = adapter.register_agent("https://buyer.example.com/agent.json")
    r2 = adapter.register_agent("https://seller.example.com/agent.json")
    assert r1["agent_id"] == 1
    assert r2["agent_id"] == 2


# ── Validation Recording ────────────────────────────────────────────────────


def test_record_validation():
    adapter = _make_adapter()
    result = adapter.record_validation("req_001", "0xabc123")
    assert result["mode"] == "mock"
    assert "req_001" in adapter._mock_validations


def test_submit_validation_result_pass():
    adapter = _make_adapter()
    adapter.record_validation("req_001", "0xabc123")
    result = adapter.submit_validation_result("0xabc123", passed=True, tag="sla-compliance")
    assert result["mode"] == "mock"
    assert adapter._mock_validations["req_001"]["response"] == 100
    assert adapter._mock_validations["req_001"]["tag"] == "sla-compliance"


def test_submit_validation_result_fail():
    adapter = _make_adapter()
    adapter.record_validation("req_002", "0xdef456")
    result = adapter.submit_validation_result("0xdef456", passed=False, tag="schema-fail")
    assert result["mode"] == "mock"
    assert adapter._mock_validations["req_002"]["response"] == 0


# ── Reputation Recording ────────────────────────────────────────────────────


def test_record_reputation():
    adapter = _make_adapter()
    result = adapter.record_reputation("req_001")
    assert result["mode"] == "mock"
    assert len(adapter._mock_reputations) == 1
    assert adapter._mock_reputations[0]["request_id"] == "req_001"


# ── Agent ID Lookup ─────────────────────────────────────────────────────────


def test_get_agent_id_mock():
    adapter = _make_adapter()
    assert adapter.get_agent_id("0x1111111111111111111111111111111111111111") == 0


# ── Status ──────────────────────────────────────────────────────────────────


def test_adapter_status():
    adapter = _make_adapter()
    status = adapter.get_status()
    assert status["enabled"] is False
    assert status["mode"] == "mock"


# ── Full Lifecycle (Mock) ───────────────────────────────────────────────────


def test_full_lifecycle_mock():
    adapter = _make_adapter()

    # 1. Register agents
    r1 = adapter.register_agent("https://buyer.example.com/agent.json")
    r2 = adapter.register_agent("https://seller.example.com/agent.json")
    assert r1["agent_id"] == 1
    assert r2["agent_id"] == 2

    # 2. Record validation
    receipt_hash = "receipt_hash_001"
    adapter.record_validation("req_001", receipt_hash)

    # 3. Submit validation result
    adapter.submit_validation_result(receipt_hash, passed=True, tag="sla-compliance")

    # 4. Record reputation
    adapter.record_reputation("req_001")

    # Verify state
    assert len(adapter._mock_agents) == 2
    assert adapter._mock_validations["req_001"]["response"] == 100
    assert len(adapter._mock_reputations) == 1
