"""Tests for autonomous dispute policy."""

from __future__ import annotations

from buyer_agent.dispute_policy import DisputePolicyConfig, assess_dispute


MANDATE = {
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
    "dispute": {"window_seconds": 600, "bond_amount": "50000"},
}


def test_buyer_disputes_when_seller_is_overpaid():
    assessment = assess_dispute(
        mandate=MANDATE,
        observed_payout=100000,
        observed_refund=0,
        latency_ms=6_500,
        validation_passed=True,
    )

    assert assessment.should_dispute is True
    assert assessment.expected_payout == 60_000
    assert assessment.expected_gain == 40_000
    assert "buyer_overpaid_seller" in assessment.reasons


def test_buyer_skips_dispute_when_gain_is_too_small_for_bond():
    assessment = assess_dispute(
        mandate=MANDATE,
        observed_payout=90_000,
        observed_refund=20_000,
        latency_ms=4_500,
        validation_passed=True,
        config=DisputePolicyConfig(min_expected_gain=5_000, min_gain_to_bond_ratio=0.5),
    )

    assert assessment.should_dispute is False
    assert assessment.expected_payout == 80_000
    assert assessment.expected_gain == 10_000
    assert "gain_to_bond_ratio_below_threshold" in assessment.reasons


def test_seller_role_disputes_underpayment():
    assessment = assess_dispute(
        mandate=MANDATE,
        observed_payout=60_000,
        observed_refund=40_000,
        latency_ms=1_000,
        validation_passed=True,
        config=DisputePolicyConfig(role="seller"),
    )

    assert assessment.should_dispute is True
    assert assessment.expected_payout == 100_000
    assert assessment.expected_gain == 40_000
    assert "seller_underpaid" in assessment.reasons


def test_refund_mismatch_forces_dispute():
    assessment = assess_dispute(
        mandate=MANDATE,
        observed_payout=80_000,
        observed_refund=30_000,
        latency_ms=4_500,
        validation_passed=True,
    )

    assert assessment.should_dispute is True
    assert assessment.expected_refund == 20_000
    assert "refund_mismatch" in assessment.reasons
