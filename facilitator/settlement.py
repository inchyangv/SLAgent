"""Facilitator: settlement transaction coordinator.

Architecture: library module callable from gateway.
Handles chain submission, idempotency, and retry logic.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

logger = logging.getLogger("sla-facilitator")


class SettlementClient:
    """Coordinates settlement transactions to the on-chain contract."""

    def __init__(
        self,
        *,
        rpc_url: str,
        contract_address: str,
        gateway_private_key: str,
        settlement_abi: list[dict[str, Any]],
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url)) if rpc_url else None
        self.contract_address = contract_address
        self.gateway_private_key = gateway_private_key
        self.gateway_account = (
            Account.from_key(gateway_private_key) if gateway_private_key else None
        )

        if self.w3 and contract_address:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=settlement_abi,
            )
        else:
            self.contract = None

        # Idempotency: track submitted request_ids
        self._submitted: set[str] = set()
        self._tx_lock = Lock()
        self._last_nonce: int | None = None

    @property
    def gateway_address(self) -> str:
        if self.gateway_account:
            return self.gateway_account.address
        return ""

    def _next_nonce(self) -> int:
        if not self.w3 or not self.gateway_account:
            raise RuntimeError("Chain client not initialized")
        # Use pending nonce and keep a local monotonic nonce cache.
        # Some RPCs lag on pending nonce visibility under rapid submissions.
        chain_nonce = self.w3.eth.get_transaction_count(self.gateway_account.address, "pending")
        if self._last_nonce is None:
            nonce = chain_nonce
        else:
            nonce = max(chain_nonce, self._last_nonce + 1)
        self._last_nonce = nonce
        return nonce

    def sign_settlement(
        self,
        *,
        mandate_id: bytes,
        request_id: bytes,
        buyer: str,
        seller: str,
        max_price: int,
        payout: int,
        receipt_hash: bytes,
    ) -> bytes:
        """Sign settlement parameters with gateway private key.

        Signs: keccak256(abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash))
        """
        if not self.gateway_account:
            raise RuntimeError("Gateway private key not configured")

        # Replicate Solidity: keccak256(abi.encodePacked(...))
        packed = (
            mandate_id
            + request_id
            + bytes.fromhex(buyer[2:].lower().zfill(40))
            + bytes.fromhex(seller[2:].lower().zfill(40))
            + max_price.to_bytes(32, "big")
            + payout.to_bytes(32, "big")
            + receipt_hash
        )
        msg_hash = Web3.keccak(packed)
        signed = Account.sign_message(encode_defunct(msg_hash), self.gateway_private_key)
        return signed.signature

    def submit_deposit(
        self,
        *,
        request_id_str: str,
        request_id: bytes,
        buyer: str,
        amount: int,
    ) -> str | None:
        """Submit a deposit transaction on-chain (buyer funds escrow).

        Returns tx hash hex string, or None if mocked/not configured.
        """
        if not self.contract or not self.w3 or not self.gateway_account:
            logger.info(
                f"Deposit mock: req={request_id_str} buyer={buyer} amount={amount} "
                f"(no chain connection configured)"
            )
            return None

        try:
            with self._tx_lock:
                tx = self.contract.functions.deposit(
                    request_id,
                    Web3.to_checksum_address(buyer),
                    amount,
                ).build_transaction({
                    "chainId": int(self.w3.eth.chain_id),
                    "from": self.gateway_account.address,
                    "nonce": self._next_nonce(),
                    "gas": 200_000,
                    "gasPrice": self.w3.eth.gas_price,
                })

                signed_tx = self.w3.eth.account.sign_transaction(tx, self.gateway_private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                hex_hash = tx_hash.hex()

            logger.info(f"Deposit tx submitted: {hex_hash}")
            return hex_hash

        except Exception as e:
            self._last_nonce = None
            logger.error(f"Deposit tx failed: {e}")
            raise

    def submit_settlement(
        self,
        *,
        mandate_id: bytes,
        request_id_str: str,
        request_id: bytes,
        buyer: str,
        seller: str,
        max_price: int,
        payout: int,
        receipt_hash: bytes,
        gateway_sig: bytes,
    ) -> str | None:
        """Submit a settlement transaction on-chain.

        Returns tx hash hex string, or None if mocked/not configured.
        Enforces idempotency: won't submit same request_id twice.
        """
        # Idempotency check
        if request_id_str in self._submitted:
            logger.warning(f"Duplicate settlement submission for {request_id_str}, skipping")
            return None

        self._submitted.add(request_id_str)

        if not self.contract or not self.w3 or not self.gateway_account:
            logger.info(
                f"Settlement mock: req={request_id_str} payout={payout} "
                f"(no chain connection configured)"
            )
            return None

        try:
            # Build transaction
            with self._tx_lock:
                tx = self.contract.functions.settle(
                    mandate_id,
                    request_id,
                    Web3.to_checksum_address(buyer),
                    Web3.to_checksum_address(seller),
                    max_price,
                    payout,
                    receipt_hash,
                    gateway_sig,
                ).build_transaction({
                    "chainId": int(self.w3.eth.chain_id),
                    "from": self.gateway_account.address,
                    "nonce": self._next_nonce(),
                    "gas": 300_000,
                    "gasPrice": self.w3.eth.gas_price,
                })

                signed_tx = self.w3.eth.account.sign_transaction(tx, self.gateway_private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                hex_hash = tx_hash.hex()

            logger.info(f"Settlement tx submitted: {hex_hash}")
            return hex_hash

        except Exception as e:
            self._last_nonce = None
            logger.error(f"Settlement tx failed: {e}")
            # Remove from submitted so it can be retried
            self._submitted.discard(request_id_str)
            raise
