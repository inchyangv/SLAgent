"""HTTP client for the local WDK sidecar."""

from __future__ import annotations

import os
from dataclasses import dataclass
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

    _address: str | None = None

    @classmethod
    def from_env(
        cls,
        *,
        role: str = "buyer",
        expected_address: str | None = None,
    ) -> WDKWallet | None:
        service_url = os.getenv("WDK_SERVICE_URL", "").strip()
        seed_phrase = (
            os.getenv(f"{role.upper()}_WDK_SEED_PHRASE", "").strip()
            or os.getenv("WDK_SEED_PHRASE", "").strip()
            or os.getenv("DEMO_MNEMONIC", "").strip()
        )
        if not service_url or not seed_phrase:
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

    def _request(
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
            timeout=self.timeout,
        )
        data: dict[str, Any] = response.json()
        if response.status_code >= 400:
            raise WDKServiceError(data.get("error", f"wdk-service {response.status_code}"))
        return data

    def ensure_wallet_loaded(self) -> str:
        if self._address:
            return self._address

        data = self._request(
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

    def balance(self, *, token_address: str | None = None) -> dict[str, Any]:
        address = self.ensure_wallet_loaded()
        path = f"/wallet/{address}/balance"
        if token_address:
            path += f"?tokenAddress={token_address}"
        return self._request("GET", path)

    def approve(
        self,
        *,
        spender: str,
        amount: str | int,
        token_address: str,
    ) -> str:
        address = self.ensure_wallet_loaded()
        data = self._request(
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

    def deposit(
        self,
        *,
        request_id: str,
        amount: str | int,
        settlement_contract: str,
        buyer_address: str | None = None,
    ) -> str:
        address = self.ensure_wallet_loaded()
        data = self._request(
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

    def sign_message(self, message: str) -> str:
        address = self.ensure_wallet_loaded()
        data = self._request(
            "POST",
            "/wallet/sign-message",
            json_body={
                "address": address,
                "message": message,
            },
        )
        return str(data.get("signature", ""))
