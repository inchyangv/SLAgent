"""Agentic tool chain over deposit-first settlement."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from buyer_agent.wdk_wallet import WDKWallet
from gateway.app.hashing import compute_mandate_id

logger = logging.getLogger("tool-chain")

TOOL_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "tool_catalog.json"


@dataclass
class ToolDef:
    """A paid tool from the catalog."""

    tool_id: str
    name: str
    description: str
    endpoint: str
    price: str
    max_latency_ms: int
    quality: str
    schema_id: str
    mode: str
    offer_id: str


@dataclass
class BudgetConfig:
    """Deterministic budget constraints."""

    budget_tokens: int
    max_step_price: int
    min_value_per_price: float = 0.0

    @classmethod
    def default(cls) -> BudgetConfig:
        return cls(
            budget_tokens=int(os.getenv("BUDGET_USDT", os.getenv("BUDGET_USDC", "200000"))),
            max_step_price=int(os.getenv("MAX_STEP_PRICE", "100000")),
        )


@dataclass
class StepSpend:
    """Spend record for one tool call step."""

    step: int
    tool_id: str
    tool_name: str
    price: int
    payout: int
    refund: int
    receipt_id: str
    receipt_hash: str
    deposit_tx_hash: str | None
    tx_hash: str | None
    latency_ms: int
    validation_passed: bool
    wallet_address: str
    wallet_mode: str
    budget_before: int
    budget_after: int
    status: str


@dataclass
class ChainResult:
    """Result of a full multi-step tool chain execution."""

    chain_id: str
    steps: list[StepSpend]
    total_spent: int
    total_refunded: int
    budget_initial: int
    budget_remaining: int
    budget_config: dict[str, Any]
    wallet_status: dict[str, Any]
    completed: bool
    abort_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "steps": [asdict(s) for s in self.steps],
            "total_spent": self.total_spent,
            "total_refunded": self.total_refunded,
            "budget_initial": self.budget_initial,
            "budget_remaining": self.budget_remaining,
            "budget_config": self.budget_config,
            "wallet_status": self.wallet_status,
            "completed": self.completed,
            "abort_reason": self.abort_reason,
        }


def load_tool_catalog(path: Path | None = None) -> list[ToolDef]:
    """Load tool catalog from JSON file."""
    catalog_path = path or TOOL_CATALOG_PATH
    with catalog_path.open(encoding="utf-8") as f:
        data = json.load(f)

    return [
        ToolDef(
            tool_id=item["tool_id"],
            name=item["name"],
            description=item["description"],
            endpoint=item["endpoint"],
            price=item["price"],
            max_latency_ms=item["max_latency_ms"],
            quality=item["quality"],
            schema_id=item["schema_id"],
            mode=item["mode"],
            offer_id=item["offer_id"],
        )
        for item in data.get("tools", [])
    ]


class BudgetManager:
    """Deterministic budget tracking and reasoning."""

    def __init__(self, config: BudgetConfig) -> None:
        self.config = config
        self.remaining = config.budget_tokens
        self.total_spent = 0
        self.total_refunded = 0

    def can_afford(self, price: int) -> tuple[bool, str]:
        if price > self.remaining:
            return False, f"BUDGET_EXCEEDED: price={price} > remaining={self.remaining}"
        if price > self.config.max_step_price:
            return False, f"MAX_STEP_PRICE_EXCEEDED: price={price} > max={self.config.max_step_price}"
        return True, "OK"

    def record_spend(self, price: int, refund: int) -> None:
        net = price - refund
        self.total_spent += net
        self.total_refunded += refund
        self.remaining = self.config.budget_tokens - self.total_spent

    def summary(self) -> dict[str, Any]:
        return {
            "budget_initial": self.config.budget_tokens,
            "budget_remaining": self.remaining,
            "total_spent": self.total_spent,
            "total_refunded": self.total_refunded,
            "max_step_price": self.config.max_step_price,
        }


class ToolChainExecutor:
    """Execute a multi-step tool chain using deposit-first authorization."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        seller_url: str = "http://localhost:8001",
        wallet: WDKWallet | None = None,
        budget: BudgetConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        buyer_address = os.getenv("BUYER_ADDRESS", "").strip() or None
        self.gateway_url = gateway_url.rstrip("/")
        self.seller_url = seller_url.rstrip("/")
        self.wallet = wallet or WDKWallet.from_env(role="buyer", expected_address=buyer_address)
        self.budget_mgr = BudgetManager(budget or BudgetConfig.default())
        self.timeout = timeout
        self._chain_id = f"chain_{int(time.time() * 1000)}"

    def _wallet_mode(self) -> str:
        return "wdk_sidecar" if self.wallet else "mock_no_wallet"

    def _resolve_buyer_address(self) -> str:
        if self.wallet:
            return self.wallet.ensure_wallet_loaded()
        return os.getenv("BUYER_ADDRESS", "0x" + "1" * 40)

    def _submit_deposit(self, *, request_id: str, amount: int) -> str | None:
        if not self.wallet:
            return None

        settlement_addr = os.getenv("SETTLEMENT_CONTRACT_ADDRESS", "").strip()
        token_addr = os.getenv("PAYMENT_TOKEN_ADDRESS", "").strip()
        if not settlement_addr or not token_addr:
            return None

        buyer_address = self.wallet.ensure_wallet_loaded()
        self.wallet.approve(
            spender=settlement_addr,
            amount=amount,
            token_address=token_addr,
        )
        return self.wallet.deposit(
            request_id=request_id,
            amount=amount,
            settlement_contract=settlement_addr,
            buyer_address=buyer_address,
        )

    def _build_mandate_for_tool(self, tool: ToolDef) -> dict[str, Any]:
        from gateway.app.offers import get_offer

        offer = get_offer(tool.offer_id)
        buyer_address = self._resolve_buyer_address()
        seller_address = os.getenv("SELLER_ADDRESS", "0x" + "2" * 40)

        if offer:
            mandate = {
                "version": "1.0",
                "buyer": buyer_address,
                "seller": seller_address,
                "max_price": tool.price,
                "base_pay": offer["base_pay"],
                "bonus_rules": offer["bonus_rules"],
                "validators": offer["validators"],
                "timeout_ms": offer["timeout_ms"],
                "dispute": offer["dispute"],
            }
        else:
            price = int(tool.price)
            mandate = {
                "version": "1.0",
                "buyer": buyer_address,
                "seller": seller_address,
                "max_price": tool.price,
                "base_pay": str(int(price * 0.6)),
                "bonus_rules": {
                    "type": "latency_tiers",
                    "tiers": [
                        {"lte_ms": tool.max_latency_ms, "payout": tool.price},
                        {"lte_ms": tool.max_latency_ms * 2, "payout": str(int(price * 0.8))},
                        {"lte_ms": 999999999, "payout": str(int(price * 0.6))},
                    ],
                },
                "validators": [{"type": "json_schema", "schema_id": tool.schema_id}],
                "timeout_ms": tool.max_latency_ms * 2,
                "dispute": {"window_seconds": 600, "bond_amount": str(int(price * 0.5))},
            }

        mandate["mandate_id"] = compute_mandate_id(mandate)
        return mandate

    async def _register_mandate(self, mandate: dict[str, Any]) -> str | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(f"{self.gateway_url}/v1/mandates", json=mandate)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("mandate_id", mandate.get("mandate_id"))
            except Exception as exc:
                logger.warning("Mandate registration failed: %s", exc)
        return mandate.get("mandate_id")

    def _wallet_status(self) -> dict[str, Any]:
        if not self.wallet:
            return {}

        address = ""
        try:
            address = self.wallet.ensure_wallet_loaded()
        except Exception as exc:
            logger.warning("WDK wallet status unavailable: %s", exc)

        return {
            "address": address,
            "service_url": self.wallet.service_url,
            "account_index": self.wallet.account_index,
            "mode": self._wallet_mode(),
        }

    async def execute_tool(
        self,
        tool: ToolDef,
        step_num: int,
        previous_output: dict[str, Any] | None = None,
    ) -> StepSpend:
        price = int(tool.price)
        budget_before = self.budget_mgr.remaining
        wallet_address = ""

        ok, reason = self.budget_mgr.can_afford(price)
        if not ok:
            return StepSpend(
                step=step_num,
                tool_id=tool.tool_id,
                tool_name=tool.name,
                price=price,
                payout=0,
                refund=0,
                receipt_id="",
                receipt_hash="",
                deposit_tx_hash=None,
                tx_hash=None,
                latency_ms=0,
                validation_passed=False,
                wallet_address=wallet_address,
                wallet_mode=self._wallet_mode(),
                budget_before=budget_before,
                budget_after=budget_before,
                status=reason.split(":")[0].lower(),
            )

        mandate = self._build_mandate_for_tool(tool)
        mandate_id = await self._register_mandate(mandate)
        request_id = f"{self._chain_id}_step_{step_num:02d}"

        call_body: dict[str, Any] = {
            "mode": tool.mode,
            "mandate_id": mandate_id,
            "request_id": request_id,
            "buyer": mandate["buyer"],
        }
        if previous_output:
            call_body["input_context"] = previous_output

        deposit_tx_hash = None
        try:
            wallet_address = self._resolve_buyer_address()
            deposit_tx_hash = self._submit_deposit(request_id=request_id, amount=price)
        except Exception as exc:
            logger.warning("Step %d (%s): deposit submission failed: %s", step_num, tool.tool_id, exc)

        headers: dict[str, str] = {}
        if deposit_tx_hash:
            headers["X-DEPOSIT-TX-HASH"] = deposit_tx_hash
            call_body["deposit_tx_hash"] = deposit_tx_hash

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.gateway_url}/v1/call?mode={tool.mode}",
                json=call_body,
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error(
                    "Step %d (%s): paid request failed: %d %s",
                    step_num,
                    tool.tool_id,
                    resp.status_code,
                    resp.text[:200],
                )
                return StepSpend(
                    step=step_num,
                    tool_id=tool.tool_id,
                    tool_name=tool.name,
                    price=price,
                    payout=0,
                    refund=0,
                    receipt_id="",
                    receipt_hash="",
                    deposit_tx_hash=deposit_tx_hash,
                    tx_hash=None,
                    latency_ms=0,
                    validation_passed=False,
                    wallet_address=wallet_address,
                    wallet_mode=self._wallet_mode(),
                    budget_before=budget_before,
                    budget_after=budget_before,
                    status="failed",
                )
            data = resp.json()

        payout = int(data.get("payout", "0"))
        refund = int(data.get("refund", "0"))
        receipt_hash = data.get("receipt_hash", "")
        receipt_id = data.get("request_id", request_id)
        tx_hash = data.get("settle_tx_hash") or data.get("tx_hash")
        latency = int(data.get("metrics", {}).get("latency_ms", 0))
        validation = bool(data.get("validation_passed", False))

        self.budget_mgr.record_spend(price, refund)

        return StepSpend(
            step=step_num,
            tool_id=tool.tool_id,
            tool_name=tool.name,
            price=price,
            payout=payout,
            refund=refund,
            receipt_id=receipt_id,
            receipt_hash=receipt_hash,
            deposit_tx_hash=deposit_tx_hash,
            tx_hash=tx_hash,
            latency_ms=latency,
            validation_passed=validation,
            wallet_address=wallet_address,
            wallet_mode=self._wallet_mode(),
            budget_before=budget_before,
            budget_after=self.budget_mgr.remaining,
            status="success" if validation else "failed",
        )

    async def run_chain(self, tools: list[ToolDef] | None = None) -> ChainResult:
        if tools is None:
            tools = load_tool_catalog()

        steps: list[StepSpend] = []
        previous_output: dict[str, Any] | None = None
        abort_reason: str | None = None

        for index, tool in enumerate(tools, start=1):
            step = await self.execute_tool(tool, step_num=index, previous_output=previous_output)
            steps.append(step)

            if step.status in ("budget_exceeded", "max_step_price_exceeded"):
                abort_reason = f"Step {index} ({tool.tool_id}): {step.status}"
                break

            if step.status == "success":
                previous_output = {
                    "tool_id": tool.tool_id,
                    "receipt_id": step.receipt_id,
                    "receipt_hash": step.receipt_hash,
                }

        return ChainResult(
            chain_id=self._chain_id,
            steps=steps,
            total_spent=self.budget_mgr.total_spent,
            total_refunded=self.budget_mgr.total_refunded,
            budget_initial=self.budget_mgr.config.budget_tokens,
            budget_remaining=self.budget_mgr.remaining,
            budget_config=asdict(self.budget_mgr.config),
            wallet_status=self._wallet_status(),
            completed=abort_reason is None,
            abort_reason=abort_reason,
        )
