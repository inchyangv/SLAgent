"""SLA-Pay v2 Gateway — FastAPI reverse proxy with metrics, validation, pricing, x402."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.app.config import settings
from gateway.app.metrics import RequestMetrics
from gateway.app.models import Metrics, PricingResult
from gateway.app.pricing import compute_payout
from gateway.app.receipt import build_receipt, generate_request_id, receipt_store
from gateway.app.validators.json_schema import validate_json_schema
from gateway.app.x402 import create_402_response, verify_payment_header

logger = logging.getLogger("sla-gateway")

app = FastAPI(title="SLA-Pay v2 Gateway", version="0.1.0")

# Default mandate for demo (matches PROJECT.md)
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


@app.post("/v1/call")
async def call_endpoint(request: Request) -> JSONResponse:
    """Main proxy endpoint with x402 payment gating."""
    body = await request.body()
    mandate = DEFAULT_MANDATE
    max_price = mandate["max_price"]

    # x402: check for payment
    payment_info = verify_payment_header(request, max_price=max_price)
    if payment_info is None:
        return create_402_response(
            max_price=max_price,
            payment_token_address=settings.payment_token,
            settlement_contract=settings.settlement_contract,
            chain_id=2046399126,
            seller=settings.seller_upstream_url,
        )

    buyer = payment_info["buyer"]

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
            metrics = Metrics(ttft_ms=rm.ttft_ms, latency_ms=rm.latency_ms)
            receipt = build_receipt(
                request_id=request_id,
                mandate_id="",
                buyer=buyer,
                seller="",
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
        mandate_id="",
        buyer=buyer,
        seller=settings.seller_upstream_url,
        gateway_addr="",
        metrics=metrics,
        outcome=outcome,
        validation=validation,
        pricing=pricing,
        request_body=body,
        response_body=seller_body,
    )
    receipt_store.save(receipt)

    logger.info(
        f"Settled: req={request_id} buyer={buyer} "
        f"payout={pricing_decision.payout} refund={pricing_decision.refund} "
        f"rule={pricing_decision.rule_applied}"
    )

    return JSONResponse(
        content={
            "request_id": request_id,
            "seller_response": seller_json,
            "metrics": {"ttft_ms": metrics.ttft_ms, "latency_ms": metrics.latency_ms},
            "validation_passed": overall_pass,
            "payout": str(pricing_decision.payout),
            "refund": str(pricing_decision.refund),
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
