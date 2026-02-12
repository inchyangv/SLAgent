"""Google A2A/AP2 protocol message envelope layer.

Defines message types and translation between:
- SLA-Pay internal REST JSON format
- A2A protocol envelope format (agent-to-agent messaging)

Message Types:
- MandateRequest / MandateResponse
- ReceiptSubmission / ReceiptAck
- DisputeOpen / DisputeResolve

This implements a minimal A2A-compatible message framing so that
SLA-Pay mandates and receipts can be exchanged as structured protocol messages
rather than raw REST JSON.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


# ── Message Envelope ─────────────────────────────────────────────────────────


def create_envelope(
    *,
    message_type: str,
    sender: str,
    receiver: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Create an A2A protocol message envelope.

    Format follows a minimal A2A/AP2-compatible structure:
    {
        "a2a_version": "1.0",
        "message_id": "<uuid>",
        "message_type": "<type>",
        "sender": "<agent_id>",
        "receiver": "<agent_id>",
        "correlation_id": "<for request/response pairing>",
        "timestamp": "<iso8601>",
        "payload": { ... }
    }
    """
    return {
        "a2a_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "message_type": message_type,
        "sender": sender,
        "receiver": receiver,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def parse_envelope(data: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Parse an A2A envelope and return (message_type, payload, correlation_id)."""
    return (
        data.get("message_type", ""),
        data.get("payload", {}),
        data.get("correlation_id", ""),
    )


# ── Message Constructors ────────────────────────────────────────────────────


def mandate_request(
    *,
    sender: str,
    receiver: str,
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """Create a MandateRequest message (buyer → seller/gateway)."""
    return create_envelope(
        message_type="sla-pay.mandate.request",
        sender=sender,
        receiver=receiver,
        payload={"mandate": mandate},
    )


def mandate_response(
    *,
    sender: str,
    receiver: str,
    correlation_id: str,
    accepted: bool,
    mandate_id: str = "",
) -> dict[str, Any]:
    """Create a MandateResponse message (seller/gateway → buyer)."""
    return create_envelope(
        message_type="sla-pay.mandate.response",
        sender=sender,
        receiver=receiver,
        correlation_id=correlation_id,
        payload={"accepted": accepted, "mandate_id": mandate_id},
    )


def receipt_submission(
    *,
    sender: str,
    receiver: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Create a ReceiptSubmission message (gateway → buyer/seller)."""
    return create_envelope(
        message_type="sla-pay.receipt.submission",
        sender=sender,
        receiver=receiver,
        payload={"receipt": receipt},
    )


def receipt_ack(
    *,
    sender: str,
    receiver: str,
    correlation_id: str,
    accepted: bool,
    request_id: str = "",
) -> dict[str, Any]:
    """Create a ReceiptAck message (buyer → gateway)."""
    return create_envelope(
        message_type="sla-pay.receipt.ack",
        sender=sender,
        receiver=receiver,
        correlation_id=correlation_id,
        payload={"accepted": accepted, "request_id": request_id},
    )


def dispute_open_msg(
    *,
    sender: str,
    receiver: str,
    request_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Create a DisputeOpen message."""
    return create_envelope(
        message_type="sla-pay.dispute.open",
        sender=sender,
        receiver=receiver,
        payload={"request_id": request_id, "reason": reason},
    )


def dispute_resolve_msg(
    *,
    sender: str,
    receiver: str,
    correlation_id: str,
    request_id: str,
    final_payout: int,
) -> dict[str, Any]:
    """Create a DisputeResolve message."""
    return create_envelope(
        message_type="sla-pay.dispute.resolve",
        sender=sender,
        receiver=receiver,
        correlation_id=correlation_id,
        payload={"request_id": request_id, "final_payout": final_payout},
    )
