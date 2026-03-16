"""Autonomous buyer loop with seller discovery, ranking, and disputes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import httpx

from buyer_agent.client import BuyerAgent, BuyerResult, InvariantViolation
from buyer_agent.dispute_policy import DisputeAssessment, DisputePolicyConfig, assess_dispute
from buyer_agent.strategy import (
    ReceiptRecord,
    SellerCandidate,
    SellerEvaluation,
    StrategyConfig,
    pick_best_seller,
    rank_sellers,
)


@dataclass(frozen=True)
class AutonomousSellerTarget:
    """Configured seller endpoint for the autonomous loop."""

    seller_url: str
    mode: str = "fast"
    delay_ms: int = 0
    label: str = ""


@dataclass(frozen=True)
class DiscoveredSeller:
    """Seller target plus fetched capabilities and strategy identity."""

    target: AutonomousSellerTarget
    candidate: SellerCandidate


@dataclass(frozen=True)
class AutonomousRound:
    """One completed or attempted autonomous round."""

    round_number: int
    seller_id: str
    seller_url: str
    seller_score: float
    mode: str
    delay_ms: int
    request_id: str
    payout: int
    refund: int
    budget_before: int
    budget_after: int
    validation_passed: bool
    latency_ms: int | None
    disputed: bool
    dispute_reasons: tuple[str, ...]
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutonomousLoopResult:
    """Summary of the autonomous loop execution."""

    rounds: list[AutonomousRound]
    budget_initial: int
    budget_remaining: int
    sellers_seen: tuple[str, ...]
    disputes_opened: int
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": [round_result.to_dict() for round_result in self.rounds],
            "budget_initial": self.budget_initial,
            "budget_remaining": self.budget_remaining,
            "sellers_seen": list(self.sellers_seen),
            "disputes_opened": self.disputes_opened,
            "stop_reason": self.stop_reason,
        }


class AutonomousBuyerLoop:
    """Budget-aware loop that explores sellers, ranks them, and opens disputes."""

    def __init__(
        self,
        *,
        gateway_url: str,
        seller_targets: list[AutonomousSellerTarget],
        buyer_address: str,
        buyer_private_key: str | None = None,
        budget_tokens: int = 1_000_000,
        max_rounds: int = 10,
        strategy_config: StrategyConfig | None = None,
        dispute_config: DisputePolicyConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.seller_targets = seller_targets
        self.buyer_address = buyer_address
        self.buyer_private_key = buyer_private_key
        self.budget_tokens = budget_tokens
        self.max_rounds = max_rounds
        self.strategy_config = strategy_config or StrategyConfig()
        self.dispute_config = dispute_config or DisputePolicyConfig(role="buyer")
        self.timeout = timeout
        self.history: list[ReceiptRecord] = []

    async def discover_available_sellers(self) -> list[DiscoveredSeller]:
        """Fetch capabilities for each configured seller target."""
        discovered: list[DiscoveredSeller] = []
        for target in self.seller_targets:
            agent = BuyerAgent(
                gateway_url=self.gateway_url,
                seller_url=target.seller_url,
                buyer_address=self.buyer_address,
                buyer_private_key=self.buyer_private_key,
                timeout=self.timeout,
            )
            try:
                capabilities = await agent.discover_seller()
            except Exception:
                continue
            seller_id = str(
                capabilities.get("seller_address")
                or target.label
                or target.seller_url
            ).strip()
            discovered.append(
                DiscoveredSeller(
                    target=target,
                    candidate=SellerCandidate(
                        seller_id=seller_id,
                        seller_url=target.seller_url,
                        seller_address=str(capabilities.get("seller_address", "")),
                        capabilities=capabilities,
                    ),
                )
            )
        return discovered

    async def run(self) -> AutonomousLoopResult:
        """Run the autonomous loop until budget or round limits are reached."""
        rounds: list[AutonomousRound] = []
        budget_remaining = self.budget_tokens
        disputes_opened = 0
        seen_sellers: list[str] = []
        stop_reason = "max_rounds_reached"

        for round_number in range(1, self.max_rounds + 1):
            discovered = await self.discover_available_sellers()
            if not discovered:
                stop_reason = "no_sellers_available"
                break

            selection = self._select_seller(discovered)
            if selection is None:
                stop_reason = "all_sellers_blacklisted"
                break

            chosen_seller, evaluation = selection
            if evaluation.candidate.seller_id not in seen_sellers:
                seen_sellers.append(evaluation.candidate.seller_id)

            agent = BuyerAgent(
                gateway_url=self.gateway_url,
                seller_url=chosen_seller.target.seller_url,
                buyer_address=self.buyer_address,
                buyer_private_key=self.buyer_private_key,
                timeout=self.timeout,
            )

            try:
                negotiation = await agent.negotiate_mandate(
                    seller_capabilities=chosen_seller.candidate.capabilities,
                    scenario_tag="autonomous",
                )
                max_price = int(negotiation.mandate.get("max_price", agent.max_price))
            except Exception as exc:
                self.history.append(
                    ReceiptRecord(
                        seller_id=evaluation.candidate.seller_id,
                        latency_ms=None,
                        validation_passed=False,
                        success=False,
                        payout=0,
                        max_price=int(agent.max_price),
                    )
                )
                rounds.append(
                    AutonomousRound(
                        round_number=round_number,
                        seller_id=evaluation.candidate.seller_id,
                        seller_url=chosen_seller.target.seller_url,
                        seller_score=evaluation.score,
                        mode=chosen_seller.target.mode,
                        delay_ms=chosen_seller.target.delay_ms,
                        request_id="",
                        payout=0,
                        refund=0,
                        budget_before=budget_remaining,
                        budget_after=budget_remaining,
                        validation_passed=False,
                        latency_ms=None,
                        disputed=False,
                        dispute_reasons=(),
                        status="negotiation_failed",
                        error=str(exc),
                    )
                )
                continue

            if budget_remaining < max_price:
                stop_reason = "budget_exhausted"
                break

            budget_before = budget_remaining

            try:
                result = await agent.call(
                    mode=chosen_seller.target.mode,
                    delay_ms=chosen_seller.target.delay_ms,
                    scenario_tag="autonomous",
                    seller_url=chosen_seller.target.seller_url,
                )
                status = "success"
            except InvariantViolation as exc:
                result = exc.result or self._error_result(
                    mode=chosen_seller.target.mode,
                    max_price=max_price,
                    error=str(exc),
                )
                status = "refused"
            except Exception as exc:
                result = self._error_result(
                    mode=chosen_seller.target.mode,
                    max_price=max_price,
                    error=str(exc),
                )
                status = "error"

            dispute_assessment: DisputeAssessment | None = None
            dispute_opened = False
            if result.request_id and result.metrics:
                dispute_assessment = assess_dispute(
                    mandate=negotiation.mandate,
                    observed_payout=result.payout,
                    observed_refund=result.refund,
                    latency_ms=int(result.metrics.get("latency_ms", 0) or 0),
                    validation_passed=result.validation_passed,
                    success=True,
                    config=self.dispute_config,
                )
                if dispute_assessment.should_dispute:
                    dispute_opened = await self._open_dispute(result.request_id)
                    if dispute_opened:
                        disputes_opened += 1

            budget_after = max(0, budget_before - result.payout)
            budget_remaining = budget_after

            self.history.append(
                # Record dispute intent so future rounds can down-rank inconsistent sellers.
                ReceiptRecord(
                    seller_id=evaluation.candidate.seller_id,
                    latency_ms=result.metrics.get("latency_ms"),
                    validation_passed=result.validation_passed,
                    success=status == "success",
                    payout=result.payout,
                    max_price=max_price,
                    disputed=dispute_opened
                    or bool(dispute_assessment and dispute_assessment.should_dispute),
                )
            )

            rounds.append(
                AutonomousRound(
                    round_number=round_number,
                    seller_id=evaluation.candidate.seller_id,
                    seller_url=chosen_seller.target.seller_url,
                    seller_score=evaluation.score,
                    mode=chosen_seller.target.mode,
                    delay_ms=chosen_seller.target.delay_ms,
                    request_id=result.request_id,
                    payout=result.payout,
                    refund=result.refund,
                    budget_before=budget_before,
                    budget_after=budget_after,
                    validation_passed=result.validation_passed,
                    latency_ms=result.metrics.get("latency_ms"),
                    disputed=dispute_opened,
                    dispute_reasons=(
                        dispute_assessment.reasons if dispute_assessment else ()
                    ),
                    status=status,
                    error=result.error,
                )
            )

        return AutonomousLoopResult(
            rounds=rounds,
            budget_initial=self.budget_tokens,
            budget_remaining=budget_remaining,
            sellers_seen=tuple(seen_sellers),
            disputes_opened=disputes_opened,
            stop_reason=stop_reason,
        )

    async def _open_dispute(self, request_id: str) -> bool:
        """Open a dispute through the gateway."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/disputes/open",
                json={"request_id": request_id},
            )
            return response.status_code == 200

    def _select_seller(
        self,
        discovered: list[DiscoveredSeller],
    ) -> tuple[DiscoveredSeller, SellerEvaluation] | None:
        evaluations = rank_sellers(
            [seller.candidate for seller in discovered],
            self.history,
            config=self.strategy_config,
        )
        evaluation_map = {
            evaluation.candidate.seller_id: evaluation
            for evaluation in evaluations
        }

        for seller in discovered:
            evaluation = evaluation_map[seller.candidate.seller_id]
            if evaluation.stats.total_calls == 0 and not evaluation.blacklisted:
                return seller, evaluation

        best = pick_best_seller(
            [seller.candidate for seller in discovered],
            self.history,
            config=self.strategy_config,
        )
        if best is None:
            return None

        for seller in discovered:
            if seller.candidate.seller_id == best.candidate.seller_id:
                return seller, best
        return None

    @staticmethod
    def _error_result(*, mode: str, max_price: int, error: str) -> BuyerResult:
        return BuyerResult(
            request_id="",
            mode=mode,
            success=False,
            metrics={},
            validation_passed=False,
            payout=0,
            refund=max_price,
            max_price=max_price,
            receipt_hash="",
            tx_hash=None,
            seller_response={},
            invariant_checks=[],
            error=error,
        )
