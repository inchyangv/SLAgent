"""x402 Payment Gating — 402 Payment Required challenge flow.

Supports two modes controlled by PAYMENT_MODE env var:
- "hmac":  simplified HMAC-SHA256 token (local dev, no keys needed)
- "x402":  real x402-compatible EIP-3009/EIP-712 signed authorization

In x402 mode:
- 402 response includes EIP-3009-compatible payment requirements
- Client signs a TransferAuthorization via EIP-712 typed data
- Gateway verifies the signature (recovers signer, checks parameters)
- Compatible with Coinbase x402 protocol spec (v1 header format)
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import logging
import os
import time
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("sla-gateway.x402")

# ── Configuration ────────────────────────────────────────────────────────────

PAYMENT_MODE = os.getenv("PAYMENT_MODE", "hmac")  # "hmac" or "x402"
PAYMENT_SECRET = "slagent-402-demo-secret"  # HMAC mode only

def _token_domain() -> tuple[str, str]:
    """Return (name, version) for the EIP-712 domain.

    Note: For USDC on SKALE Base Sepolia (BITE v2 Sandbox 2):
    - name() == "USDC"
    - version() == "" (empty string)
    """
    name = os.getenv("SLA_TOKEN_NAME", "USDC")
    version = os.getenv("SLA_TOKEN_VERSION", "")
    return name, version

# Track used nonces for replay protection (in-memory for MVP)
_used_nonces: set[str] = set()


# ── 402 Response ─────────────────────────────────────────────────────────────


def create_402_response(
    *,
    max_price: str,
    payment_token_address: str,
    settlement_contract: str,
    chain_id: int,
    seller: str,
) -> JSONResponse:
    """Return a 402 Payment Required response with x402-compatible payment details."""
    token_name, token_version = _token_domain()
    payment_details: dict[str, Any] = {
        "scheme": "exact",
        "network": f"eip155:{chain_id}",
        "maxAmountRequired": max_price,
        "resource": settlement_contract,
        "description": "SLAgent-402 — pay max_price, receive performance-based refund",
        "payTo": seller,
        "asset": payment_token_address,
        "maxTimeoutSeconds": 300,
        "extra": {
            "name": token_name,
            "version": token_version,
            "protocol": "slagent-402",
        },
    }

    body = {
        "x402Version": 1,
        "error": "Payment Required",
        "accepts": [payment_details],
    }

    return JSONResponse(
        status_code=402,
        content=body,
        headers={
            "X-PAYMENT-REQUIRED": "true",
        },
    )


# ── HMAC Mode (local dev) ───────────────────────────────────────────────────


def create_payment_token(
    *,
    path: str,
    max_price: str,
    nonce: str,
    secret: str = PAYMENT_SECRET,
) -> str:
    """Create an HMAC-based payment token (simplified local dev mode)."""
    message = f"{path}:{max_price}:{nonce}"
    return hmac_mod.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _verify_hmac(request: Request, *, max_price: str) -> dict[str, Any] | None:
    """Verify HMAC-based X-PAYMENT header."""
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

    path = str(request.url.path)
    expected = create_payment_token(path=path, max_price=header_max_price, nonce=nonce)

    if not hmac_mod.compare_digest(token, expected):
        logger.warning("X-PAYMENT HMAC verification failed")
        return None

    if header_max_price != max_price:
        logger.warning("X-PAYMENT max_price mismatch: %s != %s", header_max_price, max_price)
        return None

    logger.info("HMAC payment verified: buyer=%s, max_price=%s", buyer, max_price)
    return {"buyer": buyer, "max_price": max_price, "nonce": nonce, "verified": True}


# ── x402 Mode (EIP-3009 / EIP-712) ──────────────────────────────────────────

# EIP-712 types for TransferWithAuthorization (EIP-3009)
TRANSFER_AUTH_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


def create_x402_payment(
    *,
    private_key: str,
    from_address: str,
    to_address: str,
    value: str,
    asset: str,
    chain_id: int,
    token_name: str | None = None,
    token_version: str | None = None,
) -> str:
    """Create an x402 payment header value (Base64-encoded JSON).

    Signs a TransferWithAuthorization message using EIP-712.
    """
    if token_name is None or token_version is None:
        default_name, default_version = _token_domain()
        token_name = default_name if token_name is None else token_name
        token_version = default_version if token_version is None else token_version

    nonce = os.urandom(32)
    nonce_hex = "0x" + nonce.hex()
    now = int(time.time())
    valid_before = now + 300  # 5 minute window

    domain_data = {
        "name": token_name,
        "version": token_version,
        "chainId": chain_id,
        "verifyingContract": asset,
    }

    message_data = {
        "from": from_address,
        "to": to_address,
        "value": int(value),
        "validAfter": 0,
        "validBefore": valid_before,
        "nonce": nonce,
    }

    # Sign using eth_account's EIP-712 support
    signable = encode_typed_data(
        domain_data=domain_data,
        message_types={"TransferWithAuthorization": TRANSFER_AUTH_TYPES["TransferWithAuthorization"]},
        message_data=message_data,
    )
    signed = Account.sign_message(signable, private_key=private_key)

    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": f"eip155:{chain_id}",
        "payload": {
            "signature": signed.signature.hex() if isinstance(signed.signature, bytes) else hex(signed.signature),
            "authorization": {
                "from": from_address,
                "to": to_address,
                "value": value,
                "validAfter": "0",
                "validBefore": str(valid_before),
                "nonce": nonce_hex,
            },
        },
    }

    return base64.b64encode(json.dumps(payload).encode()).decode()


def _verify_x402(request: Request, *, max_price: str, chain_id: int, asset: str) -> dict[str, Any] | None:
    """Verify x402 EIP-3009 payment authorization from X-PAYMENT header."""
    payment_header = request.headers.get("X-PAYMENT")
    if not payment_header:
        return None

    # Decode Base64
    try:
        decoded = base64.b64decode(payment_header)
        payment = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        # Fallback: try raw JSON (for backward compatibility)
        try:
            payment = json.loads(payment_header)
        except json.JSONDecodeError:
            logger.warning("Invalid X-PAYMENT header: not Base64 JSON or raw JSON")
            return None

    # Extract fields
    payload = payment.get("payload", {})
    authorization = payload.get("authorization", {})
    signature_hex = payload.get("signature", "")

    from_addr = authorization.get("from", "")
    to_addr = authorization.get("to", "")
    value = authorization.get("value", "")
    valid_after = int(authorization.get("validAfter", "0"))
    valid_before = int(authorization.get("validBefore", "0"))
    nonce_hex = authorization.get("nonce", "")

    if not all([from_addr, to_addr, value, signature_hex, nonce_hex]):
        logger.warning("x402 payment missing required authorization fields")
        return None

    # Check value >= max_price
    if int(value) < int(max_price):
        logger.warning("x402 payment value %s < max_price %s", value, max_price)
        return None

    # Check time window
    now = int(time.time())
    if now < valid_after:
        logger.warning("x402 payment not yet valid (validAfter=%d, now=%d)", valid_after, now)
        return None
    if valid_before > 0 and now > valid_before:
        logger.warning("x402 payment expired (validBefore=%d, now=%d)", valid_before, now)
        return None

    # Replay protection
    if nonce_hex in _used_nonces:
        logger.warning("x402 nonce already used: %s", nonce_hex)
        return None

    # Recover signer from EIP-712 signature
    try:
        nonce_bytes = bytes.fromhex(nonce_hex.removeprefix("0x"))
        token_name, token_version = _token_domain()

        domain_data = {
            "name": token_name,
            "version": token_version,
            "chainId": chain_id,
            "verifyingContract": asset,
        }

        message_data = {
            "from": from_addr,
            "to": to_addr,
            "value": int(value),
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_bytes,
        }

        signable = encode_typed_data(
            domain_data=domain_data,
            message_types={"TransferWithAuthorization": TRANSFER_AUTH_TYPES["TransferWithAuthorization"]},
            message_data=message_data,
        )

        sig_bytes = bytes.fromhex(signature_hex.removeprefix("0x"))
        recovered = Account.recover_message(signable, signature=sig_bytes)

        if recovered.lower() != from_addr.lower():
            logger.warning(
                "x402 signature mismatch: recovered=%s, from=%s",
                recovered, from_addr,
            )
            return None

    except Exception as exc:
        logger.warning("x402 signature verification failed: %s", exc)
        return None

    # Mark nonce as used
    _used_nonces.add(nonce_hex)

    logger.info("x402 payment verified: buyer=%s, value=%s, nonce=%s", from_addr, value, nonce_hex)
    return {
        "buyer": from_addr,
        "max_price": max_price,
        "nonce": nonce_hex,
        "verified": True,
    }


# ── Public API ───────────────────────────────────────────────────────────────


def verify_payment_header(
    request: Request,
    *,
    max_price: str,
    chain_id: int = 0,
    asset: str = "",
    secret: str = PAYMENT_SECRET,
) -> dict[str, Any] | None:
    """Verify the X-PAYMENT header on a request.

    Dispatches to HMAC or x402 mode based on PAYMENT_MODE env var.
    """
    mode = os.getenv("PAYMENT_MODE", PAYMENT_MODE)

    if mode == "x402":
        return _verify_x402(request, max_price=max_price, chain_id=chain_id, asset=asset)
    else:
        return _verify_hmac(request, max_price=max_price)


def clear_nonce_cache() -> None:
    """Clear the nonce cache (for testing)."""
    _used_nonces.clear()
