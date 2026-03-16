"""Tests for the buyer-side WDK sidecar client."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from buyer_agent.wdk_wallet import WDKServiceError, WDKWallet


@dataclass
class _MockResponse:
    status_code: int
    payload: dict[str, object]

    def json(self) -> dict[str, object]:
        return self.payload


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


def test_ensure_wallet_loaded_imports_once(monkeypatch):
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request(method: str, url: str, json: dict[str, object] | None = None, timeout: float = 0):
        calls.append((method, url, json))
        return _MockResponse(
            200,
            {"address": "0x1111111111111111111111111111111111111111"},
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
        expected_address="0x1111111111111111111111111111111111111111",
    )

    assert wallet.ensure_wallet_loaded() == "0x1111111111111111111111111111111111111111"
    assert wallet.ensure_wallet_loaded() == "0x1111111111111111111111111111111111111111"
    assert len(calls) == 1
    assert calls[0][0] == "POST"
    assert calls[0][1] == "http://localhost:3100/wallet/import"


def test_ensure_wallet_loaded_rejects_address_mismatch(monkeypatch):
    def fake_request(method: str, url: str, json: dict[str, object] | None = None, timeout: float = 0):
        return _MockResponse(
            200,
            {"address": "0x2222222222222222222222222222222222222222"},
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
        expected_address="0x1111111111111111111111111111111111111111",
    )

    with pytest.raises(WDKServiceError, match="wdk address mismatch"):
        wallet.ensure_wallet_loaded()


def test_balance_approve_deposit_and_sign(monkeypatch):
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request(method: str, url: str, json: dict[str, object] | None = None, timeout: float = 0):
        calls.append((method, url, json))
        if url.endswith("/wallet/import"):
            return _MockResponse(200, {"address": "0x1111111111111111111111111111111111111111"})
        if "/balance" in url:
            return _MockResponse(200, {"native": "1", "tokenBalance": "2"})
        if url.endswith("/wallet/approve"):
            return _MockResponse(200, {"txHash": "0xapprove"})
        if url.endswith("/wallet/deposit"):
            return _MockResponse(200, {"txHash": "0xdeposit"})
        if url.endswith("/wallet/sign-message"):
            return _MockResponse(200, {"signature": "0xsigned"})
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(httpx, "request", fake_request)

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
    )

    balance = wallet.balance(token_address="0x9999999999999999999999999999999999999999")
    approve_tx = wallet.approve(
        spender="0x3333333333333333333333333333333333333333",
        amount=123,
        token_address="0x9999999999999999999999999999999999999999",
    )
    deposit_tx = wallet.deposit(
        request_id="req_123",
        amount=123,
        settlement_contract="0x4444444444444444444444444444444444444444",
        buyer_address="0x5555555555555555555555555555555555555555",
    )
    signature = wallet.sign_message("hello")

    assert balance["tokenBalance"] == "2"
    assert approve_tx == "0xapprove"
    assert deposit_tx == "0xdeposit"
    assert signature == "0xsigned"
    assert len(calls) == 5


def test_request_raises_service_error(monkeypatch):
    def fake_request(method: str, url: str, json: dict[str, object] | None = None, timeout: float = 0):
        return _MockResponse(400, {"error": "bad request"})

    monkeypatch.setattr(httpx, "request", fake_request)

    wallet = WDKWallet(
        service_url="http://localhost:3100",
        seed_phrase="test test test test test test test test test test test junk",
        account_index=0,
    )

    with pytest.raises(WDKServiceError, match="bad request"):
        wallet.ensure_wallet_loaded()
