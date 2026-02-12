"""Pydantic models for gateway requests/responses and receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CallRequest(BaseModel):
    """Incoming call request body."""
    payload: dict[str, Any]
    mandate_id: str | None = None


class ValidationResult(BaseModel):
    type: str
    schema_id: str | None = None
    passed: bool = False
    details: Any = None


class Metrics(BaseModel):
    ttft_ms: int | None = None
    latency_ms: int = 0


class PricingResult(BaseModel):
    max_price: str
    computed_payout: str
    computed_refund: str
    rule_applied: str


class Receipt(BaseModel):
    version: str = "1.0"
    mandate_id: str = ""
    request_id: str = ""
    buyer: str = ""
    seller: str = ""
    gateway: str = ""
    timestamps: dict[str, str] = {}
    metrics: Metrics = Metrics()
    outcome: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    pricing: PricingResult | None = None
    hashes: dict[str, str] = {}
    signatures: dict[str, str] = {}


class CallResponse(BaseModel):
    """Response returned to caller after processing."""
    request_id: str
    seller_response: Any
    metrics: Metrics
    validation_passed: bool
    payout: str = "0"
    refund: str = "0"
    receipt_hash: str = ""
    tx_hash: str | None = None
