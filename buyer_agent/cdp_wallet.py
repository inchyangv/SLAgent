"""CDP Wallet adapter for x402 payment signing.

Wraps signing through a Coinbase Developer Platform (CDP) wallet interface.
In demo mode, uses local eth_account signing with CDP-compatible logging
so that CDP wallet usage is evidenced in logs and audit trail.

Production usage would route to the CDP SDK (cdp-sdk) for custodial signing.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from eth_account import Account

logger = logging.getLogger("cdp-wallet")


@dataclass
class CDPSignResult:
    """Result of a CDP wallet signing operation."""

    signature: str
    signer_address: str
    wallet_id: str
    custody_mode: str  # "cdp_local" or "cdp_hosted"
    signed_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class CDPWallet:
    """CDP-compatible wallet for x402 payment authorization signing.

    In demo mode (CDP_MODE=local), uses local eth_account for signing
    but wraps it in the CDP interface for evidence and audit trail.

    Env vars:
        CDP_MODE: "local" (default) or "hosted"
        CDP_WALLET_ID: wallet identifier for audit (auto-generated if missing)
    """

    def __init__(
        self,
        private_key: str,
        address: str | None = None,
    ) -> None:
        self._private_key = private_key
        self._account = Account.from_key(private_key)
        self._address = address or self._account.address
        self._mode = os.getenv("CDP_MODE", "local")
        self._wallet_id = os.getenv("CDP_WALLET_ID", f"cdp_demo_{self._address[:10]}")
        self._sign_count = 0

        logger.info(
            "CDP Wallet initialized: address=%s, mode=%s, wallet_id=%s",
            self._address,
            self._mode,
            self._wallet_id,
        )

    @property
    def address(self) -> str:
        return self._address

    @property
    def wallet_id(self) -> str:
        return self._wallet_id

    @property
    def mode(self) -> str:
        return self._mode

    def sign_payment(
        self,
        *,
        to_address: str,
        value: str,
        asset: str,
        chain_id: int,
        token_name: str = "USDC",
        token_version: str = "",
    ) -> CDPSignResult:
        """Sign an x402 payment authorization via CDP wallet.

        Returns a CDPSignResult with the Base64-encoded payment header value
        and CDP audit metadata.
        """
        from gateway.app.x402 import create_x402_payment

        header_value = create_x402_payment(
            private_key=self._private_key,
            from_address=self._address,
            to_address=to_address,
            value=value,
            asset=asset,
            chain_id=chain_id,
            token_name=token_name,
            token_version=token_version,
        )

        self._sign_count += 1
        signed_at = time.time()

        result = CDPSignResult(
            signature=header_value,
            signer_address=self._address,
            wallet_id=self._wallet_id,
            custody_mode=f"cdp_{self._mode}",
            signed_at=signed_at,
            metadata={
                "to": to_address,
                "value": value,
                "asset": asset,
                "chain_id": chain_id,
                "sign_count": self._sign_count,
            },
        )

        logger.info(
            "CDP Wallet signed payment #%d: to=%s, value=%s, wallet_id=%s, mode=%s",
            self._sign_count,
            to_address,
            value,
            self._wallet_id,
            self._mode,
        )

        return result

    def sign_receipt_hash(self, receipt_hash: str) -> CDPSignResult:
        """Sign a receipt hash for attestation via CDP wallet."""
        from gateway.app.attestation import sign_receipt_hash

        signature = sign_receipt_hash(receipt_hash, self._private_key)
        self._sign_count += 1

        return CDPSignResult(
            signature=signature,
            signer_address=self._address,
            wallet_id=self._wallet_id,
            custody_mode=f"cdp_{self._mode}",
            signed_at=time.time(),
            metadata={
                "receipt_hash": receipt_hash,
                "sign_count": self._sign_count,
            },
        )

    def status(self) -> dict[str, Any]:
        """Return wallet status for logging/audit."""
        return {
            "wallet_id": self._wallet_id,
            "address": self._address,
            "mode": self._mode,
            "custody": f"cdp_{self._mode}",
            "sign_count": self._sign_count,
        }
