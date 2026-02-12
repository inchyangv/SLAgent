"""Tests for buyer agent — uses mocked gateway responses."""

from __future__ import annotations

import json

import httpx
import pytest

from buyer_agent.client import BuyerAgent, BuyerResult, InvariantViolation


# ── Mock Gateway ─────────────────────────────────────────────────────────────


def _make_mock_handler(payout: int, refund: int, validation_passed: bool = True):
    """Create a mock request handler for httpx.MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        # Health check
        if "/v1/health" in url and request.method == "GET":
            return httpx.Response(200, json={"status": "ok"})

        # Call endpoint
        if "/v1/call" in url and request.method == "POST":
            has_payment = "x-payment" in {k.lower(): v for k, v in request.headers.items()}

            if not has_payment:
                return httpx.Response(
                    402,
                    json={
                        "error": "Payment Required",
                        "accepts": [{"maxAmountRequired": "100000", "nonce": "123"}],
                    },
                )

            return httpx.Response(
                200,
                json={
                    "request_id": "req_test_001",
                    "seller_response": {"invoice_id": "INV-TEST"},
                    "metrics": {"ttft_ms": 100, "latency_ms": 500},
                    "validation_passed": validation_passed,
                    "payout": str(payout),
                    "refund": str(refund),
                    "receipt_hash": "0xabc123def456",
                    "tx_hash": "0xtx_mock",
                },
            )

        return httpx.Response(404, json={"error": "Not found"})

    return handler


# ── Helper ───────────────────────────────────────────────────────────────────


async def _run_mock_flow(
    agent: BuyerAgent,
    mode: str,
    payout: int,
    refund: int,
    validation_passed: bool = True,
) -> BuyerResult:
    """Run a mock 402→paid flow and check invariants."""
    handler = _make_mock_handler(payout, refund, validation_passed)
    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        # Step 1: 402
        resp_402 = await client.post("http://test/v1/call", json={"mode": mode})
        assert resp_402.status_code == 402

        # Step 2: Paid
        headers = agent._make_payment_header()
        resp = await client.post(
            f"http://test/v1/call?mode={mode}",
            json={"mode": mode},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()

    payout_val = int(data["payout"])
    refund_val = int(data["refund"])
    max_price_val = int(agent.max_price)

    checks = agent._check_invariants(
        payout=payout_val,
        refund=refund_val,
        max_price=max_price_val,
        validation_passed=data["validation_passed"],
        mode=mode,
    )

    return BuyerResult(
        request_id=data["request_id"],
        mode=mode,
        success=all(c["passed"] for c in checks),
        metrics=data["metrics"],
        validation_passed=data["validation_passed"],
        payout=payout_val,
        refund=refund_val,
        max_price=max_price_val,
        receipt_hash=data["receipt_hash"],
        tx_hash=data["tx_hash"],
        seller_response=data["seller_response"],
        invariant_checks=checks,
    )


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_mode_full_payout():
    """Fast mode: full payout, all invariants pass."""
    agent = BuyerAgent(gateway_url="http://test")
    result = await _run_mock_flow(agent, "fast", payout=100000, refund=0)
    assert result.success
    assert result.payout == 100000
    assert result.refund == 0
    assert all(c["passed"] for c in result.invariant_checks)


@pytest.mark.asyncio
async def test_partial_payout():
    """Mid-tier payout: invariants should still pass."""
    agent = BuyerAgent(gateway_url="http://test")
    result = await _run_mock_flow(agent, "slow", payout=80000, refund=20000)
    assert result.success
    assert result.payout == 80000
    assert result.refund == 20000
    assert all(c["passed"] for c in result.invariant_checks)


@pytest.mark.asyncio
async def test_zero_payout_invalid():
    """Invalid mode: payout=0, refund=max_price."""
    agent = BuyerAgent(gateway_url="http://test")
    result = await _run_mock_flow(
        agent, "invalid", payout=0, refund=100000, validation_passed=False
    )
    assert result.success
    assert result.payout == 0
    assert result.refund == 100000
    invalid_check = next(c for c in result.invariant_checks if c["name"] == "invalid_zero_payout")
    assert invalid_check["passed"]


def test_invariant_payout_exceeds_max():
    """Invariant violation: payout > max_price."""
    agent = BuyerAgent()
    checks = agent._check_invariants(
        payout=200000,
        refund=-100000,
        max_price=100000,
        validation_passed=True,
        mode="fast",
    )
    payout_check = next(c for c in checks if c["name"] == "payout_le_max_price")
    assert not payout_check["passed"]


def test_invariant_refund_mismatch():
    """Invariant violation: refund != max_price - payout."""
    agent = BuyerAgent()
    checks = agent._check_invariants(
        payout=80000,
        refund=10000,  # should be 20000
        max_price=100000,
        validation_passed=True,
        mode="fast",
    )
    refund_check = next(c for c in checks if c["name"] == "refund_correctness")
    assert not refund_check["passed"]
    total_check = next(c for c in checks if c["name"] == "total_conservation")
    assert not total_check["passed"]


def test_invariant_invalid_nonzero_payout():
    """Invariant violation: invalid mode but payout > 0."""
    agent = BuyerAgent()
    checks = agent._check_invariants(
        payout=50000,
        refund=50000,
        max_price=100000,
        validation_passed=False,
        mode="invalid",
    )
    invalid_check = next(c for c in checks if c["name"] == "invalid_zero_payout")
    assert not invalid_check["passed"]


def test_invariant_all_pass_fast():
    """Fast mode: all invariants pass with correct values."""
    agent = BuyerAgent()
    checks = agent._check_invariants(
        payout=100000,
        refund=0,
        max_price=100000,
        validation_passed=True,
        mode="fast",
    )
    assert all(c["passed"] for c in checks)
    assert len(checks) == 5  # no invalid_zero_payout check for fast mode


def test_invariant_all_pass_invalid():
    """Invalid mode: all invariants pass with zero payout."""
    agent = BuyerAgent()
    checks = agent._check_invariants(
        payout=0,
        refund=100000,
        max_price=100000,
        validation_passed=False,
        mode="invalid",
    )
    assert all(c["passed"] for c in checks)
    assert len(checks) == 6  # includes invalid_zero_payout check


def test_buyer_result_dataclass():
    """BuyerResult can be constructed and accessed."""
    result = BuyerResult(
        request_id="req_001",
        mode="fast",
        success=True,
        metrics={"latency_ms": 100},
        validation_passed=True,
        payout=100000,
        refund=0,
        max_price=100000,
        receipt_hash="0xabc",
        tx_hash="0xtx",
        seller_response={"invoice_id": "INV-001"},
        invariant_checks=[],
    )
    assert result.success
    assert result.payout == 100000
    assert result.error is None
