"""Receipt generation and in-memory storage."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from gateway.app.hashing import compute_receipt_hash, keccak256, canonical_json
from gateway.app.models import Metrics, PricingResult, Receipt


class ReceiptStore:
    """Simple in-memory receipt store."""

    def __init__(self) -> None:
        self._receipts: dict[str, Receipt] = {}

    def save(self, receipt: Receipt) -> None:
        self._receipts[receipt.request_id] = receipt

    def get(self, request_id: str) -> Receipt | None:
        return self._receipts.get(request_id)

    def list_recent(self, limit: int = 50) -> list[Receipt]:
        items = list(self._receipts.values())
        return items[-limit:]


# Singleton store
receipt_store = ReceiptStore()


def generate_request_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"req_{ts}_{short}"


def build_receipt(
    *,
    request_id: str,
    mandate_id: str,
    buyer: str,
    seller: str,
    gateway_addr: str,
    metrics: Metrics,
    outcome: dict[str, Any],
    validation: dict[str, Any],
    pricing: PricingResult,
    request_body: bytes,
    response_body: bytes,
) -> Receipt:
    """Assemble a receipt with computed hashes."""
    now = datetime.now(timezone.utc)

    receipt = Receipt(
        version="1.0",
        mandate_id=mandate_id,
        request_id=request_id,
        buyer=buyer,
        seller=seller,
        gateway=gateway_addr,
        timestamps={
            "t_request_received": now.isoformat(),
            "t_response_done": now.isoformat(),
        },
        metrics=metrics,
        outcome=outcome,
        validation=validation,
        pricing=pricing,
    )

    # Compute hashes
    request_hash = keccak256(request_body)
    response_hash = keccak256(response_body)
    receipt_hash = compute_receipt_hash(receipt.model_dump())

    receipt.hashes = {
        "request_hash": request_hash,
        "response_hash": response_hash,
        "receipt_hash": receipt_hash,
    }

    return receipt
