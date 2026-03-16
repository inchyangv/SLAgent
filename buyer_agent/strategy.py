"""Seller selection strategy for the autonomous buyer loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class SellerCandidate:
    """A discoverable seller endpoint the buyer can evaluate."""

    seller_id: str
    seller_url: str
    seller_address: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReceiptRecord:
    """Minimal historical receipt facts used for strategy updates."""

    seller_id: str
    latency_ms: int | None
    validation_passed: bool
    success: bool
    payout: int
    max_price: int
    disputed: bool = False

    @property
    def payout_ratio(self) -> float:
        if self.max_price <= 0:
            return 0.0
        return max(0.0, min(1.0, self.payout / self.max_price))


@dataclass(frozen=True)
class SellerStats:
    """Aggregated historical stats for one seller."""

    seller_id: str
    total_calls: int
    success_rate: float
    validation_pass_rate: float
    dispute_rate: float
    avg_latency_ms: float | None
    avg_payout_ratio: float

    @classmethod
    def empty(cls, seller_id: str) -> SellerStats:
        return cls(
            seller_id=seller_id,
            total_calls=0,
            success_rate=0.0,
            validation_pass_rate=0.0,
            dispute_rate=0.0,
            avg_latency_ms=None,
            avg_payout_ratio=0.0,
        )


@dataclass(frozen=True)
class StrategyConfig:
    """Tunable weights and guardrails for seller ranking."""

    target_latency_ms: int = 2_000
    degraded_latency_ms: int = 5_000
    min_samples_for_blacklist: int = 3
    blacklist_score_threshold: float = 45.0
    min_validation_pass_rate: float = 0.5
    min_success_rate: float = 0.5
    cold_start_score: float = 55.0


@dataclass(frozen=True)
class SellerEvaluation:
    """Final strategy decision input for one seller candidate."""

    candidate: SellerCandidate
    stats: SellerStats
    score: float
    blacklisted: bool
    reasons: tuple[str, ...] = ()


def summarize_receipts(
    seller_id: str,
    history: Sequence[ReceiptRecord],
) -> SellerStats:
    """Aggregate historical receipt metrics for one seller."""
    relevant = [record for record in history if record.seller_id == seller_id]
    if not relevant:
        return SellerStats.empty(seller_id)

    latencies = [record.latency_ms for record in relevant if record.latency_ms is not None]
    return SellerStats(
        seller_id=seller_id,
        total_calls=len(relevant),
        success_rate=sum(1 for record in relevant if record.success) / len(relevant),
        validation_pass_rate=sum(1 for record in relevant if record.validation_passed) / len(relevant),
        dispute_rate=sum(1 for record in relevant if record.disputed) / len(relevant),
        avg_latency_ms=mean(latencies) if latencies else None,
        avg_payout_ratio=mean(record.payout_ratio for record in relevant),
    )


def rank_sellers(
    candidates: Sequence[SellerCandidate],
    history: Sequence[ReceiptRecord],
    config: StrategyConfig | None = None,
) -> list[SellerEvaluation]:
    """Score every seller and return them in descending preference order."""
    resolved_config = config or StrategyConfig()
    evaluations = [
        evaluate_seller(candidate, history=history, config=resolved_config)
        for candidate in candidates
    ]
    return sorted(
        evaluations,
        key=lambda item: (item.blacklisted, -item.score, item.candidate.seller_id),
    )


def pick_best_seller(
    candidates: Sequence[SellerCandidate],
    history: Sequence[ReceiptRecord],
    config: StrategyConfig | None = None,
) -> SellerEvaluation | None:
    """Return the highest-ranked non-blacklisted seller, if any."""
    for evaluation in rank_sellers(candidates, history, config=config):
        if not evaluation.blacklisted:
            return evaluation
    return None


def evaluate_seller(
    candidate: SellerCandidate,
    *,
    history: Sequence[ReceiptRecord],
    config: StrategyConfig | None = None,
) -> SellerEvaluation:
    """Compute the seller score and blacklist decision."""
    resolved_config = config or StrategyConfig()
    stats = summarize_receipts(candidate.seller_id, history)

    if stats.total_calls == 0:
        return SellerEvaluation(
            candidate=candidate,
            stats=stats,
            score=resolved_config.cold_start_score,
            blacklisted=False,
            reasons=("cold_start",),
        )

    latency_score = _latency_score(stats.avg_latency_ms, resolved_config)
    score = round(
        100.0
        * (
            (stats.validation_pass_rate * 0.40)
            + (stats.success_rate * 0.20)
            + (latency_score * 0.25)
            + (stats.avg_payout_ratio * 0.15)
        )
        - (stats.dispute_rate * 15.0),
        2,
    )

    reasons: list[str] = []
    if stats.total_calls >= resolved_config.min_samples_for_blacklist:
        if stats.validation_pass_rate < resolved_config.min_validation_pass_rate:
            reasons.append("validation_pass_rate_below_threshold")
        if stats.success_rate < resolved_config.min_success_rate:
            reasons.append("success_rate_below_threshold")
        if score < resolved_config.blacklist_score_threshold:
            reasons.append("score_below_threshold")

    return SellerEvaluation(
        candidate=candidate,
        stats=stats,
        score=score,
        blacklisted=bool(reasons),
        reasons=tuple(reasons),
    )


def _latency_score(avg_latency_ms: float | None, config: StrategyConfig) -> float:
    """Normalize observed latency into a 0..1 score."""
    if avg_latency_ms is None:
        return 0.5
    if avg_latency_ms <= config.target_latency_ms:
        return 1.0
    if avg_latency_ms >= config.degraded_latency_ms:
        return max(0.1, config.degraded_latency_ms / avg_latency_ms)

    span = max(1, config.degraded_latency_ms - config.target_latency_ms)
    overshoot = avg_latency_ms - config.target_latency_ms
    return max(0.4, 1.0 - (overshoot / span))

