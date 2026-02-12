"""Tests for pricing engine — matches PROJECT.md example tiers."""

from gateway.app.pricing import compute_payout

# PROJECT.md example mandate
SAMPLE_MANDATE = {
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
}


# --- Success + validation pass ---

def test_fast_full_payout():
    """latency <= 2000ms → payout = 100000 (full)"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=1500, success=True, validation_pass=True)
    assert d.payout == 100_000
    assert d.refund == 0
    assert d.rule_applied == "latency_tier_lte_2000"


def test_exact_boundary_2000ms():
    """latency == 2000ms → payout = 100000"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=2000, success=True, validation_pass=True)
    assert d.payout == 100_000


def test_mid_tier():
    """2000 < latency <= 5000ms → payout = 80000"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=3500, success=True, validation_pass=True)
    assert d.payout == 80_000
    assert d.refund == 20_000
    assert d.rule_applied == "latency_tier_lte_5000"


def test_slow_base_pay():
    """latency > 5000ms → payout = 60000 (base_pay)"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=7000, success=True, validation_pass=True)
    assert d.payout == 60_000
    assert d.refund == 40_000
    assert d.rule_applied == "latency_tier_lte_999999999"


# --- Error → zero payout ---

def test_error_zero_payout():
    """success=False → payout = 0, full refund"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=1000, success=False, validation_pass=True)
    assert d.payout == 0
    assert d.refund == 100_000
    assert d.rule_applied == "error"


# --- Validation fail → zero payout ---

def test_validation_fail_zero_payout():
    """validation_pass=False → payout = 0, full refund"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=1000, success=True, validation_pass=False)
    assert d.payout == 0
    assert d.refund == 100_000
    assert d.rule_applied == "validation_failed"


# --- Invariants ---

def test_payout_never_exceeds_max():
    """payout <= max_price always"""
    for lat in [100, 1500, 2001, 5001, 10000]:
        d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=lat, success=True, validation_pass=True)
        assert d.payout <= d.max_price
        assert d.payout + d.refund == d.max_price


def test_refund_is_exact_difference():
    """refund = max_price - payout (exact subtraction)"""
    d = compute_payout(mandate=SAMPLE_MANDATE, latency_ms=3000, success=True, validation_pass=True)
    assert d.refund == d.max_price - d.payout


# --- Edge: no bonus rules → base_pay only ---

def test_no_bonus_rules_fallback():
    mandate = {"max_price": "100000", "base_pay": "60000"}
    d = compute_payout(mandate=mandate, latency_ms=1000, success=True, validation_pass=True)
    assert d.payout == 60_000
    assert d.rule_applied == "base_pay_only"
