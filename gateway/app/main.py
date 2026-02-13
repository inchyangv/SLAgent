"""SLA-Pay v2 Gateway — FastAPI reverse proxy with metrics, validation, pricing, x402."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.app.config import settings
from gateway.app.mandates import mandate_store
from gateway.app.metrics import RequestMetrics
from gateway.app.models import Metrics, PricingResult
from gateway.app.pricing import compute_payout
from gateway.app.receipt import build_receipt, generate_request_id, receipt_store
from gateway.app.settlement_client import (
    settle_request,
    submit_dispute_open,
    submit_dispute_resolve,
    submit_finalize,
)
from gateway.app.validators.json_schema import validate_json_schema
from gateway.app.x402 import create_402_response, verify_payment_header

logger = logging.getLogger("sla-gateway")

app = FastAPI(title="SLA-Pay v2 Gateway", version="0.2.0")

# A2A/AP2 protocol routes
from gateway.app.a2a.routes import router as a2a_router
app.include_router(a2a_router)

# Default mandate for demo fallback (matches PROJECT.md)
DEFAULT_MANDATE = {
    "max_price": "100000",
    "base_pay": "60000",
    "bonus_rules": {
        "type": "latency_tiers",
        "tiers": [
            {"lte_ms": 2000, "payout": "100000"},
            {"lte_ms": 5000, "payout": "80000"},
            {"lte_ms": 999999999, "payout": "60000"},
        ],
    },
    "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
}


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Mandate endpoints ---


@app.post("/v1/mandates")
async def register_mandate(request: Request) -> JSONResponse:
    """Register a negotiated mandate. Returns the stored mandate with mandate_id."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Mandate must be a JSON object")
    mandate = mandate_store.register(body)
    logger.info(f"Mandate registered: {mandate.get('mandate_id', '')}")
    return JSONResponse(content=mandate)


@app.get("/v1/mandates")
async def list_mandates(limit: int = 50) -> JSONResponse:
    """List registered mandates."""
    mandates = mandate_store.list_all(limit)
    return JSONResponse(content={"mandates": mandates, "count": mandate_store.count()})


@app.get("/v1/mandates/{mandate_id}")
async def get_mandate(mandate_id: str) -> JSONResponse:
    """Get a mandate by ID."""
    mandate = mandate_store.get(mandate_id)
    if mandate is None:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return JSONResponse(content=mandate)


@app.post("/v1/call")
async def call_endpoint(request: Request) -> JSONResponse:
    """Main proxy endpoint with x402 payment gating.

    Requires mandate_id in body. Falls back to DEFAULT_MANDATE if not provided
    (for backward compatibility with existing demo scripts).
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Resolve mandate: look up by mandate_id or fall back to default
    mandate_id = payload.get("mandate_id", "")
    if mandate_id:
        mandate = mandate_store.get(mandate_id)
        if mandate is None:
            raise HTTPException(status_code=400, detail=f"Unknown mandate_id: {mandate_id}")
    else:
        mandate = DEFAULT_MANDATE
        mandate_id = ""

    max_price = mandate["max_price"]

    # x402: check for payment
    payment_info = verify_payment_header(
        request,
        max_price=max_price,
        chain_id=settings.chain_id,
        asset=settings.payment_token,
    )
    if payment_info is None:
        return create_402_response(
            max_price=max_price,
            payment_token_address=settings.payment_token,
            settlement_contract=settings.settlement_contract,
            chain_id=settings.chain_id,
            seller=settings.seller_address or settings.seller_upstream_url,
        )

    buyer = payment_info["buyer"]
    seller_addr = mandate.get("seller") or settings.seller_address or settings.seller_upstream_url
    gateway_addr = settings.gateway_private_key and "" or ""  # filled by settlement_client

    request_id = generate_request_id()
    rm = RequestMetrics()
    rm.start()

    # Extract mode from query or body (default: fast)
    mode = request.query_params.get("mode") or payload.get("mode", "fast")

    # Forward to seller with mode as query param + body
    seller_payload = {**payload, "mode": mode}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            seller_resp = await client.post(
                f"{settings.seller_upstream_url}/seller/call?mode={mode}",
                json=seller_payload,
            )
            rm.mark_first_token()
            seller_body = seller_resp.content
            seller_json = seller_resp.json()
            rm.mark_done()
        except httpx.RequestError as e:
            rm.mark_done()
            metrics = Metrics(ttft_ms=rm.ttft_ms, latency_ms=rm.latency_ms)
            receipt = build_receipt(
                request_id=request_id,
                mandate_id=mandate_id,
                buyer=buyer,
                seller=seller_addr,
                gateway_addr="",
                metrics=metrics,
                outcome={"success": False, "error_code": "upstream_error"},
                validation={"overall_pass": False, "results": []},
                pricing=PricingResult(
                    max_price=max_price,
                    computed_payout="0",
                    computed_refund=max_price,
                    rule_applied="error",
                ),
                request_body=body,
                response_body=b"",
            )
            receipt_store.save(receipt)
            raise HTTPException(
                status_code=502,
                detail={"error": str(e), "request_id": request_id},
            )

    metrics = Metrics(ttft_ms=rm.ttft_ms, latency_ms=rm.latency_ms)

    # Run validators
    success = seller_resp.status_code == 200
    validation_results = []
    overall_pass = True

    if success:
        for v in mandate.get("validators", []):
            if v["type"] == "json_schema":
                result = validate_json_schema(seller_json, v.get("schema_id", ""))
                validation_results.append(result)
                if not result["pass"]:
                    overall_pass = False

    outcome: dict[str, Any] = {"success": success, "error_code": None if success else "http_error"}
    validation: dict[str, Any] = {"overall_pass": overall_pass, "results": validation_results}

    # Compute pricing
    pricing_decision = compute_payout(
        mandate=mandate,
        latency_ms=metrics.latency_ms,
        success=success,
        validation_pass=overall_pass,
    )
    pricing = PricingResult(
        max_price=str(pricing_decision.max_price),
        computed_payout=str(pricing_decision.payout),
        computed_refund=str(pricing_decision.refund),
        rule_applied=pricing_decision.rule_applied,
    )

    receipt = build_receipt(
        request_id=request_id,
        mandate_id=mandate_id,
        buyer=buyer,
        seller=seller_addr,
        gateway_addr="",
        metrics=metrics,
        outcome=outcome,
        validation=validation,
        pricing=pricing,
        request_body=body,
        response_body=seller_body,
    )

    # Submit settlement on-chain
    receipt_hash = receipt.hashes.get("receipt_hash", "")
    settlement_result = settle_request(
        request_id=request_id,
        mandate_id=mandate_id,
        buyer=buyer,
        seller=seller_addr,
        max_price=pricing_decision.max_price,
        payout=pricing_decision.payout,
        receipt_hash=receipt_hash,
    )

    # Update receipt with settlement info
    receipt.signatures = {"gateway_signature": settlement_result["gateway_signature"]}
    receipt_store.save(receipt)

    tx_hash = settlement_result.get("tx_hash")

    logger.info(
        f"Settled: req={request_id} mandate={mandate_id} buyer={buyer} "
        f"payout={pricing_decision.payout} refund={pricing_decision.refund} "
        f"rule={pricing_decision.rule_applied} tx={tx_hash}"
    )

    return JSONResponse(
        content={
            "request_id": request_id,
            "mandate_id": mandate_id,
            "seller_response": seller_json,
            "metrics": {"ttft_ms": metrics.ttft_ms, "latency_ms": metrics.latency_ms},
            "validation_passed": overall_pass,
            "payout": str(pricing_decision.payout),
            "refund": str(pricing_decision.refund),
            "receipt_hash": receipt_hash,
            "tx_hash": tx_hash,
        }
    )


@app.get("/v1/receipts")
async def list_receipts(limit: int = 50) -> JSONResponse:
    """List recent receipts."""
    receipts = receipt_store.list_recent(limit)
    return JSONResponse(content=[r.model_dump() for r in receipts])


@app.get("/v1/receipts/search")
async def search_receipts(
    buyer: str | None = None,
    seller: str | None = None,
    min_payout: int | None = None,
    max_latency_ms: int | None = None,
    validation_pass: bool | None = None,
    rule_applied: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    """Search receipts by indexed fields (buyer, seller, payout, latency, etc.)."""
    receipts = receipt_store.search(
        buyer=buyer,
        seller=seller,
        min_payout=min_payout,
        max_latency_ms=max_latency_ms,
        validation_pass=validation_pass,
        rule_applied=rule_applied,
        limit=limit,
        offset=offset,
    )
    return JSONResponse(content={
        "results": [r.model_dump() for r in receipts],
        "count": len(receipts),
        "limit": limit,
        "offset": offset,
    })


@app.get("/v1/receipts/export")
async def export_receipts() -> JSONResponse:
    """Export all receipts as JSONL."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=receipt_store.export_jsonl(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=receipts.jsonl"},
    )


@app.get("/v1/receipts/{request_id}")
async def get_receipt(request_id: str) -> JSONResponse:
    """Retrieve a receipt by request_id."""
    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return JSONResponse(content=receipt.model_dump())


# --- Dispute endpoints (in-memory cache + on-chain submission) ---

_dispute_state: dict[str, dict] = {}


@app.post("/v1/disputes/open")
async def open_dispute(request: Request) -> JSONResponse:
    """Open a dispute for a settled request."""
    body = await request.json()
    request_id = body.get("request_id", "")

    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if request_id in _dispute_state:
        raise HTTPException(status_code=409, detail="Dispute already open")

    # Submit on-chain (mock if no chain configured)
    chain_result = submit_dispute_open(request_id=request_id)

    _dispute_state[request_id] = {
        "status": "DISPUTED",
        "original_payout": receipt.pricing.computed_payout if receipt.pricing else "0",
        "final_payout": None,
        "open_tx_hash": chain_result.get("tx_hash"),
        "mode": chain_result.get("mode", "mock"),
    }

    logger.info(f"Dispute opened: {request_id} mode={chain_result.get('mode')}")

    return JSONResponse(content={
        "request_id": request_id,
        "dispute_status": "DISPUTED",
        "message": "Dispute opened. Awaiting resolver decision.",
        "tx_hash": chain_result.get("tx_hash"),
    })


@app.post("/v1/disputes/resolve")
async def resolve_dispute(request: Request) -> JSONResponse:
    """Resolve a dispute (resolver only in MVP)."""
    body = await request.json()
    request_id = body.get("request_id", "")
    final_payout = body.get("final_payout")

    if request_id not in _dispute_state:
        raise HTTPException(status_code=404, detail="No open dispute for this request")

    dispute = _dispute_state[request_id]
    if dispute["status"] != "DISPUTED":
        raise HTTPException(status_code=409, detail="Dispute already resolved")

    # Submit on-chain (mock if no chain configured)
    chain_result = submit_dispute_resolve(
        request_id=request_id,
        final_payout=int(final_payout),
    )

    original = dispute["original_payout"]
    dispute["status"] = "RESOLVED"
    dispute["final_payout"] = str(final_payout)
    dispute["resolve_tx_hash"] = chain_result.get("tx_hash")

    logger.info(f"Dispute resolved: {request_id} original={original} final={final_payout}")

    return JSONResponse(content={
        "request_id": request_id,
        "dispute_status": "RESOLVED",
        "original_payout": original,
        "final_payout": str(final_payout),
        "tx_hash": chain_result.get("tx_hash"),
    })


@app.post("/v1/disputes/finalize")
async def finalize_settlement(request: Request) -> JSONResponse:
    """Finalize a settled request after dispute window (no dispute)."""
    body = await request.json()
    request_id = body.get("request_id", "")

    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")

    chain_result = submit_finalize(request_id=request_id)

    if request_id not in _dispute_state:
        _dispute_state[request_id] = {"status": "FINALIZED"}
    else:
        _dispute_state[request_id]["status"] = "FINALIZED"
    _dispute_state[request_id]["finalize_tx_hash"] = chain_result.get("tx_hash")

    logger.info(f"Finalized: {request_id}")

    return JSONResponse(content={
        "request_id": request_id,
        "dispute_status": "FINALIZED",
        "tx_hash": chain_result.get("tx_hash"),
    })


@app.get("/v1/disputes/{request_id}")
async def get_dispute(request_id: str) -> JSONResponse:
    """Get dispute status for a request."""
    if request_id not in _dispute_state:
        return JSONResponse(content={"request_id": request_id, "dispute_status": "NONE"})
    return JSONResponse(content={
        "request_id": request_id,
        **_dispute_state[request_id],
    })


# --- Multi-attestation endpoints (Buyer + Seller + Gateway) ---

from gateway.app.attestation import attestation_store, verify_receipt_signature


@app.post("/v1/receipts/{request_id}/attest")
async def attest_receipt(request_id: str, request: Request) -> JSONResponse:
    """Submit a signature attestation for a receipt.

    Body: { "role": "buyer"|"seller"|"gateway", "signature": "0x...", "address": "0x..." }
    """
    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")

    body = await request.json()
    role = body.get("role", "")
    signature = body.get("signature", "")
    address = body.get("address")

    if role not in ("buyer", "seller", "gateway"):
        raise HTTPException(status_code=400, detail="role must be buyer, seller, or gateway")
    if not signature:
        raise HTTPException(status_code=400, detail="signature is required")

    receipt_hash = receipt.hashes.get("receipt_hash", "")
    if not receipt_hash:
        raise HTTPException(status_code=400, detail="Receipt has no hash")

    result = attestation_store.add_attestation(
        request_id=request_id,
        receipt_hash=receipt_hash,
        role=role,
        signature=signature,
        expected_address=address,
    )

    return JSONResponse(content=result)


@app.get("/v1/receipts/{request_id}/attestations")
async def get_attestations(request_id: str) -> JSONResponse:
    """Get all attestations for a receipt."""
    return JSONResponse(content=attestation_store.get_attestations(request_id))
