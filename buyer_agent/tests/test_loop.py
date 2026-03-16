"""Tests for the autonomous buyer loop."""

from __future__ import annotations

import asyncio

from buyer_agent.client import BuyerResult, NegotiationResult
from buyer_agent.loop import AutonomousBuyerLoop, AutonomousSellerTarget

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
    "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
    "dispute": {"window_seconds": 600, "bond_amount": "50000"},
}


def _make_result(*, request_id: str, payout: int, refund: int, latency_ms: int) -> BuyerResult:
    return BuyerResult(
        request_id=request_id,
        mode="fast",
        success=True,
        metrics={"latency_ms": latency_ms, "ttft_ms": 100},
        validation_passed=True,
        payout=payout,
        refund=refund,
        max_price=100000,
        receipt_hash=f"0x{request_id}",
        tx_hash=f"0xtx_{request_id}",
        seller_response={"invoice_id": request_id},
        invariant_checks=[],
    )


def test_autonomous_loop_explores_then_prefers_best(monkeypatch):
    state = {
        "calls": {
            "http://seller-a": [
                _make_result(
                    request_id="a1",
                    payout=60_000,
                    refund=40_000,
                    latency_ms=6_000,
                )
            ],
            "http://seller-b": [
                _make_result(request_id="b1", payout=100_000, refund=0, latency_ms=900),
                _make_result(request_id="b2", payout=100_000, refund=0, latency_ms=1_000),
            ],
        }
    }

    class FakeBuyerAgent:
        def __init__(
            self,
            gateway_url,
            seller_url,
            buyer_address,
            buyer_private_key=None,
            timeout=30.0,
        ):
            self.seller_url = seller_url
            self.max_price = "100000"

        async def discover_seller(self):
            seller_id = "seller-a" if self.seller_url.endswith("seller-a") else "seller-b"
            return {
                "seller_address": seller_id,
                "supported_schemas": ["invoice_v1"],
                "llm_model": "fake",
            }

        async def negotiate_mandate(self, seller_capabilities=None, scenario_tag=""):
            seller_id = seller_capabilities["seller_address"]
            return NegotiationResult(
                seller_capabilities=seller_capabilities or {},
                mandate={**MANDATE, "seller": seller_id},
                mandate_id=f"0x{seller_id}",
                seller_accepted=True,
                summary="ok",
            )

        async def call(self, mode="fast", delay_ms=0, scenario_tag="", seller_url=None):
            chosen_url = seller_url or self.seller_url
            return state["calls"][chosen_url].pop(0)

    monkeypatch.setattr("buyer_agent.loop.BuyerAgent", FakeBuyerAgent)

    loop = AutonomousBuyerLoop(
        gateway_url="http://gateway",
        seller_targets=[
            AutonomousSellerTarget("http://seller-a"),
            AutonomousSellerTarget("http://seller-b"),
        ],
        buyer_address="0xbuyer",
        budget_tokens=500000,
        max_rounds=3,
    )

    result = asyncio.run(loop.run())

    assert [round_result.seller_id for round_result in result.rounds] == [
        "seller-a",
        "seller-b",
        "seller-b",
    ]
    assert result.stop_reason == "max_rounds_reached"


def test_autonomous_loop_opens_dispute_when_policy_triggers(monkeypatch):
    class FakeBuyerAgent:
        def __init__(
            self,
            gateway_url,
            seller_url,
            buyer_address,
            buyer_private_key=None,
            timeout=30.0,
        ):
            self.seller_url = seller_url
            self.max_price = "100000"

        async def discover_seller(self):
            return {
                "seller_address": "seller-risky",
                "supported_schemas": ["invoice_v1"],
                "llm_model": "fake",
            }

        async def negotiate_mandate(self, seller_capabilities=None, scenario_tag=""):
            return NegotiationResult(
                seller_capabilities=seller_capabilities or {},
                mandate={**MANDATE, "seller": "seller-risky"},
                mandate_id="0xseller-risky",
                seller_accepted=True,
                summary="ok",
            )

        async def call(self, mode="fast", delay_ms=0, scenario_tag="", seller_url=None):
            return _make_result(request_id="req-risky", payout=100_000, refund=0, latency_ms=7_000)

    dispute_requests: list[str] = []

    async def fake_open_dispute(self, request_id: str) -> bool:
        dispute_requests.append(request_id)
        return True

    monkeypatch.setattr("buyer_agent.loop.BuyerAgent", FakeBuyerAgent)
    monkeypatch.setattr(AutonomousBuyerLoop, "_open_dispute", fake_open_dispute)

    loop = AutonomousBuyerLoop(
        gateway_url="http://gateway",
        seller_targets=[AutonomousSellerTarget("http://seller-risky")],
        buyer_address="0xbuyer",
        budget_tokens=200000,
        max_rounds=1,
    )

    result = asyncio.run(loop.run())

    assert dispute_requests == ["req-risky"]
    assert result.disputes_opened == 1
    assert result.rounds[0].disputed is True


def test_autonomous_loop_stops_when_budget_cannot_cover_next_round(monkeypatch):
    class FakeBuyerAgent:
        def __init__(
            self,
            gateway_url,
            seller_url,
            buyer_address,
            buyer_private_key=None,
            timeout=30.0,
        ):
            self.seller_url = seller_url
            self.max_price = "100000"

        async def discover_seller(self):
            return {
                "seller_address": "seller-one",
                "supported_schemas": ["invoice_v1"],
                "llm_model": "fake",
            }

        async def negotiate_mandate(self, seller_capabilities=None, scenario_tag=""):
            return NegotiationResult(
                seller_capabilities=seller_capabilities or {},
                mandate={**MANDATE, "seller": "seller-one"},
                mandate_id="0xseller-one",
                seller_accepted=True,
                summary="ok",
            )

        async def call(self, mode="fast", delay_ms=0, scenario_tag="", seller_url=None):
            return _make_result(request_id="req-one", payout=100_000, refund=0, latency_ms=1_000)

    monkeypatch.setattr("buyer_agent.loop.BuyerAgent", FakeBuyerAgent)

    loop = AutonomousBuyerLoop(
        gateway_url="http://gateway",
        seller_targets=[AutonomousSellerTarget("http://seller-one")],
        buyer_address="0xbuyer",
        budget_tokens=50_000,
        max_rounds=3,
    )

    result = asyncio.run(loop.run())

    assert result.rounds == []
    assert result.stop_reason == "budget_exhausted"


def test_autonomous_loop_marks_buyer_error_results_as_errors(monkeypatch):
    class FakeBuyerAgent:
        def __init__(
            self,
            gateway_url,
            seller_url,
            buyer_address,
            buyer_private_key=None,
            timeout=30.0,
        ):
            self.seller_url = seller_url
            self.max_price = "100000"

        async def discover_seller(self):
            return {
                "seller_address": "seller-one",
                "supported_schemas": ["invoice_v1"],
                "llm_model": "fake",
            }

        async def negotiate_mandate(self, seller_capabilities=None, scenario_tag=""):
            return NegotiationResult(
                seller_capabilities=seller_capabilities or {},
                mandate={**MANDATE, "seller": "seller-one"},
                mandate_id="0xseller-one",
                seller_accepted=True,
                summary="ok",
            )

        async def call(self, mode="fast", delay_ms=0, scenario_tag="", seller_url=None):
            return BuyerResult(
                request_id="",
                mode=mode,
                success=False,
                metrics={},
                validation_passed=False,
                payout=0,
                refund=0,
                max_price=100000,
                receipt_hash="",
                tx_hash=None,
                seller_response={},
                invariant_checks=[],
                error="Buyer deposit failed",
            )

    monkeypatch.setattr("buyer_agent.loop.BuyerAgent", FakeBuyerAgent)

    loop = AutonomousBuyerLoop(
        gateway_url="http://gateway",
        seller_targets=[AutonomousSellerTarget("http://seller-one")],
        buyer_address="0xbuyer",
        budget_tokens=200000,
        max_rounds=1,
    )

    result = asyncio.run(loop.run())

    assert result.rounds[0].status == "error"
    assert result.rounds[0].error == "Buyer deposit failed"
