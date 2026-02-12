"""Receipt generation and storage (in-memory + SQLite persistence)."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.app.hashing import compute_receipt_hash, keccak256, canonical_json
from gateway.app.models import Metrics, PricingResult, Receipt


class ReceiptStore:
    """Receipt store with SQLite persistence and in-memory cache."""

    def __init__(self, db_path: str | None = None) -> None:
        self._cache: dict[str, Receipt] = {}
        self._db_path = db_path or os.getenv("RECEIPT_DB_PATH", "")
        self._conn: sqlite3.Connection | None = None

        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with receipts table."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                request_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

        # Load existing receipts into cache
        cursor = self._conn.execute(
            "SELECT request_id, data FROM receipts ORDER BY created_at"
        )
        for row in cursor:
            try:
                receipt = Receipt.model_validate_json(row[1])
                self._cache[row[0]] = receipt
            except Exception:
                pass

    def save(self, receipt: Receipt) -> None:
        """Save receipt to cache and (if configured) to SQLite."""
        self._cache[receipt.request_id] = receipt

        if self._conn:
            data = receipt.model_dump_json()
            self._conn.execute(
                "INSERT OR REPLACE INTO receipts (request_id, data, created_at) VALUES (?, ?, ?)",
                (receipt.request_id, data, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def get(self, request_id: str) -> Receipt | None:
        return self._cache.get(request_id)

    def list_recent(self, limit: int = 50) -> list[Receipt]:
        items = list(self._cache.values())
        return items[-limit:]

    def export_jsonl(self) -> str:
        """Export all receipts as JSONL (one JSON object per line)."""
        lines = []
        for receipt in self._cache.values():
            lines.append(receipt.model_dump_json())
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._cache)


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
