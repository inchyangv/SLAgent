"""Integration tests for settlement_client WDK → local key fallback paths.

Tests:
- WDK sign_bytes failure → local key signing succeeds
- WDK completely unavailable → local key signing succeeds
- Both WDK and local key unavailable → appropriate error
- Concurrent settle_request calls (no race conditions)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.app.settlement_client import settle_request, _sign_settlement


@pytest.fixture(autouse=True)
def reset_settlement_client(monkeypatch):
    """Reset singleton between tests."""
    import gateway.app.settlement_client as sc
    sc._client = None
    sc._gateway_wdk_wallet = None
    monkeypatch.setattr(sc.settings, "chain_rpc_url", "")
    monkeypatch.setattr(sc.settings, "settlement_contract", "")
    monkeypatch.setattr(sc.settings, "gateway_private_key", "")
    yield
    sc._client = None
    sc._gateway_wdk_wallet = None


# ── Helper fixtures ──────────────────────────────────────────────────────────

DUMMY_BUYER = "0x" + "11" * 20
DUMMY_SELLER = "0x" + "22" * 20
DUMMY_RECEIPT_HASH = "0x" + "aa" * 32


def _make_mock_wdk(sign_bytes_side_effect=None, sign_bytes_return="0x" + "cc" * 65):
    """Create a mock WDKWallet with controllable sign_bytes behavior."""
    wdk = MagicMock()
    if sign_bytes_side_effect:
        wdk.sign_bytes = AsyncMock(side_effect=sign_bytes_side_effect)
    else:
        wdk.sign_bytes = AsyncMock(return_value=sign_bytes_return)
    wdk.ensure_wallet_loaded = AsyncMock(return_value="0x" + "77" * 20)
    return wdk


# ── WDK failure → local key fallback ────────────────────────────────────────

@pytest.mark.asyncio
async def test_settle_mock_mode_no_key():
    """settle_request returns mock result when no signing key is available."""
    result = await settle_request(
        request_id="req_fallback_001",
        mandate_id="mandate_test",
        buyer=DUMMY_BUYER,
        seller=DUMMY_SELLER,
        max_price=100_000,
        payout=80_000,
        receipt_hash=DUMMY_RECEIPT_HASH,
    )
    assert result["tx_hash"] is None
    assert result["gateway_signature"] == ""


@pytest.mark.asyncio
async def test_wdk_sign_fails_uses_local_key_if_available():
    """When WDK sign_bytes raises, _sign_settlement falls back to client.sign_settlement."""
    import gateway.app.settlement_client as sc
    from web3 import Web3

    mock_wdk = _make_mock_wdk(sign_bytes_side_effect=RuntimeError("WDK unavailable"))

    # Minimal mock SettlementClient with sign_settlement support
    mock_client = MagicMock()
    mock_client.gateway_address = "0x" + "55" * 20
    mock_client.sign_settlement = MagicMock(return_value=b"\xcc" * 65)

    with patch.object(sc, "_get_gateway_wdk_wallet", return_value=mock_wdk):
        mandate_id_bytes = Web3.keccak(text="mandate_test")
        request_id_bytes = Web3.keccak(text="req_fb_002")
        sig, addr = await _sign_settlement(
            client=mock_client,
            mandate_id_bytes=mandate_id_bytes,
            request_id_bytes=request_id_bytes,
            buyer_addr=Web3.to_checksum_address(DUMMY_BUYER),
            seller_addr=Web3.to_checksum_address(DUMMY_SELLER),
            max_price=100_000,
            payout=80_000,
            receipt_hash_bytes=bytes.fromhex(DUMMY_RECEIPT_HASH[2:]),
        )

    assert sig == b"\xcc" * 65
    assert addr == mock_client.gateway_address
    mock_wdk.sign_bytes.assert_awaited_once()
    mock_client.sign_settlement.assert_called_once()


@pytest.mark.asyncio
async def test_wdk_unavailable_uses_local_key():
    """When WDK is None, _sign_settlement goes straight to local key."""
    import gateway.app.settlement_client as sc
    from web3 import Web3

    mock_client = MagicMock()
    mock_client.gateway_address = "0x" + "44" * 20
    mock_client.sign_settlement = MagicMock(return_value=b"\xbb" * 65)

    with patch.object(sc, "_get_gateway_wdk_wallet", return_value=None):
        mandate_id_bytes = Web3.keccak(text="mandate_fallback")
        request_id_bytes = Web3.keccak(text="req_fb_003")
        sig, addr = await _sign_settlement(
            client=mock_client,
            mandate_id_bytes=mandate_id_bytes,
            request_id_bytes=request_id_bytes,
            buyer_addr=Web3.to_checksum_address(DUMMY_BUYER),
            seller_addr=Web3.to_checksum_address(DUMMY_SELLER),
            max_price=100_000,
            payout=80_000,
            receipt_hash_bytes=bytes.fromhex(DUMMY_RECEIPT_HASH[2:]),
        )

    assert sig == b"\xbb" * 65
    assert addr == mock_client.gateway_address
    mock_client.sign_settlement.assert_called_once()


@pytest.mark.asyncio
async def test_both_wdk_and_local_key_fail_raises():
    """When both WDK and local key fail, an exception propagates."""
    import gateway.app.settlement_client as sc
    from web3 import Web3

    mock_wdk = _make_mock_wdk(sign_bytes_side_effect=RuntimeError("WDK down"))

    mock_client = MagicMock()
    mock_client.gateway_address = ""
    mock_client.sign_settlement = MagicMock(side_effect=RuntimeError("no key"))

    with patch.object(sc, "_get_gateway_wdk_wallet", return_value=mock_wdk):
        with pytest.raises(RuntimeError, match="no key"):
            mandate_id_bytes = Web3.keccak(text="mandate_both_fail")
            request_id_bytes = Web3.keccak(text="req_fb_004")
            await _sign_settlement(
                client=mock_client,
                mandate_id_bytes=mandate_id_bytes,
                request_id_bytes=request_id_bytes,
                buyer_addr=Web3.to_checksum_address(DUMMY_BUYER),
                seller_addr=Web3.to_checksum_address(DUMMY_SELLER),
                max_price=100_000,
                payout=80_000,
                receipt_hash_bytes=bytes.fromhex(DUMMY_RECEIPT_HASH[2:]),
            )


# ── Concurrent settle requests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_settle_requests_no_race():
    """3 concurrent settle_request calls should all return without race conditions."""
    tasks = [
        settle_request(
            request_id=f"req_concurrent_{i:03d}",
            mandate_id="mandate_test",
            buyer=DUMMY_BUYER,
            seller=DUMMY_SELLER,
            max_price=100_000,
            payout=80_000,
            receipt_hash=DUMMY_RECEIPT_HASH,
        )
        for i in range(3)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 3
    for r in results:
        assert "tx_hash" in r
        assert "gateway_signature" in r
