"""Tests for gateway settlement_client (deposit + settle wrappers)."""

import pytest
from unittest.mock import patch, MagicMock

from gateway.app.settlement_client import submit_deposit, settle_request, get_settlement_client


@pytest.fixture(autouse=True)
def reset_client():
    """Reset singleton settlement client between tests."""
    import gateway.app.settlement_client as sc
    sc._client = None
    yield
    sc._client = None


def test_submit_deposit_mock_mode():
    """submit_deposit returns mock result when no chain configured."""
    result = submit_deposit(
        request_id="req_test_001",
        buyer="0x" + "11" * 20,
        amount=100_000,
    )
    assert result["mode"] == "mock"
    assert result["tx_hash"] is None


def test_submit_deposit_with_invalid_buyer():
    """submit_deposit normalizes invalid buyer to zero-address."""
    result = submit_deposit(
        request_id="req_test_002",
        buyer="not-an-address",
        amount=100_000,
    )
    # Should not crash, just warn and use zero-address
    assert result["mode"] == "mock"


def test_settle_request_mock_mode():
    """settle_request returns mock result when no chain configured."""
    result = settle_request(
        request_id="req_test_003",
        mandate_id="mandate_test",
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=80_000,
        receipt_hash="0x" + "aa" * 32,
    )
    # No key → signing skipped
    assert result["gateway_signature"] == ""
    assert result["tx_hash"] is None


def test_deposit_then_settle_sequence():
    """Deposit and settle can be called in sequence without errors."""
    dep = submit_deposit(
        request_id="req_seq_001",
        buyer="0x" + "11" * 20,
        amount=100_000,
    )
    assert dep["mode"] == "mock"

    settle = settle_request(
        request_id="req_seq_001",
        mandate_id="mandate_seq",
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=100_000,
        receipt_hash="0x" + "bb" * 32,
    )
    assert settle["tx_hash"] is None
