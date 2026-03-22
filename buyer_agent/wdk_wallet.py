"""HTTP client for the local WDK sidecar."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


ROLE_ACCOUNT_INDEX = {
    "buyer": 0,
    "seller": 1,
    "gateway": 2,
    "resolver": 3,
}


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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._get_async_client()
        response = await client.request(
            method,
            path,
            json=json_body,
            headers=self._get_headers(),
        )
        data: dict[str, Any] = response.json()
        if response.status_code >= 400:
            raise WDKServiceError(data.get("error", f"wdk-service {response.status_code}"))
        return data

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
            },
        )
        return str(data.get("txHash", ""))

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

    async def status(self) -> dict[str, Any]:
        return {
            "address": self._address,
            "expected_address": self.expected_address,
            "service_url": self.service_url,
            "account_index": self.account_index,
        }
