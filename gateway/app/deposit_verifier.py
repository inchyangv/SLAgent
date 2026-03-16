"""Deposit-first verification stub for the gateway.

This is intentionally lightweight for the first migration step:
- if chain config is absent, local demos can proceed in mock mode
- if chain config is present, the client must provide a deposit tx hash
- on-chain receipt decoding will replace this stub in a later step
"""

from __future__ import annotations

import re
from typing import Any

_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def verify_deposit_submission(
    *,
    request_id: str,
    buyer: str,
    max_price: str,
    deposit_tx_hash: str | None,
    chain_rpc_url: str,
    settlement_contract: str,
    source: str,
) -> dict[str, Any] | None:
    """Verify that a request is backed by a deposit signal."""
    tx_hash = (deposit_tx_hash or "").strip() or None
    has_chain_config = bool(chain_rpc_url and settlement_contract)

    if not tx_hash:
        if not has_chain_config:
            return {
                "request_id": request_id,
                "buyer": buyer,
                "amount": max_price,
                "tx_hash": None,
                "mode": "mock_no_chain",
                "source": "no_chain_config",
            }
        return None

    if not _TX_HASH_RE.fullmatch(tx_hash):
        return None

    return {
        "request_id": request_id,
        "buyer": buyer,
        "amount": max_price,
        "tx_hash": tx_hash,
        "mode": "deposit_stub",
        "source": source,
    }
