"""A2A/AP2 protocol endpoints — translate between envelope format and REST API.

These endpoints accept and return A2A-framed messages, delegating to the
existing REST logic internally.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.app.a2a.envelope import (
    create_envelope,
    mandate_response,
    parse_envelope,
    receipt_ack,
    receipt_submission,
)
from gateway.app.receipt import receipt_store

logger = logging.getLogger("sla-gateway.a2a")

router = APIRouter(prefix="/a2a", tags=["a2a"])


@router.post("/message")
async def handle_a2a_message(request: Request) -> JSONResponse:
    """Universal A2A message handler — dispatches based on message_type."""
    body = await request.json()

    msg_type, payload, correlation_id = parse_envelope(body)
    sender = body.get("sender", "unknown")
    receiver = body.get("receiver", "gateway")

    if msg_type == "sla-pay.mandate.request":
        return _handle_mandate_request(sender, payload, correlation_id)

    elif msg_type == "sla-pay.receipt.ack":
        return _handle_receipt_ack(sender, payload, correlation_id)

    elif msg_type == "sla-pay.dispute.open":
        return _handle_dispute_open(sender, payload, correlation_id)

    else:
        return JSONResponse(
            status_code=400,
            content=create_envelope(
                message_type="sla-pay.error",
                sender="gateway",
                receiver=sender,
                correlation_id=correlation_id,
                payload={"error": f"Unknown message type: {msg_type}"},
            ),
        )


def _handle_mandate_request(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle MandateRequest: accept the mandate and return MandateResponse."""
    mandate = payload.get("mandate", {})
    mandate_id = mandate.get("mandate_id", "accepted")

    logger.info(f"A2A mandate request from {sender}: {mandate_id}")

    resp = mandate_response(
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        accepted=True,
        mandate_id=mandate_id,
    )
    return JSONResponse(content=resp)


def _handle_receipt_ack(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle ReceiptAck: buyer acknowledges receipt."""
    request_id = payload.get("request_id", "")
    accepted = payload.get("accepted", False)

    logger.info(f"A2A receipt ack from {sender}: req={request_id} accepted={accepted}")

    return JSONResponse(content=create_envelope(
        message_type="sla-pay.receipt.ack.confirmed",
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        payload={"request_id": request_id, "status": "confirmed"},
    ))


def _handle_dispute_open(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle DisputeOpen via A2A envelope."""
    request_id = payload.get("request_id", "")
    reason = payload.get("reason", "")

    logger.info(f"A2A dispute open from {sender}: req={request_id} reason={reason}")

    return JSONResponse(content=create_envelope(
        message_type="sla-pay.dispute.opened",
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        payload={"request_id": request_id, "status": "DISPUTED"},
    ))


@router.get("/receipts/{request_id}")
async def get_receipt_a2a(request_id: str) -> JSONResponse:
    """Get a receipt in A2A envelope format."""
    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return JSONResponse(content=receipt_submission(
        sender="gateway",
        receiver="requester",
        receipt=receipt.model_dump(),
    ))
