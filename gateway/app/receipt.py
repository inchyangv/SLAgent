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
    """Receipt store with SQLite persistence, indexed search, and in-memory cache."""

    def __init__(self, db_path: str | None = None) -> None:
        self._cache: dict[str, Receipt] = {}
        self._db_path = db_path or os.getenv("RECEIPT_DB_PATH", "")
        self._conn: sqlite3.Connection | None = None

        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with indexed receipts table."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                request_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                buyer TEXT DEFAULT '',
                seller TEXT DEFAULT '',
                payout INTEGER DEFAULT 0,
                refund INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                validation_pass INTEGER DEFAULT 0,
                rule_applied TEXT DEFAULT ''
            )
        """)
        # Create indexes for common search patterns
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_buyer ON receipts(buyer)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_seller ON receipts(seller)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_payout ON receipts(payout)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_latency ON receipts(latency_ms)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_validation ON receipts(validation_pass)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_created ON receipts(created_at)"
        )
        self._conn.commit()

        # Migrate: add columns if missing (for DBs created by T-126)
        self._migrate_columns()

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

    def _migrate_columns(self) -> None:
        """Add indexed columns if they don't exist (backward compat with T-126)."""
        cursor = self._conn.execute("PRAGMA table_info(receipts)")
        existing = {row[1] for row in cursor}
        new_cols = {
            "buyer": "TEXT DEFAULT ''",
            "seller": "TEXT DEFAULT ''",
            "payout": "INTEGER DEFAULT 0",
            "refund": "INTEGER DEFAULT 0",
            "latency_ms": "INTEGER DEFAULT 0",
            "validation_pass": "INTEGER DEFAULT 0",
            "rule_applied": "TEXT DEFAULT ''",
        }
        for col, typedef in new_cols.items():
            if col not in existing:
                self._conn.execute(f"ALTER TABLE receipts ADD COLUMN {col} {typedef}")
        self._conn.commit()

    @staticmethod
    def _extract_indexed_fields(receipt: Receipt) -> dict[str, Any]:
        """Extract indexed fields from a receipt for SQLite columns."""
        payout = 0
        refund = 0
        rule_applied = ""
        if receipt.pricing:
            payout = int(receipt.pricing.computed_payout)
            refund = int(receipt.pricing.computed_refund)
            rule_applied = receipt.pricing.rule_applied
        return {
            "buyer": receipt.buyer,
            "seller": receipt.seller,
            "payout": payout,
            "refund": refund,
            "latency_ms": receipt.metrics.latency_ms,
            "validation_pass": 1 if receipt.validation.get("overall_pass") else 0,
            "rule_applied": rule_applied,
        }

    def save(self, receipt: Receipt) -> None:
        """Save receipt to cache and (if configured) to SQLite with indexed fields."""
        self._cache[receipt.request_id] = receipt

        if self._conn:
            data = receipt.model_dump_json()
            fields = self._extract_indexed_fields(receipt)
            self._conn.execute(
                """INSERT OR REPLACE INTO receipts
                   (request_id, data, created_at, buyer, seller, payout, refund,
                    latency_ms, validation_pass, rule_applied)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    receipt.request_id,
                    data,
                    datetime.now(timezone.utc).isoformat(),
                    fields["buyer"],
                    fields["seller"],
                    fields["payout"],
                    fields["refund"],
                    fields["latency_ms"],
                    fields["validation_pass"],
                    fields["rule_applied"],
                ),
            )
            self._conn.commit()

    def get(self, request_id: str) -> Receipt | None:
        return self._cache.get(request_id)

    def list_recent(self, limit: int = 50) -> list[Receipt]:
        items = list(self._cache.values())
        return items[-limit:]

    def search(
        self,
        *,
        buyer: str | None = None,
        seller: str | None = None,
        min_payout: int | None = None,
        max_latency_ms: int | None = None,
        validation_pass: bool | None = None,
        rule_applied: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Receipt]:
        """Search receipts by indexed fields.

        When SQLite is configured, uses indexed SQL queries.
        Otherwise falls back to in-memory filtering.
        """
        if self._conn:
            return self._search_sqlite(
                buyer=buyer,
                seller=seller,
                min_payout=min_payout,
                max_latency_ms=max_latency_ms,
                validation_pass=validation_pass,
                rule_applied=rule_applied,
                limit=limit,
                offset=offset,
            )
        return self._search_memory(
            buyer=buyer,
            seller=seller,
            min_payout=min_payout,
            max_latency_ms=max_latency_ms,
            validation_pass=validation_pass,
            rule_applied=rule_applied,
            limit=limit,
            offset=offset,
        )

    def _search_sqlite(self, **kwargs: Any) -> list[Receipt]:
        """Search using SQLite indexed queries."""
        conditions = []
        params: list[Any] = []

        if kwargs.get("buyer"):
            conditions.append("buyer = ?")
            params.append(kwargs["buyer"])
        if kwargs.get("seller"):
            conditions.append("seller = ?")
            params.append(kwargs["seller"])
        if kwargs.get("min_payout") is not None:
            conditions.append("payout >= ?")
            params.append(kwargs["min_payout"])
        if kwargs.get("max_latency_ms") is not None:
            conditions.append("latency_ms <= ?")
            params.append(kwargs["max_latency_ms"])
        if kwargs.get("validation_pass") is not None:
            conditions.append("validation_pass = ?")
            params.append(1 if kwargs["validation_pass"] else 0)
        if kwargs.get("rule_applied"):
            conditions.append("rule_applied = ?")
            params.append(kwargs["rule_applied"])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)

        query = f"SELECT data FROM receipts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._conn.execute(query, params)
        results = []
        for row in cursor:
            try:
                results.append(Receipt.model_validate_json(row[0]))
            except Exception:
                pass
        return results

    def _search_memory(self, **kwargs: Any) -> list[Receipt]:
        """Search using in-memory filtering (fallback when no SQLite)."""
        results = list(self._cache.values())

        if kwargs.get("buyer"):
            results = [r for r in results if r.buyer == kwargs["buyer"]]
        if kwargs.get("seller"):
            results = [r for r in results if r.seller == kwargs["seller"]]
        if kwargs.get("min_payout") is not None:
            results = [
                r for r in results
                if r.pricing and int(r.pricing.computed_payout) >= kwargs["min_payout"]
            ]
        if kwargs.get("max_latency_ms") is not None:
            results = [
                r for r in results if r.metrics.latency_ms <= kwargs["max_latency_ms"]
            ]
        if kwargs.get("validation_pass") is not None:
            target = kwargs["validation_pass"]
            results = [
                r for r in results
                if r.validation.get("overall_pass") == target
            ]
        if kwargs.get("rule_applied"):
            results = [
                r for r in results
                if r.pricing and r.pricing.rule_applied == kwargs["rule_applied"]
            ]

        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)
        return results[offset : offset + limit]

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
    t_request_received: float = 0.0,
    t_first_token: float = 0.0,
    t_response_done: float = 0.0,
    breach_reasons: list[str] | None = None,
) -> Receipt:
    """Assemble a receipt with computed hashes and accurate timestamps.

    Timestamps are epoch floats from RequestMetrics. If not provided, uses now().
    TTFT is defined as "time to first response byte from seller" (non-streaming).
    """
    now = datetime.now(timezone.utc)

    def _ts(epoch: float) -> str:
        if epoch > 0:
            return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        return now.isoformat()

    timestamps = {
        "t_request_received": _ts(t_request_received),
        "t_first_token": _ts(t_first_token),
        "t_response_done": _ts(t_response_done),
    }

    receipt = Receipt(
        version="1.0",
        mandate_id=mandate_id,
        request_id=request_id,
        buyer=buyer,
        seller=seller,
        gateway=gateway_addr,
        timestamps=timestamps,
        metrics=metrics,
        outcome=outcome,
        validation=validation,
        pricing=pricing,
        breach_reasons=breach_reasons or [],
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
