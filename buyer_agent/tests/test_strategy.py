"""Tests for buyer seller-selection strategy."""

from __future__ import annotations

from buyer_agent.strategy import (
    ReceiptRecord,
    SellerCandidate,
    StrategyConfig,
    pick_best_seller,
    rank_sellers,
    summarize_receipts,
)


def test_summarize_receipts_computes_history_metrics():
    history = [
        ReceiptRecord("seller-a", 1_000, True, True, 100_000, 100_000),
        ReceiptRecord("seller-a", 2_500, True, True, 80_000, 100_000, disputed=True),
        ReceiptRecord("seller-b", 6_000, False, False, 0, 100_000),
    ]

    stats = summarize_receipts("seller-a", history)

    assert stats.total_calls == 2
    assert stats.success_rate == 1.0
    assert stats.validation_pass_rate == 1.0
    assert stats.dispute_rate == 0.5
    assert stats.avg_latency_ms == 1_750
    assert stats.avg_payout_ratio == 0.9


def test_rank_sellers_prefers_fast_consistent_history():
    candidates = [
        SellerCandidate("seller-fast", "http://seller-fast"),
        SellerCandidate("seller-slow", "http://seller-slow"),
    ]
    history = [
        ReceiptRecord("seller-fast", 900, True, True, 100_000, 100_000),
        ReceiptRecord("seller-fast", 1_400, True, True, 100_000, 100_000),
        ReceiptRecord("seller-slow", 5_500, True, True, 60_000, 100_000),
        ReceiptRecord("seller-slow", 6_000, True, True, 60_000, 100_000),
    ]

    ranked = rank_sellers(candidates, history)

    assert [item.candidate.seller_id for item in ranked] == ["seller-fast", "seller-slow"]
    assert ranked[0].score > ranked[1].score
    assert ranked[0].blacklisted is False


def test_rank_sellers_blacklists_low_quality_history():
    candidate = SellerCandidate("seller-risky", "http://seller-risky")
    history = [
        ReceiptRecord("seller-risky", 8_000, False, False, 0, 100_000),
        ReceiptRecord("seller-risky", 7_500, False, False, 0, 100_000),
        ReceiptRecord("seller-risky", 9_000, False, False, 0, 100_000, disputed=True),
    ]

    ranked = rank_sellers([candidate], history)

    assert len(ranked) == 1
    assert ranked[0].blacklisted is True
    assert "validation_pass_rate_below_threshold" in ranked[0].reasons
    assert "score_below_threshold" in ranked[0].reasons


def test_pick_best_seller_skips_blacklisted_candidates():
    candidates = [
        SellerCandidate("seller-risky", "http://seller-risky"),
        SellerCandidate("seller-safe", "http://seller-safe"),
    ]
    history = [
        ReceiptRecord("seller-risky", 8_000, False, False, 0, 100_000),
        ReceiptRecord("seller-risky", 8_500, False, False, 0, 100_000),
        ReceiptRecord("seller-risky", 9_000, False, False, 0, 100_000),
        ReceiptRecord("seller-safe", 2_000, True, True, 80_000, 100_000),
        ReceiptRecord("seller-safe", 2_200, True, True, 100_000, 100_000),
    ]

    best = pick_best_seller(candidates, history)

    assert best is not None
    assert best.candidate.seller_id == "seller-safe"
    assert best.blacklisted is False


def test_pick_best_seller_uses_cold_start_score_for_new_candidate():
    config = StrategyConfig(cold_start_score=61.0)
    candidate = SellerCandidate("seller-new", "http://seller-new")

    best = pick_best_seller([candidate], history=[], config=config)

    assert best is not None
    assert best.score == 61.0
    assert best.reasons == ("cold_start",)
