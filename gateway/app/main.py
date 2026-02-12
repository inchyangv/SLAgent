"""SLA-Pay v2 Gateway — FastAPI reverse proxy with metrics and receipts."""

from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.app.config import settings
from gateway.app.metrics import RequestMetrics
from gateway.app.models import CallRequest, CallResponse, Metrics, PricingResult
from gateway.app.receipt import build_receipt, generate_request_id, receipt_store

app = FastAPI(title="SLA-Pay v2 Gateway", version="0.1.0")


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/call")
async def call_endpoint(request: Request) -> JSONResponse:
    """Main proxy endpoint. Forwards to seller, measures metrics, builds receipt."""
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    request_id = generate_request_id()
    rm = RequestMetrics()
    rm.start()

    # Forward to seller
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            seller_resp = await client.post(
                f"{settings.seller_upstream_url}/seller/call",
                json=payload,
            )
            rm.mark_first_token()
            seller_body = seller_resp.content
            seller_json = seller_resp.json()
            rm.mark_done()
        except httpx.RequestError as e:
            rm.mark_done()
            # Build failure receipt
            metrics = Metrics(ttft_ms=rm.ttft_ms, latency_ms=rm.latency_ms)
            receipt = build_receipt(
                request_id=request_id,
                mandate_id="",
                buyer="",
                seller="",
                gateway_addr="",
                metrics=metrics,
                outcome={"success": False, "error_code": "upstream_error"},
                validation={"overall_pass": False, "results": []},
                pricing=PricingResult(
                    max_price="0",
                    computed_payout="0",
                    computed_refund="0",
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

    # Placeholder: validation and pricing will be wired in later tickets
    outcome: dict[str, Any] = {"success": True, "error_code": None}
    validation: dict[str, Any] = {"overall_pass": True, "results": []}
    pricing = PricingResult(
        max_price="0",
        computed_payout="0",
        computed_refund="0",
        rule_applied="placeholder",
    )

    receipt = build_receipt(
        request_id=request_id,
        mandate_id="",
        buyer="",
        seller="",
        gateway_addr="",
        metrics=metrics,
        outcome=outcome,
        validation=validation,
        pricing=pricing,
        request_body=body,
        response_body=seller_body,
    )
    receipt_store.save(receipt)

    return JSONResponse(
        content={
            "request_id": request_id,
            "seller_response": seller_json,
            "metrics": {"ttft_ms": metrics.ttft_ms, "latency_ms": metrics.latency_ms},
            "validation_passed": True,
            "receipt_hash": receipt.hashes.get("receipt_hash", ""),
        }
    )


@app.get("/v1/receipts/{request_id}")
async def get_receipt(request_id: str) -> JSONResponse:
    """Retrieve a receipt by request_id."""
    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return JSONResponse(content=receipt.model_dump())


@app.get("/v1/receipts")
async def list_receipts(limit: int = 50) -> JSONResponse:
    """List recent receipts."""
    receipts = receipt_store.list_recent(limit)
    return JSONResponse(content=[r.model_dump() for r in receipts])
