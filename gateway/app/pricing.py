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
        PricingDecision with payout, refund, and applied rule
    """
    max_price = int(mandate["max_price"])

    # Fail-closed: error or validation failure → zero payout
    if not success or not validation_pass:
        rule = "error" if not success else "validation_failed"
        return PricingDecision(
            max_price=max_price,
            payout=0,
            refund=max_price,
            rule_applied=rule,
        )

    # Apply bonus rules
    bonus_rules = mandate.get("bonus_rules", {})
    rule_type = bonus_rules.get("type", "")

    if rule_type == "latency_tiers":
        return _apply_latency_tiers(max_price, bonus_rules, latency_ms)

    # Fallback: base_pay only
    base_pay = int(mandate.get("base_pay", "0"))
    payout = min(base_pay, max_price)
    return PricingDecision(
        max_price=max_price,
        payout=payout,
        refund=max_price - payout,
        rule_applied="base_pay_only",
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

    for tier in sorted_tiers:
        if latency_ms <= tier["lte_ms"]:
            payout = int(tier["payout"])
            # Enforce invariant: payout <= max_price
            payout = min(payout, max_price)
            return PricingDecision(
                max_price=max_price,
                payout=payout,
                refund=max_price - payout,
                rule_applied=f"latency_tier_lte_{tier['lte_ms']}",
            )

    # No tier matched (shouldn't happen if last tier is very large)
    # Fallback to zero bonus
    return PricingDecision(
        max_price=max_price,
        payout=0,
        refund=max_price,
        rule_applied="no_tier_matched",
    )
