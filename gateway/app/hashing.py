"""Canonical JSON hashing for SLA mandates and receipts.

Rules:
- Sort keys alphabetically at every level
- Compact JSON (no whitespace)
- UTF-8 encoding
- keccak256 hash
"""

import json
from typing import Any

from eth_utils import keccak


def canonical_json(obj: dict[str, Any]) -> bytes:
    """Produce canonical JSON bytes: sorted keys, compact, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def keccak256(data: bytes) -> str:
    """Compute keccak256 and return 0x-prefixed hex string."""
    return "0x" + keccak(data).hex()


# --- Mandate hashing ---

_MANDATE_EXCLUDE_FIELDS = {"mandate_id", "seller_signature", "buyer_signature"}


def compute_mandate_id(mandate: dict[str, Any]) -> str:
    """Compute mandate_id = keccak256(canonical_json(mandate without excluded fields))."""
    payload = {k: v for k, v in mandate.items() if k not in _MANDATE_EXCLUDE_FIELDS}
    return keccak256(canonical_json(payload))


# --- Receipt hashing ---

_RECEIPT_EXCLUDE_FIELDS = {"hashes", "signatures"}


def compute_receipt_hash(receipt: dict[str, Any]) -> str:
    """Compute receipt_hash = keccak256(canonical_json(receipt without excluded fields))."""
    payload = {k: v for k, v in receipt.items() if k not in _RECEIPT_EXCLUDE_FIELDS}
    return keccak256(canonical_json(payload))
