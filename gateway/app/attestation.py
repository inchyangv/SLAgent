"""Multi-attestation for receipts — Buyer + Seller + Gateway.

Provides receipt signing and verification for all three parties.
Each party signs the receipt hash using ECDSA (eth_sign style),
creating an auditable, multi-party attestation of what happened.

Usage:
    from gateway.app.attestation import sign_receipt_hash, verify_receipt_signature

    sig = sign_receipt_hash(receipt_hash, private_key)
    addr = verify_receipt_signature(receipt_hash, sig)
"""

from __future__ import annotations

import logging
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

logger = logging.getLogger("sla-gateway.attestation")


def sign_receipt_hash(receipt_hash: str, private_key: str) -> str:
    """Sign a receipt hash with an ECDSA private key.

    Args:
        receipt_hash: 0x-prefixed keccak256 hash of the receipt
        private_key: 0x-prefixed hex private key

    Returns:
        0x-prefixed hex signature (65 bytes: r + s + v)
    """
    hash_bytes = bytes.fromhex(receipt_hash[2:]) if receipt_hash.startswith("0x") else bytes.fromhex(receipt_hash)
    message = encode_defunct(hash_bytes)
    signed = Account.sign_message(message, private_key=private_key)
    return "0x" + signed.signature.hex()


def verify_receipt_signature(receipt_hash: str, signature: str) -> str | None:
    """Verify a receipt signature and recover the signer address.

    Args:
        receipt_hash: 0x-prefixed keccak256 hash of the receipt
        signature: 0x-prefixed hex signature

    Returns:
        Checksummed signer address, or None if verification fails
    """
    try:
        hash_bytes = bytes.fromhex(receipt_hash[2:]) if receipt_hash.startswith("0x") else bytes.fromhex(receipt_hash)
        message = encode_defunct(hash_bytes)
        sig_bytes = bytes.fromhex(signature[2:]) if signature.startswith("0x") else bytes.fromhex(signature)
        address = Account.recover_message(message, signature=sig_bytes)
        return Web3.to_checksum_address(address)
    except Exception as e:
        logger.warning(f"Signature verification failed: {e}")
        return None


class AttestationStore:
    """Tracks multi-party attestations (signatures) for receipts."""

    def __init__(self) -> None:
        # request_id -> { role -> { address, signature, verified } }
        self._attestations: dict[str, dict[str, dict[str, Any]]] = {}

    def add_attestation(
        self,
        request_id: str,
        receipt_hash: str,
        role: str,
        signature: str,
        expected_address: str | None = None,
    ) -> dict[str, Any]:
        """Add a party's signature attestation for a receipt.

        Args:
            request_id: The receipt's request ID
            receipt_hash: The receipt hash that was signed
            role: "buyer", "seller", or "gateway"
            signature: The 0x-prefixed signature
            expected_address: If provided, verify signer matches this address

        Returns:
            Attestation result with signer address and verification status
        """
        signer = verify_receipt_signature(receipt_hash, signature)
        if signer is None:
            return {"role": role, "verified": False, "error": "Invalid signature"}

        verified = True
        if expected_address:
            expected = Web3.to_checksum_address(expected_address)
            if signer != expected:
                verified = False

        attestation = {
            "role": role,
            "signer": signer,
            "signature": signature,
            "receipt_hash": receipt_hash,
            "verified": verified,
        }

        if request_id not in self._attestations:
            self._attestations[request_id] = {}
        self._attestations[request_id][role] = attestation

        return attestation

    def get_attestations(self, request_id: str) -> dict[str, Any]:
        """Get all attestations for a receipt."""
        atts = self._attestations.get(request_id, {})

        return {
            "request_id": request_id,
            "attestations": atts,
            "parties_signed": list(atts.keys()),
            "all_verified": all(a.get("verified", False) for a in atts.values()),
            "count": len(atts),
            "complete": len(atts) == 3,  # buyer + seller + gateway
        }

    def has_attestation(self, request_id: str, role: str) -> bool:
        return role in self._attestations.get(request_id, {})


# Singleton
attestation_store = AttestationStore()
