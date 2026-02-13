"""A2A/AP2 protocol endpoints — translate between envelope format and REST API.

These endpoints accept and return A2A-framed messages, delegating to the
existing REST logic internally.

AP2 Intent → Authorization → Settlement → Receipt pattern:
  1. intent.create     — propose a settlement
  2. intent.authorize  — authorize the intent (with policy/mandate)
  3. settlement.execute — execute settlement (blocked without valid auth)
  4. receipt.issue     — issue final receipt with authorization audit trail
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.app.a2a.authorization import AuthorizationError, auth_store
from gateway.app.a2a.envelope import (
    create_envelope,
    intent_authorize,
    mandate_response,
    parse_envelope,
    receipt_ack,
    receipt_issue,
    receipt_submission,
    settlement_execute,
)
from gateway.app.events import event_store
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

    if msg_type == "slagent-402.mandate.request":
        return _handle_mandate_request(sender, payload, correlation_id)

    elif msg_type == "slagent-402.receipt.ack":
        return _handle_receipt_ack(sender, payload, correlation_id)

    elif msg_type == "slagent-402.dispute.open":
        return _handle_dispute_open(sender, payload, correlation_id)

    # ── AP2 Intent → Authorization → Settlement → Receipt ─────────────
    elif msg_type == "slagent-402.intent.create":
        return _handle_intent_create(sender, payload, correlation_id)

    elif msg_type == "slagent-402.intent.authorize":
        return _handle_intent_authorize(sender, payload, correlation_id)

    elif msg_type == "slagent-402.intent.reject":
        return _handle_intent_reject(sender, payload, correlation_id)

    elif msg_type == "slagent-402.settlement.execute":
        return _handle_settlement_execute(sender, payload, correlation_id)

    elif msg_type == "slagent-402.receipt.issue":
        return _handle_receipt_issue(sender, payload, correlation_id)

    else:
        return JSONResponse(
            status_code=400,
            content=create_envelope(
                message_type="slagent-402.error",
                sender="gateway",
                receiver=sender,
                correlation_id=correlation_id,
                payload={"error": f"Unknown message type: {msg_type}"},
            ),
        )


# ── Existing handlers ─────────────────────────────────────────────────────


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
        message_type="slagent-402.receipt.ack.confirmed",
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
        message_type="slagent-402.dispute.opened",
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        payload={"request_id": request_id, "status": "DISPUTED"},
    ))


# ── AP2 Intent → Authorization → Settlement → Receipt ─────────────────────


def _handle_intent_create(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle intent.create: propose a settlement intent."""
    mandate_id = payload.get("mandate_id", "")
    buyer = payload.get("buyer", sender)
    seller = payload.get("seller", "")
    max_price = payload.get("max_price", "0")

    intent = auth_store.create_intent(
        mandate_id=mandate_id,
        buyer=buyer,
        seller=seller,
        max_price=max_price,
        created_by=sender,
    )

    event_store.record(
        kind="authorization.intent_created",
        actor=sender,
        mandate_id=mandate_id,
        data={
            "intent_id": intent.intent_id,
            "buyer": buyer,
            "seller": seller,
            "max_price": max_price,
        },
    )

    logger.info("AP2 intent created: %s by %s (mandate=%s)", intent.intent_id, sender, mandate_id)

    return JSONResponse(content=create_envelope(
        message_type="slagent-402.intent.created",
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        payload={
            "intent_id": intent.intent_id,
            "status": intent.status,
            "mandate_id": mandate_id,
        },
    ))


def _handle_intent_authorize(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle intent.authorize: authorize an intent for settlement."""
    intent_id = payload.get("intent_id", "")
    authorizer = payload.get("authorizer", sender)
    policy_id = payload.get("policy_id", "")
    expires_at_str = payload.get("expires_at", "")

    expires_at = float(expires_at_str) if expires_at_str else 0.0

    try:
        auth = auth_store.authorize_intent(
            intent_id=intent_id,
            authorizer=authorizer,
            policy_id=policy_id,
            expires_at=expires_at,
        )
    except AuthorizationError as e:
        event_store.record(
            kind="authorization.failed",
            actor=sender,
            data={"intent_id": intent_id, "error": str(e)},
        )
        return JSONResponse(
            status_code=400,
            content=create_envelope(
                message_type="slagent-402.intent.authorize.failed",
                sender="gateway",
                receiver=sender,
                correlation_id=correlation_id,
                payload={"intent_id": intent_id, "error": str(e)},
            ),
        )

    event_store.record(
        kind="authorization.granted",
        actor=authorizer,
        data={
            "authorization_id": auth.authorization_id,
            "intent_id": intent_id,
            "authorizer": authorizer,
            "policy_id": auth.policy_id,
            "expires_at": expires_at,
        },
    )

    logger.info(
        "AP2 intent authorized: %s → auth=%s by %s",
        intent_id,
        auth.authorization_id,
        authorizer,
    )

    return JSONResponse(content=intent_authorize(
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        intent_id=intent_id,
        authorization_id=auth.authorization_id,
        authorizer=authorizer,
        policy_id=auth.policy_id,
        expires_at=str(expires_at) if expires_at else "",
    ))


def _handle_intent_reject(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle intent.reject: reject an intent."""
    intent_id = payload.get("intent_id", "")
    reason = payload.get("reason", "")

    try:
        intent = auth_store.reject_intent(intent_id, reason)
    except AuthorizationError as e:
        return JSONResponse(
            status_code=400,
            content=create_envelope(
                message_type="slagent-402.error",
                sender="gateway",
                receiver=sender,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            ),
        )

    event_store.record(
        kind="authorization.rejected",
        actor=sender,
        data={"intent_id": intent_id, "reason": reason},
    )

    logger.info("AP2 intent rejected: %s by %s reason=%s", intent_id, sender, reason)

    return JSONResponse(content=create_envelope(
        message_type="slagent-402.intent.rejected",
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        payload={"intent_id": intent_id, "status": "REJECTED", "reason": reason},
    ))


def _handle_settlement_execute(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle settlement.execute: execute settlement (requires valid authorization)."""
    intent_id = payload.get("intent_id", "")
    authorization_id = payload.get("authorization_id", "")
    settlement_id = payload.get("settlement_id", f"settle_{uuid.uuid4().hex[:12]}")

    # Enforce: settlement blocked without valid authorization
    ok, reason = auth_store.validate_for_settlement(intent_id, authorization_id)
    if not ok:
        event_store.record(
            kind="authorization.settlement_blocked",
            actor=sender,
            data={
                "intent_id": intent_id,
                "authorization_id": authorization_id,
                "settlement_id": settlement_id,
                "reason": reason,
            },
        )

        logger.warning(
            "AP2 settlement blocked: intent=%s auth=%s reason=%s",
            intent_id,
            authorization_id,
            reason,
        )

        return JSONResponse(
            status_code=403,
            content=create_envelope(
                message_type="slagent-402.settlement.blocked",
                sender="gateway",
                receiver=sender,
                correlation_id=correlation_id,
                payload={
                    "settlement_id": settlement_id,
                    "intent_id": intent_id,
                    "authorization_id": authorization_id,
                    "status": "BLOCKED",
                    "reason": reason,
                },
            ),
        )

    # Authorization valid — mark as consumed and proceed
    auth_store.mark_settled(intent_id, authorization_id)

    auth = auth_store.get_authorization(authorization_id)
    event_store.record(
        kind="authorization.settlement_executed",
        actor="gateway",
        data={
            "settlement_id": settlement_id,
            "intent_id": intent_id,
            "authorization_id": authorization_id,
            "authorized_by": auth.authorizer if auth else "",
            "authorized_at": str(auth.created_at) if auth else "",
            "policy_id": auth.policy_id if auth else "",
        },
    )

    logger.info(
        "AP2 settlement executed: %s (intent=%s, auth=%s)",
        settlement_id,
        intent_id,
        authorization_id,
    )

    return JSONResponse(content=settlement_execute(
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        settlement_id=settlement_id,
        intent_id=intent_id,
        authorization_id=authorization_id,
    ))


def _handle_receipt_issue(
    sender: str, payload: dict[str, Any], correlation_id: str
) -> JSONResponse:
    """Handle receipt.issue: issue a receipt with authorization audit trail."""
    intent_id = payload.get("intent_id", "")
    request_id = payload.get("request_id", "")
    receipt_id = request_id or f"receipt_{uuid.uuid4().hex[:12]}"

    intent = auth_store.get_intent(intent_id)
    auth = auth_store.get_authorization_for_intent(intent_id) if intent else None

    authorized_by = auth.authorizer if auth else ""
    authorized_at = str(auth.created_at) if auth else ""
    policy_id = auth.policy_id if auth else ""

    if intent:
        auth_store.mark_receipt_issued(intent_id)

    event_store.record(
        kind="authorization.receipt_issued",
        actor="gateway",
        request_id=request_id,
        data={
            "receipt_id": receipt_id,
            "intent_id": intent_id,
            "authorized_by": authorized_by,
            "authorized_at": authorized_at,
            "policy_id": policy_id,
        },
    )

    logger.info(
        "AP2 receipt issued: %s (intent=%s, authorized_by=%s)",
        receipt_id,
        intent_id,
        authorized_by,
    )

    return JSONResponse(content=receipt_issue(
        sender="gateway",
        receiver=sender,
        correlation_id=correlation_id,
        receipt_id=receipt_id,
        request_id=request_id,
        authorized_by=authorized_by,
        authorized_at=authorized_at,
        policy_id=policy_id,
    ))


# ── REST query endpoints ──────────────────────────────────────────────────


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


@router.get("/intents")
async def list_intents(limit: int = 50) -> JSONResponse:
    """List AP2 intents."""
    intents = auth_store.list_intents(limit)
    return JSONResponse(content=[i.to_dict() for i in intents])


@router.get("/intents/{intent_id}")
async def get_intent(intent_id: str) -> JSONResponse:
    """Get a specific AP2 intent."""
    intent = auth_store.get_intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Intent not found")
    auth = auth_store.get_authorization_for_intent(intent_id)
    result = intent.to_dict()
    if auth:
        result["authorization"] = auth.to_dict()
    return JSONResponse(content=result)


@router.get("/authorizations")
async def list_authorizations(limit: int = 50) -> JSONResponse:
    """List AP2 authorizations."""
    auths = auth_store.list_authorizations(limit)
    return JSONResponse(content=[a.to_dict() for a in auths])
