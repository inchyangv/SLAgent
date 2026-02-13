"""Mandate store — in-memory registry for negotiated SLA mandates.

Mandates are registered via POST /v1/mandates and referenced by mandate_id in /v1/call.
"""

from __future__ import annotations

import time
from typing import Any

from gateway.app.hashing import compute_mandate_id


class MandateStore:
    """In-memory mandate store with lookup by mandate_id."""

    def __init__(self) -> None:
        self._mandates: dict[str, dict[str, Any]] = {}

    def register(self, mandate: dict[str, Any]) -> dict[str, Any]:
        """Register a mandate. Computes mandate_id if not provided.

        Returns the stored mandate (with mandate_id set).
        """
        # Compute mandate_id from payload if not present
        if not mandate.get("mandate_id"):
            mandate["mandate_id"] = compute_mandate_id(mandate)

        mandate_id = mandate["mandate_id"]
        mandate["registered_at"] = time.time()
        self._mandates[mandate_id] = mandate
        return mandate

    def get(self, mandate_id: str) -> dict[str, Any] | None:
        """Look up a mandate by ID."""
        return self._mandates.get(mandate_id)

    def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all registered mandates (most recent first)."""
        mandates = sorted(
            self._mandates.values(),
            key=lambda m: m.get("registered_at", 0),
            reverse=True,
        )
        return mandates[:limit]

    def count(self) -> int:
        return len(self._mandates)


# Singleton
mandate_store = MandateStore()
