"""BITE v2 demo endpoints — encrypted conditional settlement.

Provides API for:
1. Encrypting settlement terms
2. Evaluating conditions and triggering decrypt
3. Querying encrypted payload lifecycle
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from gateway.app.bite_v2 import (
    ConditionResult,
    bite_engine,
    evaluate_budget_condition,
    evaluate_sla_condition,
)
from gateway.app.events import event_store

logger = logging.getLogger("sla-gateway.bite-v2")

router = APIRouter(prefix="/v1/bite", tags=["bite-v2"])


@router.post("/encrypt")
async def encrypt_terms(body: dict[str, Any]) -> JSONResponse:
    """Encrypt settlement terms for conditional reveal.

    Body:
        terms: dict — settlement terms to encrypt
        encrypted_fields: list[str] — which fields to encrypt (optional)
        condition_type: str — "sla_validation" | "budget_policy" (default: sla_validation)
        condition_params: dict — condition parameters
    """
    terms = body.get("terms", {})
    if not terms:
        raise HTTPException(status_code=400, detail="terms required")

    payload = bite_engine.encrypt_terms(
        terms=terms,
        encrypted_fields=body.get("encrypted_fields"),
        condition_type=body.get("condition_type", "sla_validation"),
        condition_params=body.get("condition_params", {}),
    )

    event_store.record(
        kind="bite_v2.encrypted",
        actor="gateway",
        data={
            "payload_id": payload.payload_id,
            "encrypted_hash": payload.encrypted_hash,
            "encrypted_fields": payload.encrypted_fields,
            "condition_type": payload.condition_type,
        },
    )

    return JSONResponse(content={
        "payload_id": payload.payload_id,
        "encrypted_hash": payload.encrypted_hash,
        "encrypted_fields": payload.encrypted_fields,
        "condition_type": payload.condition_type,
        "status": payload.status,
    })


@router.post("/evaluate/{payload_id}")
async def evaluate_and_decrypt(payload_id: str, body: dict[str, Any]) -> JSONResponse:
    """Evaluate condition and decrypt if met.

    Body for sla_validation:
        validation_passed: bool
        latency_ms: int
        max_latency_ms: int (optional, default 8000)
        success: bool (optional, default true)

    Body for budget_policy:
        price: int
        budget_remaining: int
        max_step_price: int (optional)
    """
    payload = bite_engine.get_payload(payload_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Payload not found")

    triggered_by = body.get("triggered_by", "gateway")
    condition_type = payload.condition_type

    if condition_type == "sla_validation":
        condition = evaluate_sla_condition(
            validation_passed=body.get("validation_passed", False),
            latency_ms=body.get("latency_ms", 0),
            max_latency_ms=body.get("max_latency_ms", 8000),
            success=body.get("success", True),
        )
    elif condition_type == "budget_policy":
        condition = evaluate_budget_condition(
            price=body.get("price", 0),
            budget_remaining=body.get("budget_remaining", 0),
            max_step_price=body.get("max_step_price", 0),
        )
    else:
        # Composite: evaluate both
        sla_cond = evaluate_sla_condition(
            validation_passed=body.get("validation_passed", False),
            latency_ms=body.get("latency_ms", 0),
            max_latency_ms=body.get("max_latency_ms", 8000),
            success=body.get("success", True),
        )
        budget_cond = evaluate_budget_condition(
            price=body.get("price", 0),
            budget_remaining=body.get("budget_remaining", 0),
            max_step_price=body.get("max_step_price", 0),
        )
        all_passed = sla_cond.passed and budget_cond.passed
        condition = ConditionResult(
            passed=all_passed,
            condition_type="composite",
            checks=sla_cond.checks + budget_cond.checks,
            reason_code=sla_cond.reason_code or budget_cond.reason_code,
        )

    updated, decrypted = bite_engine.evaluate_and_decrypt(
        payload_id, condition, triggered_by=triggered_by,
    )

    event_kind = "bite_v2.decrypted" if decrypted else "bite_v2.condition_failed"
    event_store.record(
        kind=event_kind,
        actor=triggered_by,
        data={
            "payload_id": payload_id,
            "condition_passed": condition.passed,
            "condition_type": condition.condition_type,
            "reason_code": condition.reason_code,
            "encrypted_hash": updated.encrypted_hash,
        },
    )

    result: dict[str, Any] = {
        "payload_id": payload_id,
        "status": updated.status,
        "condition_passed": condition.passed,
        "condition_result": condition.to_dict(),
        "encrypted_hash": updated.encrypted_hash,
    }

    if decrypted:
        result["decrypted_terms"] = decrypted
        result["decrypt_time"] = updated.decrypted_at
    else:
        result["reason_code"] = updated.reason_code

    return JSONResponse(content=result)


@router.post("/settle/{payload_id}")
async def mark_settled(payload_id: str) -> JSONResponse:
    """Mark an encrypted payload as settled after successful on-chain settlement."""
    payload = bite_engine.mark_settled(payload_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Payload not found or not decrypted")

    event_store.record(
        kind="bite_v2.settled",
        actor="gateway",
        data={
            "payload_id": payload_id,
            "encrypted_hash": payload.encrypted_hash,
            "settled_at": payload.settled_at,
        },
    )

    return JSONResponse(content={
        "payload_id": payload_id,
        "status": payload.status,
        "settled_at": payload.settled_at,
    })


@router.get("/payloads")
async def list_payloads(limit: int = 50) -> JSONResponse:
    """List encrypted payloads."""
    payloads = bite_engine.list_payloads(limit)
    return JSONResponse(content=[p.to_dict() for p in payloads])


@router.get("/payloads/{payload_id}")
async def get_payload(payload_id: str) -> JSONResponse:
    """Get encrypted payload details."""
    payload = bite_engine.get_payload(payload_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Payload not found")
    return JSONResponse(content=payload.to_dict())
