"""Bond-aware dispute policy for autonomous settlement checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from gateway.app.pricing import compute_payout

DisputeRole = Literal["buyer", "seller"]


@dataclass(frozen=True)
class DisputePolicyConfig:
    """Thresholds for deciding whether a dispute is economically rational."""

    role: DisputeRole = "buyer"
    min_expected_gain: int = 10_000
    min_gain_to_bond_ratio: float = 0.25
    always_dispute_on_refund_mismatch: bool = True


@dataclass(frozen=True)
class DisputeAssessment:
    """Outcome of a dispute-policy evaluation."""

    should_dispute: bool
    expected_payout: int
    expected_refund: int
    observed_payout: int
    observed_refund: int
    expected_gain: int
    bond_amount: int
    gain_to_bond_ratio: float | None
    reasons: tuple[str, ...]


def assess_dispute(
    *,
    mandate: dict[str, Any],
    observed_payout: int,
    observed_refund: int,
    latency_ms: int,
    validation_passed: bool,
    success: bool = True,
    config: DisputePolicyConfig | None = None,
) -> DisputeAssessment:
    """Compare observed settlement with deterministic policy expectations."""
    resolved_config = config or DisputePolicyConfig()
    pricing = compute_payout(
        mandate=mandate,
        latency_ms=latency_ms,
        success=success,
        validation_pass=validation_passed,
    )

    expected_payout = pricing.payout
    expected_refund = pricing.refund
    bond_amount = int(mandate.get("dispute", {}).get("bond_amount", "0"))

    if resolved_config.role == "buyer":
        expected_gain = max(0, observed_payout - expected_payout)
        payout_reason = "buyer_overpaid_seller"
    else:
        expected_gain = max(0, expected_payout - observed_payout)
        payout_reason = "seller_underpaid"

    refund_mismatch = observed_refund != expected_refund
    gain_to_bond_ratio = None if bond_amount <= 0 else round(expected_gain / bond_amount, 4)

    reasons: list[str] = []
    should_dispute = False

    if expected_gain > 0:
        reasons.append(payout_reason)
        gain_gate = expected_gain >= resolved_config.min_expected_gain
        ratio_gate = bond_amount <= 0 or (
            gain_to_bond_ratio is not None
            and gain_to_bond_ratio >= resolved_config.min_gain_to_bond_ratio
        )
        should_dispute = gain_gate and ratio_gate
        if not gain_gate:
            reasons.append("expected_gain_below_threshold")
        if not ratio_gate:
            reasons.append("gain_to_bond_ratio_below_threshold")

    if refund_mismatch:
        reasons.append("refund_mismatch")
        if resolved_config.always_dispute_on_refund_mismatch:
            should_dispute = True

    return DisputeAssessment(
        should_dispute=should_dispute,
        expected_payout=expected_payout,
        expected_refund=expected_refund,
        observed_payout=observed_payout,
        observed_refund=observed_refund,
        expected_gain=expected_gain,
        bond_amount=bond_amount,
        gain_to_bond_ratio=gain_to_bond_ratio,
        reasons=tuple(reasons),
    )
