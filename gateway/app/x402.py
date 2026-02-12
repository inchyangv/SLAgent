"""x402 Payment Gating — 402 Payment Required challenge flow.

MVP Implementation:
- First request without payment header → 402 with payment details
- Second request with X-PAYMENT header → verify and proceed

For hackathon MVP, we use a simplified local verification strategy:
- Payment token is an HMAC-SHA256 of (request_path + max_price + nonce) signed with a shared secret.
- This simulates the x402 flow without requiring a full on-chain payment verification per-request.
- In production, this would be replaced with actual x402 ERC20 payment proof verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger("sla-gateway.x402")

# MVP: shared secret for HMAC-based payment verification
# In production, this would verify on-chain payment proofs
PAYMENT_SECRET = "sla-pay-v2-demo-secret"


def create_402_response(
    *,
    max_price: str,
    payment_token_address: str,
    settlement_contract: str,
    chain_id: int,
    seller: str,
    scheme: str = "x402",
) -> JSONResponse:
    """Return a 402 Payment Required response with x402-compatible payment details."""
    nonce = str(int(time.time() * 1000))

    payment_details = {
        "scheme": scheme,
        "network": str(chain_id),
        "maxAmountRequired": max_price,
        "resource": settlement_contract,
        "description": "SLA-Pay v2 — pay max_price, receive performance-based refund",
        "payTo": seller,
        "token": payment_token_address,
        "nonce": nonce,
        "extra": {
            "protocol": "sla-pay-v2",
            "version": "1.0",
        },
    }

    return JSONResponse(
        status_code=402,
        content={
            "error": "Payment Required",
            "accepts": [payment_details],
        },
        headers={
            "X-PAYMENT-REQUIRED": "true",
        },
    )


def create_payment_token(
    *,
    path: str,
    max_price: str,
    nonce: str,
    secret: str = PAYMENT_SECRET,
) -> str:
    """Create an HMAC-based payment token (MVP simplified verification)."""
    message = f"{path}:{max_price}:{nonce}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_payment_header(
    request: Request,
    *,
    max_price: str,
    secret: str = PAYMENT_SECRET,
) -> dict[str, Any] | None:
    """Verify the X-PAYMENT header on a request.

    Returns parsed payment info if valid, None if missing/invalid.

    Expected header format (JSON):
        {
            "token": "<hmac_hex>",
            "nonce": "<nonce>",
            "max_price": "<amount>",
            "buyer": "<address>"
        }
    """
    payment_header = request.headers.get("X-PAYMENT")
    if not payment_header:
        return None

    try:
        payment = json.loads(payment_header)
    except json.JSONDecodeError:
        logger.warning("Invalid X-PAYMENT header: not JSON")
        return None

    token = payment.get("token", "")
    nonce = payment.get("nonce", "")
    header_max_price = payment.get("max_price", "")
    buyer = payment.get("buyer", "")

    if not all([token, nonce, buyer]):
        logger.warning("X-PAYMENT header missing required fields")
        return None

    # Verify HMAC
    path = str(request.url.path)
    expected = create_payment_token(
        path=path,
        max_price=header_max_price,
        nonce=nonce,
        secret=secret,
    )

    if not hmac.compare_digest(token, expected):
        logger.warning("X-PAYMENT HMAC verification failed")
        return None

    # Verify max_price matches
    if header_max_price != max_price:
        logger.warning(f"X-PAYMENT max_price mismatch: {header_max_price} != {max_price}")
        return None

    logger.info(f"Payment verified: buyer={buyer}, max_price={max_price}, nonce={nonce}")

    return {
        "buyer": buyer,
        "max_price": max_price,
        "nonce": nonce,
        "verified": True,
    }
