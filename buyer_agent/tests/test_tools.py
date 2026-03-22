"""Tests for the deposit-first agentic tool chain."""

from __future__ import annotations

import json

import httpx
import pytest

from buyer_agent.tools import (
    BudgetConfig,
    BudgetManager,
    ToolChainExecutor,
    ToolDef,
    load_tool_catalog,
)


class FakeWDKWallet:
    def __init__(self) -> None:
        self.service_url = "http://localhost:3100"
        self.account_index = 0
        self._address = "0x1111111111111111111111111111111111111111"
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def ensure_wallet_loaded(self) -> str:
        self.calls.append(("load", {}))
        return self._address

    async def approve(self, **kwargs) -> str:
        self.calls.append(("approve", kwargs))
        return "0xapprove"

    async def deposit(self, **kwargs) -> str:
        self.calls.append(("deposit", kwargs))
        return f"0xdeposit_{len([c for c in self.calls if c[0] == 'deposit'])}"

    async def approve_and_deposit(self, **kwargs) -> dict:
        self.calls.append(("approve", kwargs))
        self.calls.append(("deposit", kwargs))
        n = len([c for c in self.calls if c[0] == "deposit"])
        return {"approve_tx_hash": "0xapprove", "deposit_tx_hash": f"0xdeposit_{n}"}


def test_load_tool_catalog():
    tools = load_tool_catalog()
    assert len(tools) >= 2
    assert all(tool.tool_id for tool in tools)


def test_budget_can_afford():
    budget = BudgetManager(BudgetConfig(budget_tokens=200000, max_step_price=100000))
    ok, reason = budget.can_afford(50000)
    assert ok is True
    assert reason == "OK"


def test_budget_exceeded():
    budget = BudgetManager(BudgetConfig(budget_tokens=30000, max_step_price=100000))
    ok, reason = budget.can_afford(50000)
    assert ok is False
    assert "BUDGET_EXCEEDED" in reason


def test_budget_record_spend():
    budget = BudgetManager(BudgetConfig(budget_tokens=200000, max_step_price=100000))
    budget.record_spend(price=50000, refund=10000)
    assert budget.total_spent == 40000
    assert budget.total_refunded == 10000
    assert budget.remaining == 160000


def _make_mock_handler():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if "/v1/mandates" in url and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={"mandate_id": body.get("mandate_id", "m_test")})

        if "/v1/call" in url and request.method == "POST":
            body = json.loads(request.content)
            call_count["n"] += 1
            return httpx.Response(
                200,
                json={
                    "request_id": body.get("request_id", f"req_tool_{call_count['n']}"),
                    "seller_response": {"invoice_id": f"INV-{call_count['n']}"},
                    "metrics": {"ttft_ms": 100, "latency_ms": 500},
                    "validation_passed": True,
                    "payout": "40000",
                    "refund": "10000",
                    "receipt_hash": f"0xreceipt_{call_count['n']}",
                    "deposit_tx_hash": body.get("deposit_tx_hash"),
                    "settle_tx_hash": f"0xsettle_{call_count['n']}",
                    "tx_hash": f"0xtx_{call_count['n']}",
                },
            )

        return httpx.Response(404, json={"error": "not found"})

    return handler


@pytest.fixture()
def mock_gateway(monkeypatch):
    transport = httpx.MockTransport(_make_mock_handler())
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.pop("timeout", None)
        original_init(self, *args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


@pytest.mark.asyncio
async def test_execute_single_tool_uses_deposit_first(mock_gateway, monkeypatch):
    monkeypatch.setenv("SETTLEMENT_CONTRACT_ADDRESS", "0x9999999999999999999999999999999999999999")
    monkeypatch.setenv("PAYMENT_TOKEN_ADDRESS", "0x8888888888888888888888888888888888888888")
    wallet = FakeWDKWallet()

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

    executor = ToolChainExecutor(wallet=wallet, budget=BudgetConfig(budget_tokens=200000, max_step_price=100000))
    step = await executor.execute_tool(tool, step_num=1)

    assert step.status == "success"
    assert step.deposit_tx_hash is not None
    assert step.wallet_address == wallet._address
    assert step.wallet_mode == "wdk_sidecar"
    assert [call[0] for call in wallet.calls] == ["load", "load", "load", "approve", "deposit"]


@pytest.mark.asyncio
async def test_execute_chain_two_steps(mock_gateway, monkeypatch):
    monkeypatch.setenv("SETTLEMENT_CONTRACT_ADDRESS", "0x9999999999999999999999999999999999999999")
    monkeypatch.setenv("PAYMENT_TOKEN_ADDRESS", "0x8888888888888888888888888888888888888888")
    wallet = FakeWDKWallet()
    tools = [
        ToolDef("data_lookup", "Data Lookup", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1"),
        ToolDef("report_summarize", "Report Summary", "test", "/seller/call", "80000", 3000, "premium", "invoice_v1", "fast", "offer_silver_v1"),
    ]

    executor = ToolChainExecutor(wallet=wallet, budget=BudgetConfig(budget_tokens=200000, max_step_price=100000))
    result = await executor.run_chain(tools)

    assert result.completed is True
    assert len(result.steps) == 2
    assert result.steps[0].deposit_tx_hash is not None
    assert result.total_spent > 0
    assert result.wallet_status["address"] == wallet._address


@pytest.mark.asyncio
async def test_chain_budget_abort(mock_gateway):
    tools = [
        ToolDef("tool_a", "Tool A", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1"),
        ToolDef("tool_b", "Tool B", "test", "/seller/call", "80000", 3000, "premium", "invoice_v1", "fast", "offer_silver_v1"),
    ]

    executor = ToolChainExecutor(wallet=None, budget=BudgetConfig(budget_tokens=60000, max_step_price=100000))
    result = await executor.run_chain(tools)

    assert result.completed is False
    assert result.abort_reason is not None
    assert len(result.steps) == 2
    assert result.steps[1].status == "budget_exceeded"


@pytest.mark.asyncio
async def test_chain_result_to_dict(mock_gateway):
    tool = ToolDef("tool_a", "Tool A", "test", "/seller/call", "50000", 5000, "standard", "invoice_v1", "fast", "offer_bronze_v1")

    executor = ToolChainExecutor(wallet=None, budget=BudgetConfig(budget_tokens=200000, max_step_price=100000))
    result = await executor.run_chain([tool])

    data = result.to_dict()
    assert "chain_id" in data
    assert "steps" in data
    assert "wallet_status" in data
    json.dumps(data)


@pytest.mark.asyncio
async def test_chain_max_step_price_abort(mock_gateway):
    tool = ToolDef("expensive", "Expensive Tool", "test", "/seller/call", "150000", 5000, "premium", "invoice_v1", "fast", "offer_gold_v1")

    executor = ToolChainExecutor(wallet=None, budget=BudgetConfig(budget_tokens=500000, max_step_price=100000))
    result = await executor.run_chain([tool])

    assert result.completed is False
    assert len(result.steps) == 1
    assert result.steps[0].status == "max_step_price_exceeded"
