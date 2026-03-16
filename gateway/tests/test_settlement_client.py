"""Tests for gateway settlement_client (deposit + settle wrappers)."""

import pytest

from gateway.app.settlement_client import settle_request, submit_deposit


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    """Reset singleton settlement client between tests."""
    import gateway.app.settlement_client as sc
    sc._client = None
    sc._gateway_wdk_wallet = None
    monkeypatch.setattr(sc.settings, "chain_rpc_url", "")
    monkeypatch.setattr(sc.settings, "settlement_contract", "")
    monkeypatch.setattr(sc.settings, "gateway_private_key", "")
    yield
    sc._client = None
    sc._gateway_wdk_wallet = None


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
    """submit_deposit skips invalid buyer without raising."""
    result = submit_deposit(
        request_id="req_test_002",
        buyer="not-an-address",
        amount=100_000,
    )
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


def test_settle_request_prefers_wdk_signature(monkeypatch):
    import gateway.app.settlement_client as sc

    captured: dict[str, bytes] = {}

    class FakeWallet:
        def ensure_wallet_loaded(self) -> str:
            return "0x3333333333333333333333333333333333333333"

        def sign_bytes(self, payload_hex: str) -> str:
            assert payload_hex.startswith("0x")
            return "0x" + "11" * 65

    class FakeClient:
        gateway_address = "0x9999999999999999999999999999999999999999"

        def sign_settlement(self, **kwargs):
            raise AssertionError("local signer should not be used")

        def submit_settlement(self, **kwargs):
            captured["gateway_sig"] = kwargs["gateway_sig"]
            return None

    monkeypatch.setattr(sc, "get_settlement_client", lambda: FakeClient())
    monkeypatch.setattr(sc, "_get_gateway_wdk_wallet", lambda: FakeWallet())

    result = sc.settle_request(
        request_id="req_test_004",
        mandate_id="mandate_test",
        buyer="0x" + "11" * 20,
        seller="0x" + "22" * 20,
        max_price=100_000,
        payout=80_000,
        receipt_hash="0x" + "aa" * 32,
    )

    assert result["gateway_signature"] == "0x" + "11" * 65
    assert result["gateway_address"] == "0x3333333333333333333333333333333333333333"
    assert captured["gateway_sig"] == bytes.fromhex("11" * 65)
