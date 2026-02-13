"""Pricing engine: compute payout from mandate + metrics + validation.

Rules:
- All amounts are integers (smallest token unit).
- Rounding direction: always round down (favor buyer/protocol safety).
- payout <= max_price is invariant.
- If outcome is error OR validation fails → payout = 0 (full refund).
- Otherwise, apply bonus rules (latency tiers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PricingDecision:
    max_price: int
    payout: int
    refund: int
    rule_applied: str
    breach_reasons: list[str]


def compute_payout(
    *,
    mandate: dict[str, Any],
    latency_ms: int,
    success: bool,
    validation_pass: bool,
) -> PricingDecision:
    """Compute payout based on mandate rules, measured latency, and validation outcome.

    Args:
        mandate: SLA mandate dict containing max_price, base_pay, bonus_rules
        latency_ms: Measured end-to-end latency in milliseconds
        success: Whether the seller call succeeded
        validation_pass: Whether validators passed

    Returns:
        PricingDecision with payout, refund, applied rule, and breach reasons
    """
    max_price = int(mandate["max_price"])
    breaches: list[str] = []

    # Fail-closed: error or validation failure → zero payout
    if not success:
        breaches.append("BREACH_UPSTREAM_ERROR")
        return PricingDecision(
            max_price=max_price,
            payout=0,
            refund=max_price,
            rule_applied="error",
            breach_reasons=breaches,
        )

    if not validation_pass:
        breaches.append("BREACH_SCHEMA_FAIL")
        return PricingDecision(
            max_price=max_price,
            payout=0,
            refund=max_price,
            rule_applied="validation_failed",
            breach_reasons=breaches,
        )

    # Apply bonus rules
    bonus_rules = mandate.get("bonus_rules", {})
    rule_type = bonus_rules.get("type", "")

    if rule_type == "latency_tiers":
        return _apply_latency_tiers(max_price, bonus_rules, latency_ms)

    # Fallback: base_pay only
    base_pay = int(mandate.get("base_pay", "0"))
    payout = min(base_pay, max_price)
    if payout < max_price:
        breaches.append("BREACH_LATENCY_TIER_DOWN")
    return PricingDecision(
        max_price=max_price,
        payout=payout,
        refund=max_price - payout,
        rule_applied="base_pay_only",
        breach_reasons=breaches,
    )


def _apply_latency_tiers(
    max_price: int,
    bonus_rules: dict[str, Any],
    latency_ms: int,
) -> PricingDecision:
    """Apply latency tier bonus rules.

    Tiers must be sorted by lte_ms ascending.
    Picks the first tier where latency_ms <= lte_ms.
    """
    tiers = bonus_rules.get("tiers", [])

    # Sort tiers by lte_ms to ensure deterministic evaluation
    sorted_tiers = sorted(tiers, key=lambda t: t["lte_ms"])

    # Determine best possible tier (first tier = best payout)
    best_payout = int(sorted_tiers[0]["payout"]) if sorted_tiers else max_price

    for tier in sorted_tiers:
        if latency_ms <= tier["lte_ms"]:
            payout = int(tier["payout"])
            # Enforce invariant: payout <= max_price
            payout = min(payout, max_price)
            breaches: list[str] = []
            if payout < best_payout:
                breaches.append("BREACH_LATENCY_TIER_DOWN")
            return PricingDecision(
                max_price=max_price,
                payout=payout,
                refund=max_price - payout,
                rule_applied=f"latency_tier_lte_{tier['lte_ms']}",
                breach_reasons=breaches,
            )

    # No tier matched (shouldn't happen if last tier is very large)
    # Fallback to zero bonus
    return PricingDecision(
        max_price=max_price,
        payout=0,
        refund=max_price,
        rule_applied="no_tier_matched",
        breach_reasons=["BREACH_LATENCY_TIER_DOWN"],
    )
