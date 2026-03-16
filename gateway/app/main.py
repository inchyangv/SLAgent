"""SLAgent-402 Gateway — FastAPI reverse proxy with deposit-first settlement."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from eth_account import Account
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from web3 import Web3

from gateway.app.config import settings
from gateway.app.deposit_verifier import verify_deposit_submission
from gateway.app.events import event_store
from gateway.app.mandates import mandate_store
from gateway.app.metrics import RequestMetrics
from gateway.app.models import Metrics, PricingResult
from gateway.app.pricing import PricingDecision, compute_payout
from gateway.app.receipt import build_receipt, generate_request_id, receipt_store
from gateway.app.llm_policy import evaluate_sla_with_gemini, suggest_mandate_with_gemini
from gateway.app.settlement_client import (
    settle_request,
    submit_dispute_open,
    submit_dispute_resolve,
    submit_finalize,
)
from gateway.app.validators.json_schema import validate_json_schema

logger = logging.getLogger("sla-gateway")

app = FastAPI(title="SLAgent-402 Gateway", version="0.2.0")

# Demo behavior toggles
_DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
_DEMO_INSTANT_PAYOUT = os.getenv("DEMO_INSTANT_PAYOUT", "true").lower() == "true"

# CORS — enabled in demo mode so dashboard can call API from any origin
_DEMO_CORS = os.getenv("DEMO_CORS", "true").lower() == "true"
if _DEMO_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

# Minimal ERC20 view ABI for balance dashboard.
ERC20_VIEW_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


def _to_checksum_or_empty(addr: str) -> str:
    """Return checksum address if valid EVM address, otherwise empty string."""
    if addr and Web3.is_address(addr):
        return Web3.to_checksum_address(addr)
    return ""


def _gateway_address_from_private_key() -> str:
    """Derive gateway address from env private key if available."""
    if not settings.gateway_private_key:
        return ""
    try:
        return Account.from_key(settings.gateway_private_key).address
    except Exception:
        return ""


def _token_symbol() -> str:
    return os.getenv("SLA_TOKEN_SYMBOL", "USDT")


def _default_address(fill: str) -> str:
    return "0x" + (fill * 40)


def _resolve_balance_addresses() -> dict[str, str]:
    """Resolve buyer/seller/gateway addresses for the dashboard balance panel."""
    latest_mandate = mandate_store.list_all(limit=1)
    latest = latest_mandate[0] if latest_mandate else {}

    buyer = _to_checksum_or_empty(settings.buyer_address) or _to_checksum_or_empty(latest.get("buyer", ""))
    seller = _to_checksum_or_empty(settings.seller_address) or _to_checksum_or_empty(latest.get("seller", ""))
    gateway = _to_checksum_or_empty(_gateway_address_from_private_key())

    # Fallback to the latest receipt when env/mandate addresses are missing.
    if not buyer or not seller:
        recent = receipt_store.list_recent(limit=1)
        if recent:
            last = recent[0]
            if not buyer:
                buyer = _to_checksum_or_empty(last.buyer)
            if not seller:
                seller = _to_checksum_or_empty(last.seller)

    return {"buyer": buyer, "seller": seller, "gateway": gateway}


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/balances")
def get_balances() -> JSONResponse:
    """Read on-chain settlement-token balances for buyer/seller/gateway."""
    roles = _resolve_balance_addresses()
    token_addr = _to_checksum_or_empty(settings.payment_token)

    payload: dict[str, Any] = {
        "available": False,
        "network": {
            "chain_id": settings.chain_id,
            "rpc_url": settings.chain_rpc_url,
        },
        "token": {
            "address": token_addr or settings.payment_token,
            "symbol": _token_symbol(),
            "decimals": 6,
        },
        "roles": {
            role: {"address": addr, "balance_raw": None, "balance": None}
            for role, addr in roles.items()
        },
        "updated_at": int(time.time()),
    }

    if not token_addr:
        payload["error"] = "PAYMENT_TOKEN_ADDRESS is missing or invalid."
        return JSONResponse(content=payload)

    try:
        w3 = Web3(Web3.HTTPProvider(settings.chain_rpc_url, request_kwargs={"timeout": 6}))
        if not w3.is_connected():
            raise RuntimeError("Failed to connect RPC")

        token = w3.eth.contract(address=token_addr, abi=ERC20_VIEW_ABI)

        decimals = 6
        symbol = _token_symbol()
        try:
            decimals = int(token.functions.decimals().call())
        except Exception:
            pass
        try:
            symbol = str(token.functions.symbol().call())
        except Exception:
            pass

        payload["token"]["decimals"] = decimals
        payload["token"]["symbol"] = symbol

        for role, addr in roles.items():
            if not addr:
                continue
            raw = int(token.functions.balanceOf(addr).call())
            payload["roles"][role]["balance_raw"] = str(raw)
            payload["roles"][role]["balance"] = f"{raw / (10 ** decimals):.{min(decimals, 6)}f}"

        payload["available"] = True
        payload["updated_at"] = int(time.time())
        return JSONResponse(content=payload)
    except Exception as e:
        logger.warning("Balance fetch failed: %s", e)
        payload["error"] = str(e)
        return JSONResponse(content=payload)


# --- Mandate endpoints ---


@app.post("/v1/mandates")
async def register_mandate(request: Request) -> JSONResponse:
    """Register a negotiated mandate. Returns the stored mandate with mandate_id."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Mandate must be a JSON object")
    mandate = mandate_store.register(body)
    mid = mandate.get("mandate_id", "")
    tiers = mandate.get("bonus_rules", {}).get("tiers", [])
    validators = mandate.get("validators", [])
    event_store.record(
        kind="negotiation.mandate_registered", actor="gateway", mandate_id=mid,
        data={
            "offer_id": mandate.get("offer_id"),
            "max_price": mandate.get("max_price"),
            "base_pay": mandate.get("base_pay"),
            "timeout_ms": mandate.get("timeout_ms"),
            "validators": validators,
            "tiers": tiers,
            "buyer": mandate.get("buyer"),
        },
    )
    logger.info(f"Mandate registered: {mid}")
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


@app.post("/v1/negotiation/suggest")
async def suggest_negotiation_terms(request: Request) -> JSONResponse:
    """Return Gemini-driven SLA/price negotiation suggestions.

    Body:
      {
        "mandate": {...},
        "seller_capabilities": {...}
      }
    """
    body = await request.json()
    mandate = body.get("mandate", body if isinstance(body, dict) else {})
    if not isinstance(mandate, dict):
        raise HTTPException(status_code=400, detail="mandate must be a JSON object")
    seller_caps = body.get("seller_capabilities", {}) if isinstance(body, dict) else {}
    scenario_tag = ""
    if isinstance(body, dict):
        scenario_tag = str(body.get("scenario", "") or body.get("scenario_tag", "")).strip().lower()

    suggestion = await suggest_mandate_with_gemini(
        mandate=mandate,
        seller_capabilities=seller_caps if isinstance(seller_caps, dict) else {},
        scenario_tag=scenario_tag,
    )
    if not suggestion:
        return JSONResponse(content={"mode": "disabled", "suggestion": None})

    event_store.record(
        kind="negotiation.llm_suggested",
        actor="gateway",
        mandate_id=mandate.get("mandate_id", ""),
        data={
            "accepted": suggestion.get("accepted"),
            "summary": suggestion.get("summary"),
            "model": suggestion.get("model"),
        },
    )
    return JSONResponse(content=suggestion)


@app.post("/v1/call")
async def call_endpoint(request: Request) -> JSONResponse:
    """Main proxy endpoint with deposit-first settlement authorization.

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
    request_id_hint = str(payload.get("request_id", "")).strip()
    request_id = request_id_hint or generate_request_id()
    buyer = str(
        mandate.get("buyer")
        or payload.get("buyer")
        or settings.buyer_address
        or _default_address("1")
    ).strip()
    deposit_header = request.headers.get("X-DEPOSIT-TX-HASH")
    deposit_body = str(payload.get("deposit_tx_hash", "")).strip() or None
    deposit_tx = deposit_header or deposit_body or None
    deposit_source = "header" if deposit_header else "body" if deposit_body else "missing"

    deposit_info = verify_deposit_submission(
        request_id=request_id,
        buyer=buyer,
        max_price=max_price,
        deposit_tx_hash=deposit_tx,
        chain_rpc_url=settings.chain_rpc_url,
        settlement_contract=settings.settlement_contract,
        source=deposit_source,
    )
    if deposit_info is None:
        event_store.record(
            kind="payment.deposit_required",
            actor="gateway",
            request_id=request_id,
            mandate_id=mandate_id,
            data={
                "max_price": max_price,
                "buyer": buyer,
                "chain_configured": bool(settings.chain_rpc_url and settings.settlement_contract),
            },
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "Deposit Required",
                "request_id": request_id,
                "buyer": buyer,
                "max_price": max_price,
                "settlement_contract": settings.settlement_contract,
                "detail": "Submit deposit() before calling /v1/call when chain settlement is enabled.",
            },
        )

    seller_addr = mandate.get("seller") or settings.seller_address or settings.seller_upstream_url
    event_store.record(
        kind="payment.verified",
        actor="gateway",
        request_id=request_id,
        mandate_id=mandate_id,
        data={
            "buyer": buyer,
            "mode": deposit_info.get("mode"),
            "deposit_tx_hash": deposit_info.get("tx_hash"),
        },
    )
    rm = RequestMetrics()
    rm.start()

    # Extract mode and delay_ms from query or body (default: fast, 0)
    mode = request.query_params.get("mode") or payload.get("mode", "fast")
    delay_ms = request.query_params.get("delay_ms") or payload.get("delay_ms", 0)
    scenario_tag = str(payload.get("scenario_tag", "") or payload.get("scenario", "")).strip().lower()
    if not scenario_tag:
        if mode in ("invalid", "error", "timeout"):
            scenario_tag = "breaches"
        elif mode == "slow" or int(delay_ms) >= 3000:
            scenario_tag = "slow"
        else:
            scenario_tag = "happy"

    # Forward to seller with mode + delay_ms as query param + body
    seller_payload = {**payload, "mode": mode, "delay_ms": int(delay_ms)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            seller_resp = await client.post(
                f"{settings.seller_upstream_url}/seller/call?mode={mode}&delay_ms={int(delay_ms)}",
                json=seller_payload,
            )
            rm.mark_first_token()
            seller_body = seller_resp.content
            seller_json = seller_resp.json()
            rm.mark_done()
        except httpx.RequestError as e:
            rm.mark_done()
            event_store.record(
                kind="execution.upstream_error", actor="gateway", request_id=request_id,
                mandate_id=mandate_id, data={"error": str(e)},
            )
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
                t_request_received=rm.t_request_received,
                t_first_token=rm.t_first_token,
                t_response_done=rm.t_response_done,
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

    event_store.record(
        kind="execution.seller_response", actor="gateway", request_id=request_id,
        mandate_id=mandate_id,
        data={"success": success, "latency_ms": metrics.latency_ms, "ttft_ms": metrics.ttft_ms},
    )
    event_store.record(
        kind=f"validation.{'schema_pass' if overall_pass else 'schema_fail'}",
        actor="gateway", request_id=request_id, mandate_id=mandate_id,
        data={"overall_pass": overall_pass, "results_count": len(validation_results)},
    )

    # Compute baseline pricing (deterministic rules).
    pricing_decision = compute_payout(
        mandate=mandate,
        latency_ms=metrics.latency_ms,
        success=success,
        validation_pass=overall_pass,
    )

    # Optional Gemini policy layer:
    # - can downgrade SLA pass/fail judgement
    # - can negotiate payout recommendation within hard bounds [0, max_price]
    llm_policy = await evaluate_sla_with_gemini(
        mandate=mandate,
        seller_response=seller_json if isinstance(seller_json, dict) else {},
        success=success,
        schema_validation_pass=overall_pass,
        latency_ms=metrics.latency_ms,
        mode=mode,
        scenario_tag=scenario_tag,
    )
    if llm_policy:
        llm_sla_pass = llm_policy.get("sla_pass")
        if llm_sla_pass is False and overall_pass:
            overall_pass = False
            validation["overall_pass"] = False
            validation_results.append({
                "type": "llm_sla",
                "schema_id": None,
                "pass": False,
                "details": llm_policy.get("reason", "llm judged sla fail"),
            })
            pricing_decision = compute_payout(
                mandate=mandate,
                latency_ms=metrics.latency_ms,
                success=success,
                validation_pass=False,
            )

        llm_payout = llm_policy.get("recommended_payout")
        if (
            isinstance(llm_payout, int)
            and success
            and overall_pass
        ):
            max_price_int = int(pricing_decision.max_price)
            bounded = max(0, min(llm_payout, max_price_int))
            if bounded != pricing_decision.payout:
                llm_breaches = list(pricing_decision.breach_reasons)
                if bounded < max_price_int and "BREACH_LLM_NEGOTIATED_DOWN" not in llm_breaches:
                    llm_breaches.append("BREACH_LLM_NEGOTIATED_DOWN")
                pricing_decision = PricingDecision(
                    max_price=max_price_int,
                    payout=bounded,
                    refund=max_price_int - bounded,
                    rule_applied="llm_negotiated",
                    breach_reasons=llm_breaches,
                )

        event_store.record(
            kind="llm.sla_judged",
            actor="gateway",
            request_id=request_id,
            mandate_id=mandate_id,
            data={
                "model": llm_policy.get("model"),
                "sla_pass": llm_policy.get("sla_pass"),
                "recommended_payout": llm_policy.get("recommended_payout"),
                "confidence": llm_policy.get("confidence"),
                "reason": llm_policy.get("reason"),
                "scenario_tag": scenario_tag,
            },
        )

    breach_reasons = list(pricing_decision.breach_reasons)
    outcome["llm_policy"] = llm_policy or {"mode": "disabled"}
    outcome["llm_policy_scenario"] = scenario_tag
    pricing = PricingResult(
        max_price=str(pricing_decision.max_price),
        computed_payout=str(pricing_decision.payout),
        computed_refund=str(pricing_decision.refund),
        rule_applied=pricing_decision.rule_applied,
        breach_reasons=breach_reasons,
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
        t_request_received=rm.t_request_received,
        t_first_token=rm.t_first_token,
        t_response_done=rm.t_response_done,
        breach_reasons=breach_reasons,
    )

    event_store.record(
        kind="pricing.computed", actor="gateway", request_id=request_id,
        mandate_id=mandate_id,
        data={
            "payout": pricing_decision.payout, "refund": pricing_decision.refund,
            "rule": pricing_decision.rule_applied,
        },
    )

    # Record SLA breach event if any breaches detected
    if breach_reasons:
        event_store.record(
            kind="sla.breach_detected", actor="gateway", request_id=request_id,
            mandate_id=mandate_id,
            data={
                "breach_reasons": breach_reasons,
                "payout": pricing_decision.payout,
                "max_price": pricing_decision.max_price,
                "latency_ms": metrics.latency_ms,
                "validation_pass": overall_pass,
            },
        )
    event_store.record(
        kind="receipt.hash_computed", actor="gateway", request_id=request_id,
        mandate_id=mandate_id, data={"receipt_hash": receipt.hashes.get("receipt_hash", "")},
    )

    # Buyer-funded escrow: buyer submits deposit before paid request.
    # Gateway only finalizes settlement using the deposited escrow.
    receipt_hash = receipt.hashes.get("receipt_hash", "")
    event_store.record(
        kind="chain.deposit_submitted", actor="buyer", request_id=request_id,
        mandate_id=mandate_id,
        data={
            "tx_hash": deposit_tx,
            "amount": pricing_decision.max_price,
            "source": deposit_info.get("source"),
            "verification_mode": deposit_info.get("mode"),
        },
    )

    # Step 1: Settle (distribute payout/refund) from already-deposited escrow
    settlement_result = settle_request(
        request_id=request_id,
        mandate_id=mandate_id,
        buyer=buyer,
        seller=seller_addr,
        max_price=pricing_decision.max_price,
        payout=pricing_decision.payout,
        receipt_hash=receipt_hash,
    )
    if settlement_result.get("error"):
        event_store.record(
            kind="chain.settlement_failed", actor="gateway", request_id=request_id,
            mandate_id=mandate_id,
            data={"error": settlement_result.get("error")},
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "settlement_failed",
                "reason": settlement_result.get("error"),
                "request_id": request_id,
            },
        )
    event_store.record(
        kind="chain.settlement_submitted", actor="gateway", request_id=request_id,
        mandate_id=mandate_id,
        data={"tx_hash": settlement_result.get("tx_hash"), "mode": settlement_result.get("mode")},
    )

    instant_open_tx = None
    instant_resolve_tx = None
    instant_payout_mode = None
    # Demo-only: force immediate payout/refund visibility by opening+resolving dispute
    # (resolver == gateway on current demo deployment).
    if _DEMO_MODE and _DEMO_INSTANT_PAYOUT and settlement_result.get("mode") == "chain":
        open_result = submit_dispute_open(request_id=request_id)
        instant_open_tx = open_result.get("tx_hash")
        event_store.record(
            kind="chain.instant_payout_dispute_opened",
            actor="gateway",
            request_id=request_id,
            mandate_id=mandate_id,
            data={"tx_hash": instant_open_tx, "mode": open_result.get("mode")},
        )
        resolve_result = submit_dispute_resolve(
            request_id=request_id,
            final_payout=pricing_decision.payout,
        )
        instant_resolve_tx = resolve_result.get("tx_hash")
        instant_payout_mode = resolve_result.get("mode")
        event_store.record(
            kind="chain.instant_payout_resolved",
            actor="gateway",
            request_id=request_id,
            mandate_id=mandate_id,
            data={
                "tx_hash": instant_resolve_tx,
                "mode": instant_payout_mode,
                "final_payout": pricing_decision.payout,
            },
        )

    # Update receipt with settlement info
    receipt.signatures = {"gateway_signature": settlement_result["gateway_signature"]}
    receipt_store.save(receipt)

    # Auto-submit gateway attestation
    if settings.gateway_private_key and receipt_hash:
        try:
            gw_attest_sig = sign_receipt_hash(receipt_hash, settings.gateway_private_key)
            attestation_store.add_attestation(
                request_id=request_id,
                receipt_hash=receipt_hash,
                role="gateway",
                signature=gw_attest_sig,
            )
        except Exception as e:
            logger.warning(f"Gateway auto-attestation failed: {e}")

    settle_tx = settlement_result.get("tx_hash")
    # For backward compat, tx_hash = settle tx (or deposit tx if settle was mock)
    tx_hash = settle_tx or deposit_tx

    logger.info(
        f"Settled: req={request_id} mandate={mandate_id} buyer={buyer} "
        f"payout={pricing_decision.payout} refund={pricing_decision.refund} "
        f"rule={pricing_decision.rule_applied} deposit_tx={deposit_tx} settle_tx={settle_tx}"
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
            "deposit_tx_hash": deposit_tx,
            "settle_tx_hash": settle_tx,
            "instant_dispute_open_tx_hash": instant_open_tx,
            "instant_resolve_tx_hash": instant_resolve_tx,
            "instant_payout_mode": instant_payout_mode,
            "breach_reasons": breach_reasons,
            "llm_policy": llm_policy,
            "scenario_tag": scenario_tag,
        }
    )


@app.get("/v1/receipts")
async def list_receipts(limit: int = 50) -> JSONResponse:
    """List recent receipts (includes attestation status)."""
    receipts = receipt_store.list_recent(limit)
    result = []
    for r in receipts:
        data = r.model_dump()
        data["attestations"] = attestation_store.get_attestations(r.request_id)
        result.append(data)
    return JSONResponse(content=result)


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
    """Retrieve a receipt by request_id (includes attestation status)."""
    receipt = receipt_store.get(request_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    data = receipt.model_dump()
    data["attestations"] = attestation_store.get_attestations(request_id)
    return JSONResponse(content=data)


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

from gateway.app.attestation import attestation_store, sign_receipt_hash, verify_receipt_signature


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

    event_store.record(
        kind=f"attestation.{'verified' if result.get('verified') else 'failed'}",
        actor=role, request_id=request_id,
        data={"signer": result.get("signer"), "verified": result.get("verified")},
    )

    return JSONResponse(content=result)


@app.get("/v1/receipts/{request_id}/attestations")
async def get_attestations(request_id: str) -> JSONResponse:
    """Get all attestations for a receipt."""
    return JSONResponse(content=attestation_store.get_attestations(request_id))


# --- Event Ledger API ---


@app.get("/v1/events")
async def list_events(
    request_id: str | None = None,
    mandate_id: str | None = None,
    kind: str | None = None,
    actor: str | None = None,
    limit: int = 200,
) -> JSONResponse:
    """Query event ledger with optional filters."""
    events = event_store.query(
        request_id=request_id, mandate_id=mandate_id,
        kind=kind, actor=actor, limit=limit,
    )
    return JSONResponse(content={
        "events": [e.to_dict() for e in events],
        "count": len(events),
    })


@app.get("/v1/events/export")
async def export_events() -> JSONResponse:
    """Export all events as JSONL."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=event_store.export_jsonl(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=events.jsonl"},
    )


# --- Demo Offers API (SLA offer catalog) ---

from gateway.app.offers import get_offer, get_offers


@app.get("/v1/demo/offers")
async def list_offers() -> JSONResponse:
    """List available SLA offer presets (Bronze / Silver / Gold)."""
    return JSONResponse(content={"offers": get_offers()})


@app.get("/v1/demo/offers/{offer_id}")
async def get_offer_detail(offer_id: str) -> JSONResponse:
    """Get a specific SLA offer by ID."""
    offer = get_offer(offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer not found: {offer_id}")
    return JSONResponse(content=offer)


# --- Demo Run API (server-side buyer agent orchestration) ---


@app.post("/v1/demo/run")
async def demo_run(request: Request) -> JSONResponse:
    """Run buyer agent flow server-side (demo only).

    Body: { "modes": ["fast","slow","invalid"], "seller_url": "..." }
    Returns: { "results": [...], "summary": {...} }

    Only available when DEMO_MODE=true (default for local dev).
    """
    if not _DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode is disabled")

    body = await request.json()
    modes = body.get("modes", ["fast", "slow", "invalid"])
    seller_url = body.get("seller_url", settings.seller_upstream_url)
    sim_delay_ms = int(body.get("delay_ms", 0))
    simulator = body.get("simulator", {})
    scenario_tag = str(body.get("scenario", "") or simulator.get("preset", "")).strip().lower()
    negotiate_raw = body.get("negotiate", True)
    negotiate = negotiate_raw if isinstance(negotiate_raw, bool) else str(negotiate_raw).lower() not in ("0", "false", "no")

    # Record simulator settings event
    event_store.record(
        kind="simulator.settings_applied", actor="gateway",
        data={
            "modes": modes,
            "delay_ms": sim_delay_ms,
            "simulator": simulator,
        },
    )

    buyer_key = os.getenv("BUYER_PRIVATE_KEY")
    buyer_addr = os.getenv("BUYER_ADDRESS", "0x1111111111111111111111111111111111111111")

    try:
        from buyer_agent.client import BuyerAgent, InvariantViolation
    except ImportError:
        raise HTTPException(status_code=500, detail="buyer_agent module not available")

    agent = BuyerAgent(
        gateway_url=f"http://127.0.0.1:{settings.port}",
        seller_url=seller_url,
        buyer_address=buyer_addr,
        buyer_private_key=buyer_key,
    )

    steps: list[dict] = []

    # Step 1: Negotiate (optional for autonomous tick mode)
    if negotiate:
        try:
            neg = await agent.negotiate_mandate(scenario_tag=(scenario_tag or "happy"))
            steps.append({
                "step": "negotiate",
                "ok": True,
                "mandate_id": neg.mandate_id,
                "seller_accepted": neg.seller_accepted,
                "summary": neg.summary,
            })
        except Exception as e:
            steps.append({"step": "negotiate", "ok": False, "error": str(e)})
    else:
        steps.append({"step": "negotiate", "ok": True, "skipped": True, "reason": "negotiate=false"})

    # Step 2: Execute scenarios with simulator delay
    results: list[dict] = []
    for mode in modes:
        try:
            result = await agent.call(mode=mode, delay_ms=sim_delay_ms, scenario_tag=(scenario_tag or mode))
            attest = result.attestation_status.get("status", {})
            results.append({
                "mode": mode,
                "ok": result.success,
                "request_id": result.request_id,
                "payout": result.payout,
                "refund": result.refund,
                "max_price": result.max_price,
                "validation_passed": result.validation_passed,
                "receipt_hash": result.receipt_hash,
                "tx_hash": result.tx_hash,
                "deposit_tx_hash": result.deposit_tx_hash,
                "settle_tx_hash": result.settle_tx_hash,
                "llm_policy": result.llm_policy,
                "latency_ms": result.metrics.get("latency_ms"),
                "delay_ms_applied": sim_delay_ms,
                "scenario_tag": scenario_tag or mode,
                "attestations": {
                    "count": attest.get("count", 0),
                    "complete": attest.get("complete", False),
                    "parties": attest.get("parties_signed", []),
                },
            })
            steps.append({"step": f"call:{mode}", "ok": True, "request_id": result.request_id})
        except InvariantViolation as e:
            steps.append({"step": f"call:{mode}", "ok": False, "error": str(e)})
            results.append({"mode": mode, "ok": False, "error": str(e)})
        except Exception as e:
            steps.append({"step": f"call:{mode}", "ok": False, "error": str(e)})
            results.append({"mode": mode, "ok": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("ok"))

    return JSONResponse(content={
        "steps": steps,
        "results": results,
        "summary": {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
        },
        "simulator": {"delay_ms": sim_delay_ms, "modes": modes},
    })


# --- Static file serving for dashboard (same-origin, no CORS needed) ---
# Mount AFTER all API routes so /v1/* takes precedence.

_dashboard_dir = Path(__file__).resolve().parent.parent.parent / "dashboard"
if _dashboard_dir.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")
