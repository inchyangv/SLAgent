"""Tests for x402 agentic tool chain — budget, catalog, CDP wallet, multi-step execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from buyer_agent.cdp_wallet import CDPWallet, CDPSignResult
from buyer_agent.tools import (
    BudgetConfig,
    BudgetManager,
    ChainResult,
    StepSpend,
    ToolChainExecutor,
    ToolDef,
    load_tool_catalog,
)


# ── Tool Catalog ─────────────────────────────────────────────────────────────


def test_load_tool_catalog():
    """Tool catalog loads and contains at least 2 tools."""
    tools = load_tool_catalog()
    assert len(tools) >= 2
    for t in tools:
        assert t.tool_id
        assert t.name
        assert int(t.price) > 0
        assert t.schema_id


def test_tool_catalog_has_required_fields():
    """Each tool has all required fields."""
    tools = load_tool_catalog()
    for t in tools:
        assert t.tool_id
        assert t.endpoint
        assert t.price
        assert t.max_latency_ms > 0
        assert t.quality in ("standard", "premium")
        assert t.mode
        assert t.offer_id


# ── Budget Manager ───────────────────────────────────────────────────────────


def test_budget_can_afford():
    """Budget manager correctly checks affordability."""
    bm = BudgetManager(BudgetConfig(budget_usdc=200000, max_step_price=100000))
    ok, reason = bm.can_afford(50000)
    assert ok is True
    assert reason == "OK"


def test_budget_exceeded():
    """Budget manager rejects when price exceeds remaining budget."""
    bm = BudgetManager(BudgetConfig(budget_usdc=30000, max_step_price=100000))
    ok, reason = bm.can_afford(50000)
    assert ok is False
    assert "BUDGET_EXCEEDED" in reason


def test_budget_max_step_exceeded():
    """Budget manager rejects when price exceeds max_step_price."""
    bm = BudgetManager(BudgetConfig(budget_usdc=500000, max_step_price=40000))
    ok, reason = bm.can_afford(50000)
    assert ok is False
    assert "MAX_STEP_PRICE" in reason


def test_budget_record_spend():
    """Budget manager tracks spend correctly."""
    bm = BudgetManager(BudgetConfig(budget_usdc=200000, max_step_price=100000))
    bm.record_spend(price=50000, refund=10000)
    assert bm.total_spent == 40000
    assert bm.total_refunded == 10000
    assert bm.remaining == 160000

    bm.record_spend(price=80000, refund=20000)
    assert bm.total_spent == 100000
    assert bm.total_refunded == 30000
    assert bm.remaining == 100000


def test_budget_summary():
    """Budget summary includes all fields."""
    bm = BudgetManager(BudgetConfig(budget_usdc=200000, max_step_price=100000))
    bm.record_spend(50000, 10000)
    summary = bm.summary()
    assert summary["budget_initial"] == 200000
    assert summary["budget_remaining"] == 160000
    assert summary["total_spent"] == 40000
    assert summary["total_refunded"] == 10000


# ── CDP Wallet ───────────────────────────────────────────────────────────────


TEST_KEY = "0x" + "ab" * 32


def test_cdp_wallet_init():
    """CDP wallet initializes with address and wallet_id."""
    wallet = CDPWallet(private_key=TEST_KEY)
    assert wallet.address
    assert wallet.wallet_id
    assert wallet.mode == "local"


def test_cdp_wallet_status():
    """CDP wallet status includes all audit fields."""
    wallet = CDPWallet(private_key=TEST_KEY)
    status = wallet.status()
    assert "wallet_id" in status
    assert "address" in status
    assert "mode" in status
    assert "custody" in status
    assert status["sign_count"] == 0


def test_cdp_wallet_sign_payment():
    """CDP wallet can sign an x402 payment."""
    wallet = CDPWallet(private_key=TEST_KEY)
    result = wallet.sign_payment(
        to_address="0x2222222222222222222222222222222222222222",
        value="100000",
        asset="0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8",
        chain_id=11155111,
    )
    assert isinstance(result, CDPSignResult)
    assert result.signature  # Base64-encoded x402 payload
    assert result.signer_address == wallet.address
    assert result.wallet_id == wallet.wallet_id
    assert result.custody_mode == "cdp_local"
    assert result.metadata["value"] == "100000"

    # Sign count incremented
    assert wallet.status()["sign_count"] == 1


# ── Tool Chain Executor (mocked gateway) ─────────────────────────────────────


def _make_mock_handler():
    """Create a mock handler that simulates 402 challenge + paid response."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        # Mandate registration
        if "/v1/mandates" in url and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={"mandate_id": body.get("mandate_id", "m_test")})

        # Call endpoint
        if "/v1/call" in url and request.method == "POST":
            has_payment = "x-payment" in {k.lower(): v for k, v in request.headers.items()}

            if not has_payment:
                return httpx.Response(
                    402,
                    json={"error": "Payment Required", "accepts": [{"maxAmountRequired": "100000"}]},
                )

            call_count["n"] += 1
            return httpx.Response(
                200,
                json={
                    "request_id": f"req_tool_{call_count['n']}",
                    "seller_response": {"invoice_id": f"INV-{call_count['n']}"},
                    "metrics": {"ttft_ms": 100, "latency_ms": 500},
                    "validation_passed": True,
                    "payout": "40000",
                    "refund": "10000",
                    "receipt_hash": f"0xreceipt_{call_count['n']}",
                    "tx_hash": f"0xtx_{call_count['n']}",
                },
            )

        return httpx.Response(404, json={"error": "not found"})

    return handler


@pytest.fixture()
def mock_gateway(monkeypatch):
    """Patch httpx.AsyncClient to use mock transport."""
    transport = httpx.MockTransport(_make_mock_handler())

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.pop("timeout", None)
        original_init(self, *args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    monkeypatch.setenv("PAYMENT_MODE", "hmac")


@pytest.mark.asyncio
async def test_execute_single_tool(mock_gateway):
    """Single tool execution goes through 402 → pay → receipt."""
    tool = ToolDef(
        tool_id="test_tool",
        name="Test Tool",
        description="test",
        endpoint="/seller/call",
        price="50000",
        max_latency_ms=5000,
        quality="standard",
        schema_id="invoice_v1",
        mode="fast",
        offer_id="offer_bronze_v1",
    )

    wallet = CDPWallet(private_key=TEST_KEY)
    executor = ToolChainExecutor(cdp_wallet=wallet, budget=BudgetConfig(budget_usdc=200000, max_step_price=100000))
    step = await executor.execute_tool(tool, step_num=1)

    assert step.status == "success"
    assert step.payout == 40000
    assert step.refund == 10000
    assert step.receipt_hash.startswith("0x")
    assert step.cdp_wallet_id == wallet.wallet_id


@pytest.mark.asyncio
async def test_execute_chain_two_steps(mock_gateway):
    """Full chain with 2 tools shows 2 x402 payments."""
    tools = [
        ToolDef("data_lookup", "Data Lookup", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1"),
        ToolDef("report_summarize", "Report Summary", "test", "/seller/call", "80000", 3000, "premium", "invoice_v1", "fast", "offer_silver_v1"),
    ]

    wallet = CDPWallet(private_key=TEST_KEY)
    executor = ToolChainExecutor(cdp_wallet=wallet, budget=BudgetConfig(budget_usdc=200000, max_step_price=100000))
    result = await executor.run_chain(tools)

    assert result.completed is True
    assert len(result.steps) == 2
    assert result.steps[0].tool_id == "data_lookup"
    assert result.steps[1].tool_id == "report_summarize"
    assert result.total_spent > 0
    # In HMAC mode, CDP wallet is not used for signing (sign_count stays 0).
    # In x402 mode, sign_count would be 2.
    assert "sign_count" in result.cdp_wallet_status


@pytest.mark.asyncio
async def test_chain_budget_abort(mock_gateway):
    """Chain aborts when budget is exceeded."""
    tools = [
        ToolDef("tool_a", "Tool A", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1"),
        ToolDef("tool_b", "Tool B", "test", "/seller/call", "80000", 3000, "premium", "invoice_v1", "fast", "offer_silver_v1"),
    ]

    wallet = CDPWallet(private_key=TEST_KEY)
    # Budget only enough for first tool
    executor = ToolChainExecutor(cdp_wallet=wallet, budget=BudgetConfig(budget_usdc=60000, max_step_price=100000))
    result = await executor.run_chain(tools)

    assert result.completed is False
    assert result.abort_reason is not None
    assert len(result.steps) == 2
    assert result.steps[0].status == "success"
    assert "budget_exceeded" in result.steps[1].status


@pytest.mark.asyncio
async def test_chain_result_to_dict(mock_gateway):
    """ChainResult serializes to dict for JSON export."""
    tools = [
        ToolDef("tool_a", "Tool A", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1"),
    ]

    wallet = CDPWallet(private_key=TEST_KEY)
    executor = ToolChainExecutor(cdp_wallet=wallet, budget=BudgetConfig(budget_usdc=200000, max_step_price=100000))
    result = await executor.run_chain(tools)

    d = result.to_dict()
    assert "chain_id" in d
    assert "steps" in d
    assert "total_spent" in d
    assert "budget_remaining" in d
    assert "cdp_wallet_status" in d
    # Should be JSON-serializable
    json.dumps(d)


@pytest.mark.asyncio
async def test_chain_max_step_price_abort(mock_gateway):
    """Chain aborts when tool price exceeds max_step_price."""
    tools = [
        ToolDef("expensive", "Expensive Tool", "test", "/seller/call", "150000", 5000, "premium", "invoice_v1", "fast", "offer_gold_v1"),
    ]

    wallet = CDPWallet(private_key=TEST_KEY)
    executor = ToolChainExecutor(cdp_wallet=wallet, budget=BudgetConfig(budget_usdc=500000, max_step_price=100000))
    result = await executor.run_chain(tools)

    assert result.completed is False
    assert len(result.steps) == 1
    assert "max_step_price_exceeded" in result.steps[0].status
