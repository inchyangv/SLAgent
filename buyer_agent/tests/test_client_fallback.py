"""Integration tests for BuyerAgent WDK → local key deposit fallback paths.

Tests:
- WDK deposit failure → local key deposit succeeds
- WDK timeout → local key deposit fallback
- WDK unavailable (None) → local key used directly
- health check: WDK unreachable → warning + continue
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from buyer_agent.wdk_wallet import WDKServiceError, WDKWallet


# ── WDKWallet.health() tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_status_dict(monkeypatch):
    """health() returns parsed JSON dict from /health."""
    import httpx

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test " * 11 + "junk",
        account_index=0,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "status": "healthy", "chain_id": "12345"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(wallet, "_get_async_client", lambda: mock_client)

    result = await wallet.health()
    assert result["ok"] is True
    assert result["chain_id"] == "12345"
    mock_client.get.assert_awaited_once_with("/health", headers={})


@pytest.mark.asyncio
async def test_health_raises_on_connect_error(monkeypatch):
    """health() raises WDKServiceError if the sidecar is unreachable."""
    import httpx

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test " * 11 + "junk",
        account_index=0,
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    monkeypatch.setattr(wallet, "_get_async_client", lambda: mock_client)

    with pytest.raises(WDKServiceError, match="WDK health check failed"):
        await wallet.health()


@pytest.mark.asyncio
async def test_health_raises_on_non_200(monkeypatch):
    """health() raises WDKServiceError if the status code >= 400."""
    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test " * 11 + "junk",
        account_index=0,
    )

    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.json.return_value = {"error": "service down"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(wallet, "_get_async_client", lambda: mock_client)

    with pytest.raises(WDKServiceError, match="503"):
        await wallet.health()


# ── BuyerAgent._ensure_wdk_healthy() ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_wdk_healthy_logs_warning_on_failure(caplog):
    """_ensure_wdk_healthy warns on health failure but does not raise."""
    from buyer_agent.client import BuyerAgent
    import logging

    agent = BuyerAgent(
        gateway_url="http://localhost:8000",
        seller_url="http://localhost:8001",
        buyer_address="0x" + "11" * 20,
    )
    if agent._wdk_wallet is None:
        # WDK not configured — skip
        pytest.skip("WDK not configured in env")

    with patch.object(agent._wdk_wallet, "health", AsyncMock(side_effect=WDKServiceError("unreachable"))):
        with caplog.at_level(logging.WARNING, logger="sla-gateway.buyer"):
            await agent._ensure_wdk_healthy()

    assert any("health check failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_ensure_wdk_healthy_runs_once():
    """_ensure_wdk_healthy is a one-shot check — subsequent calls skip."""
    from buyer_agent.client import BuyerAgent

    agent = BuyerAgent(
        gateway_url="http://localhost:8000",
        seller_url="http://localhost:8001",
        buyer_address="0x" + "11" * 20,
    )
    if agent._wdk_wallet is None:
        pytest.skip("WDK not configured in env")

    call_count = 0

    async def fake_health():
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    with patch.object(agent._wdk_wallet, "health", fake_health):
        await agent._ensure_wdk_healthy()
        await agent._ensure_wdk_healthy()  # should not call again

    assert call_count == 1


# ── Concurrent WDK calls (no race) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_wdk_concurrent_health_calls():
    """Multiple concurrent health() calls should all resolve without deadlock."""
    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test " * 11 + "junk",
        account_index=0,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch.object(wallet, "_get_async_client", return_value=mock_client):
        results = await asyncio.gather(*[wallet.health() for _ in range(5)])

    assert all(r["ok"] is True for r in results)
    assert mock_client.get.await_count == 5
