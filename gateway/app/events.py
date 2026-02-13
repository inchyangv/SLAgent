"""Append-only event ledger for SLA evidence timeline.

Records negotiation, payment, execution, validation, pricing,
receipt, chain, and attestation events for demo auditability.

Usage:
    from gateway.app.events import event_store

    event_store.record(
        kind="payment.402_issued",
        actor="gateway",
        request_id="req_001",
        data={"max_price": "100000"},
    )

    events = event_store.query(request_id="req_001")
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Event:
    """A single event in the SLA evidence timeline."""

    event_id: str
    ts: float  # epoch seconds
    kind: str  # e.g. "payment.402_issued", "validation.schema_pass"
    actor: str  # buyer / seller / gateway / resolver
    request_id: str = ""
    mandate_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.ts))
        return d


class EventStore:
    """In-memory append-only event store with query support."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def record(
        self,
        kind: str,
        actor: str,
        request_id: str = "",
        mandate_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> Event:
        """Record a new event."""
        event = Event(
            event_id=str(uuid.uuid4())[:12],
            ts=time.time(),
            kind=kind,
            actor=actor,
            request_id=request_id,
            mandate_id=mandate_id,
            data=data or {},
        )
        self._events.append(event)
        return event

    def query(
        self,
        request_id: str | None = None,
        mandate_id: str | None = None,
        kind: str | None = None,
        actor: str | None = None,
        limit: int = 200,
    ) -> list[Event]:
        """Query events with optional filters."""
        results = self._events
        if request_id:
            results = [e for e in results if e.request_id == request_id]
        if mandate_id:
            results = [e for e in results if e.mandate_id == mandate_id]
        if kind:
            results = [e for e in results if e.kind.startswith(kind)]
        if actor:
            results = [e for e in results if e.actor == actor]
        return results[-limit:]

    def list_recent(self, limit: int = 100) -> list[Event]:
        """Get most recent events."""
        return self._events[-limit:]

    def count(self) -> int:
        return len(self._events)

    def export_jsonl(self) -> str:
        """Export all events as JSONL."""
        lines = [json.dumps(e.to_dict()) for e in self._events]
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events.clear()


# Singleton
event_store = EventStore()
