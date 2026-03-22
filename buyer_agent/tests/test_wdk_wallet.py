"""Tests for the buyer-side WDK sidecar client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from buyer_agent.wdk_wallet import WDKServiceError, WDKWallet


def test_from_env_requires_url_and_seed(monkeypatch):
    monkeypatch.delenv("WDK_SERVICE_URL", raising=False)
    monkeypatch.delenv("WDK_SEED_PHRASE", raising=False)
    assert WDKWallet.from_env() is None


def test_from_env_uses_role_defaults(monkeypatch):
    monkeypatch.setenv("WDK_SERVICE_URL", "http://localhost:3100/")
    monkeypatch.setenv("WDK_SEED_PHRASE", "test test test test test test test test test test test junk")
    monkeypatch.setenv("BUYER_WDK_ACCOUNT_INDEX", "2")

    wallet = WDKWallet.from_env(role="buyer", expected_address="0xabc")

    assert wallet is not None
    assert wallet.service_url == "http://localhost:3100"
    assert wallet.account_index == 2
    assert wallet.expected_address == "0xabc"


@pytest.mark.asyncio
async def test_ensure_wallet_loaded_imports_once(monkeypatch):
    calls: list[tuple[str, str, Any]] = []

    async def fake_request(method: str, path: str, *, json_body: Any = None) -> dict[str, Any]:
        calls.append((method, path, json_body))
        return {"address": "0x1111111111111111111111111111111111111111"}

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
        expected_address="0x1111111111111111111111111111111111111111",
    )
    monkeypatch.setattr(wallet, "_request", fake_request)

    assert await wallet.ensure_wallet_loaded() == "0x1111111111111111111111111111111111111111"
    assert await wallet.ensure_wallet_loaded() == "0x1111111111111111111111111111111111111111"
    assert len(calls) == 1
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/wallet/import"


@pytest.mark.asyncio
async def test_ensure_wallet_loaded_rejects_address_mismatch(monkeypatch):
    async def fake_request(method: str, path: str, *, json_body: Any = None) -> dict[str, Any]:
        return {"address": "0x2222222222222222222222222222222222222222"}

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
        expected_address="0x1111111111111111111111111111111111111111",
    )
    monkeypatch.setattr(wallet, "_request", fake_request)

    with pytest.raises(WDKServiceError, match="wdk address mismatch"):
        await wallet.ensure_wallet_loaded()


@pytest.mark.asyncio
async def test_balance_approve_deposit_and_sign(monkeypatch):
    calls: list[tuple[str, str, Any]] = []
    ADDR = "0x1111111111111111111111111111111111111111"

    async def fake_request(method: str, path: str, *, json_body: Any = None) -> dict[str, Any]:
        calls.append((method, path, json_body))
        if path == "/wallet/import":
            return {"address": ADDR}
        if "/balance" in path:
            return {"native": "1", "tokenBalance": "2"}
        if path == "/wallet/approve":
            return {"txHash": "0xapprove"}
        if path == "/wallet/deposit":
            return {"txHash": "0xdeposit"}
        if path == "/wallet/sign-message":
            return {"signature": "0xsigned"}
        if path == "/wallet/sign-bytes":
            return {"signature": "0xbytesigned"}
        raise AssertionError(f"unexpected path {path}")

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
    )
    monkeypatch.setattr(wallet, "_request", fake_request)

    balance = await wallet.balance(token_address="0x9999999999999999999999999999999999999999")
    approve_tx = await wallet.approve(
        spender="0x3333333333333333333333333333333333333333",
        amount=123,
        token_address="0x9999999999999999999999999999999999999999",
    )
    deposit_tx = await wallet.deposit(
        request_id="req_123",
        amount=123,
        settlement_contract="0x4444444444444444444444444444444444444444",
        buyer_address="0x5555555555555555555555555555555555555555",
    )
    signature = await wallet.sign_message("hello")
    byte_signature = await wallet.sign_bytes("0x" + "ab" * 32)
    status = await wallet.status()

    assert balance["tokenBalance"] == "2"
    assert approve_tx == "0xapprove"
    assert deposit_tx == "0xdeposit"
    assert signature == "0xsigned"
    assert byte_signature == "0xbytesigned"
    assert status["service_url"] == "http://localhost:3100"
    assert len(calls) == 6


@pytest.mark.asyncio
async def test_request_raises_service_error(monkeypatch):
    async def fake_request(method: str, path: str, *, json_body: Any = None) -> dict[str, Any]:
        raise WDKServiceError("bad request")

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
    )
    monkeypatch.setattr(wallet, "_request", fake_request)

    with pytest.raises(WDKServiceError, match="bad request"):
        await wallet.ensure_wallet_loaded()
