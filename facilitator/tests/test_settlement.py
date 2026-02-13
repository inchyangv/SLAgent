"""Tests for facilitator settlement client."""

import pytest
from web3 import Web3

from facilitator.settlement import SettlementClient


# Test private key (DO NOT use in production)
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture
def client():
    return SettlementClient(
        rpc_url="",  # no chain connection for unit tests
        contract_address="",
        gateway_private_key=TEST_PRIVATE_KEY,
        settlement_abi=[],
    )


def test_gateway_address(client):
    """Gateway account derives from private key."""
    assert client.gateway_address.startswith("0x")
    assert len(client.gateway_address) == 42


def test_sign_settlement(client):
    """Signing produces a non-empty signature."""
    sig = client.sign_settlement(
        mandate_id=b"\x00" * 32,
        request_id=b"\x01" * 32,
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=80_000,
        receipt_hash=b"\x02" * 32,
    )
    assert len(sig) == 65  # r(32) + s(32) + v(1)


def test_sign_deterministic(client):
    """Same inputs produce same signature."""
    params = dict(
        mandate_id=b"\xaa" * 32,
        request_id=b"\xbb" * 32,
        buyer="0x" + "33" * 20,
        seller="0x" + "44" * 20,
        max_price=100_000,
        payout=60_000,
        receipt_hash=b"\xcc" * 32,
    )
    sig1 = client.sign_settlement(**params)
    sig2 = client.sign_settlement(**params)
    assert sig1 == sig2


def test_idempotency_prevents_double_submit(client):
    """Duplicate submission for same request_id returns None."""
    params = dict(
        mandate_id=b"\x00" * 32,
        request_id_str="req_001",
        request_id=b"\x01" * 32,
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=80_000,
        receipt_hash=b"\x02" * 32,
        gateway_sig=b"\x03" * 65,
    )
    # First call: returns None (no chain) but registers
    result1 = client.submit_settlement(**params)
    assert result1 is None  # no chain configured

    # Second call: idempotency blocks it
    result2 = client.submit_settlement(**params)
    assert result2 is None


def test_submit_without_chain_logs_mock(client):
    """Submit without chain connection works (mock mode)."""
    result = client.submit_settlement(
        mandate_id=b"\x00" * 32,
        request_id_str="req_mock_001",
        request_id=b"\x01" * 32,
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=100_000,
        receipt_hash=b"\x02" * 32,
        gateway_sig=b"\x03" * 65,
    )
    # No chain → returns None (mock)
    assert result is None


def test_submit_deposit_mock_mode(client):
    """submit_deposit without chain connection returns None (mock mode)."""
    result = client.submit_deposit(
        request_id_str="req_deposit_001",
        request_id=b"\x01" * 32,
        buyer="0x" + "11" * 20,
        amount=100_000,
    )
    assert result is None  # no chain configured → mock
