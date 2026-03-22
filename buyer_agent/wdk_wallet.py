"""HTTP client for the local WDK sidecar."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger("sla-gateway.wdk")


ROLE_ACCOUNT_INDEX = {
    "buyer": 0,
    "seller": 1,
    "gateway": 2,
    "resolver": 3,
}

# Retry config
_MAX_RETRIES = 2
_RETRY_BACKOFF = (0.5, 1.0)  # seconds per attempt
_RETRYABLE_STATUS = {502, 503, 504}

# Circuit breaker config
_CB_FAILURE_THRESHOLD = 3
_CB_RECOVERY_TIMEOUT = 30.0  # seconds


class _CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class WDKServiceError(RuntimeError):
    """Raised when the WDK sidecar returns an error."""


@dataclass
class WDKWallet:
    service_url: str
    seed_phrase: str
    account_index: int
    expected_address: str | None = None
    timeout: float = 20.0

    _address: str | None = field(default=None, init=False, repr=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)
    # Circuit breaker state
    _cb_state: _CBState = field(default=_CBState.CLOSED, init=False, repr=False)
    _cb_failures: int = field(default=0, init=False, repr=False)
    _cb_opened_at: float = field(default=0.0, init=False, repr=False)

    def __repr__(self) -> str:
        return (
            f"WDKWallet(service_url={self.service_url!r}, "
            f"seed_phrase='***', "
            f"account_index={self.account_index!r}, "
            f"address={self._address!r})"
        )

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def from_env(
        cls,
        *,
        role: str = "buyer",
        expected_address: str | None = None,
    ) -> WDKWallet | None:
        import logging
        logger = logging.getLogger("sla-gateway.wdk")

        service_url = os.getenv("WDK_SERVICE_URL", "").strip()
        seed_phrase = (
            os.getenv(f"{role.upper()}_WDK_SEED_PHRASE", "").strip()
            or os.getenv("WDK_SEED_PHRASE", "").strip()
            or os.getenv("DEMO_MNEMONIC", "").strip()
        )
        if not service_url or not seed_phrase:
            if not service_url:
                logger.warning("WDK_SERVICE_URL not set — WDK wallet disabled for role=%s", role)
            elif not seed_phrase:
                logger.warning("No seed phrase env var found — WDK wallet disabled for role=%s", role)
            return None

        default_index = ROLE_ACCOUNT_INDEX.get(role, 0)
        account_index = int(os.getenv(f"{role.upper()}_WDK_ACCOUNT_INDEX", str(default_index)))
        return cls(
            service_url=service_url.rstrip("/"),
            seed_phrase=seed_phrase,
            account_index=account_index,
            expected_address=expected_address,
        )

    @property
    def address(self) -> str:
        if not self._address:
            raise WDKServiceError("wallet not loaded")
        return self._address

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        auth_token = os.getenv("WDK_AUTH_TOKEN", "").strip()
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    # --- Async client (primary) ---

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            pool_size = int(os.getenv("WDK_POOL_SIZE", "10"))
            limits = httpx.Limits(max_connections=pool_size, max_keepalive_connections=pool_size)
            self._async_client = httpx.AsyncClient(
                base_url=self.service_url,
                timeout=self.timeout,
                limits=limits,
            )
        return self._async_client

    def _cb_check(self) -> None:
        """Raise immediately if circuit is OPEN (and not ready to recover)."""
        if self._cb_state == _CBState.OPEN:
            elapsed = time.monotonic() - self._cb_opened_at
            if elapsed >= _CB_RECOVERY_TIMEOUT:
                self._cb_state = _CBState.HALF_OPEN
                logger.info("WDK circuit: OPEN → HALF_OPEN after %.1fs", elapsed)
            else:
                raise WDKServiceError(
                    f"WDK circuit open — service unavailable (retry in {_CB_RECOVERY_TIMEOUT - elapsed:.0f}s)"
                )

    def _cb_record_success(self) -> None:
        if self._cb_state in (_CBState.HALF_OPEN, _CBState.OPEN):
            logger.info("WDK circuit: → CLOSED after recovery")
        self._cb_state = _CBState.CLOSED
        self._cb_failures = 0

    def _cb_record_failure(self) -> None:
        self._cb_failures += 1
        if self._cb_state == _CBState.HALF_OPEN:
            self._cb_state = _CBState.OPEN
            self._cb_opened_at = time.monotonic()
            logger.warning("WDK circuit: HALF_OPEN → OPEN (probe failed)")
        elif self._cb_failures >= _CB_FAILURE_THRESHOLD:
            self._cb_state = _CBState.OPEN
            self._cb_opened_at = time.monotonic()
            logger.warning("WDK circuit: CLOSED → OPEN (%d failures)", self._cb_failures)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._cb_check()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = _RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)]
                await asyncio.sleep(delay)

            t0 = time.monotonic()
            try:
                client = self._get_async_client()
                response = await client.request(
                    method,
                    path,
                    json=json_body,
                    headers=self._get_headers(),
                )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.debug("WDK %s %s failed in %dms (attempt %d): %s", method, path, duration_ms, attempt + 1, exc)
                last_exc = exc
                logger.warning("WDK request failed (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES + 1, exc)
                self._cb_record_failure()
                continue

            # Don't retry 4xx client errors
            if 400 <= response.status_code < 500 and response.status_code not in _RETRYABLE_STATUS:
                data: dict[str, Any] = response.json()
                self._cb_record_failure()
                raise WDKServiceError(data.get("error", f"wdk-service {response.status_code}"))

            if response.status_code in _RETRYABLE_STATUS:
                last_exc = WDKServiceError(f"wdk-service {response.status_code}")
                logger.warning("WDK retryable error %d (attempt %d/%d)", response.status_code, attempt + 1, _MAX_RETRIES + 1)
                self._cb_record_failure()
                continue

            data = response.json()
            if response.status_code >= 400:
                self._cb_record_failure()
                raise WDKServiceError(data.get("error", f"wdk-service {response.status_code}"))

            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.debug("WDK %s %s → %d in %dms", method, path, response.status_code, duration_ms)
            self._cb_record_success()
            return data

        self._cb_record_failure()
        raise last_exc or WDKServiceError("WDK request failed after retries")

    async def close(self) -> None:
        """Close the underlying AsyncClient connection pool."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    # --- Sync fallback (for code that cannot be awaited) ---

    def _request_sync(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = httpx.request(
            method,
            f"{self.service_url}{path}",
            json=json_body,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        data: dict[str, Any] = response.json()
        if response.status_code >= 400:
            raise WDKServiceError(data.get("error", f"wdk-service {response.status_code}"))
        return data

    # --- Public async methods ---

    async def ensure_wallet_loaded(self) -> str:
        if self._address:
            return self._address

        data = await self._request(
            "POST",
            "/wallet/import",
            json_body={
                "seedPhrase": self.seed_phrase,
                "accountIndex": self.account_index,
            },
        )
        address = str(data.get("address", "")).strip()
        if not address:
            raise WDKServiceError("wdk-service returned no address")
        if self.expected_address and self.expected_address.lower() != address.lower():
            raise WDKServiceError(
                f"wdk address mismatch: expected {self.expected_address}, got {address}"
            )
        self._address = address
        return address

    async def balance(self, *, token_address: str | None = None) -> dict[str, Any]:
        address = await self.ensure_wallet_loaded()
        path = f"/wallet/{address}/balance"
        if token_address:
            path += f"?tokenAddress={token_address}"
        return await self._request("GET", path)

    async def approve(
        self,
        *,
        spender: str,
        amount: str | int,
        token_address: str,
        wait_for_receipt: bool = False,
    ) -> str:
        address = await self.ensure_wallet_loaded()
        data = await self._request(
            "POST",
            "/wallet/approve",
            json_body={
                "address": address,
                "spender": spender,
                "amount": str(amount),
                "tokenAddress": token_address,
                "waitForReceipt": wait_for_receipt,
            },
        )
        return str(data.get("txHash", ""))

    async def deposit(
        self,
        *,
        request_id: str,
        amount: str | int,
        settlement_contract: str,
        buyer_address: str | None = None,
        wait_for_receipt: bool = False,
    ) -> str:
        address = await self.ensure_wallet_loaded()
        data = await self._request(
            "POST",
            "/wallet/deposit",
            json_body={
                "address": address,
                "requestId": request_id,
                "buyer": buyer_address or address,
                "amount": str(amount),
                "settlementContract": settlement_contract,
                "waitForReceipt": wait_for_receipt,
            },
        )
        return str(data.get("txHash", ""))

    async def approve_and_deposit(
        self,
        *,
        spender: str,
        request_id: str,
        amount: str | int,
        token_address: str,
        settlement_contract: str,
        buyer_address: str | None = None,
    ) -> dict[str, Any]:
        """Atomically approve and deposit in one server-side operation.

        Uses the /wallet/approve-and-deposit endpoint which retries deposit
        up to 2 times on failure and returns both tx hashes.
        """
        address = await self.ensure_wallet_loaded()
        data = await self._request(
            "POST",
            "/wallet/approve-and-deposit",
            json_body={
                "address": address,
                "spender": spender,
                "requestId": request_id,
                "buyer": buyer_address or address,
                "amount": str(amount),
                "tokenAddress": token_address,
                "settlementContract": settlement_contract,
            },
        )
        return data

    async def sign_message(self, message: str) -> str:
        address = await self.ensure_wallet_loaded()
        data = await self._request(
            "POST",
            "/wallet/sign-message",
            json_body={
                "address": address,
                "message": message,
            },
        )
        return str(data.get("signature", ""))

    async def sign_bytes(self, payload_hex: str) -> str:
        address = await self.ensure_wallet_loaded()
        data = await self._request(
            "POST",
            "/wallet/sign-bytes",
            json_body={
                "address": address,
                "payload": payload_hex,
            },
        )
        return str(data.get("signature", ""))

    async def health(self) -> dict[str, Any]:
        """Call GET /health on the WDK sidecar without auth.

        Returns the health dict from the sidecar (status, version, etc.).
        Raises WDKServiceError if the sidecar is unreachable.
        """
        t0 = time.monotonic()
        try:
            client = self._get_async_client()
            response = await client.get("/health", headers={})  # no auth on /health
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise WDKServiceError(f"WDK health check failed: {exc}") from exc
        duration_ms = int((time.monotonic() - t0) * 1000)
        data: dict[str, Any] = response.json()
        if response.status_code >= 400:
            raise WDKServiceError(f"WDK health returned {response.status_code}")
        logger.info(
            "WDK health OK in %dms — status=%s chain_id=%s",
            duration_ms,
            data.get("status"),
            data.get("chain_id"),
        )
        return data

    async def status(self) -> dict[str, Any]:
        return {
            "address": self._address,
            "expected_address": self.expected_address,
            "service_url": self.service_url,
            "account_index": self.account_index,
        }
