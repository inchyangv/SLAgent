"""Agentic tool chain — multi-step paid tool execution with budget management.

Implements a "discover → decide → authorize → outcome" chain where each tool
call is sent as a single paid request, with deterministic budget reasoning and
per-step spend tracking.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from buyer_agent.cdp_wallet import CDPWallet
from gateway.app.hashing import compute_mandate_id
from gateway.app.x402 import create_payment_token

logger = logging.getLogger("tool-chain")

TOOL_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "tool_catalog.json"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ToolDef:
    """A paid tool from the catalog."""

    tool_id: str
    name: str
    description: str
    endpoint: str
    price: str  # smallest token unit
    max_latency_ms: int
    quality: str
    schema_id: str
    mode: str
    offer_id: str


@dataclass
class BudgetConfig:
    """Deterministic budget constraints."""

    budget_usdc: int  # total budget in smallest unit (e.g. 200000 = $0.20)
    max_step_price: int  # max price per single tool call
    min_value_per_price: float = 0.0  # not used in MVP, placeholder

    @classmethod
    def default(cls) -> BudgetConfig:
        return cls(
            budget_usdc=int(os.getenv("BUDGET_USDC", "200000")),
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
    payment_hash: str  # payment header nonce or reference id
    tx_hash: str | None
    latency_ms: int
    validation_passed: bool
    cdp_wallet_id: str
    cdp_custody_mode: str
    budget_before: int
    budget_after: int
    status: str  # "success" | "failed" | "skipped" | "budget_exceeded"


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
    cdp_wallet_status: dict[str, Any]
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
            "cdp_wallet_status": self.cdp_wallet_status,
            "completed": self.completed,
            "abort_reason": self.abort_reason,
        }


# ---------------------------------------------------------------------------
# Tool catalog loader
# ---------------------------------------------------------------------------


def load_tool_catalog(path: Path | None = None) -> list[ToolDef]:
    """Load tool catalog from JSON file."""
    catalog_path = path or TOOL_CATALOG_PATH
    with open(catalog_path) as f:
        data = json.load(f)

    tools = []
    for t in data.get("tools", []):
        tools.append(
            ToolDef(
                tool_id=t["tool_id"],
                name=t["name"],
                description=t["description"],
                endpoint=t["endpoint"],
                price=t["price"],
                max_latency_ms=t["max_latency_ms"],
                quality=t["quality"],
                schema_id=t["schema_id"],
                mode=t["mode"],
                offer_id=t["offer_id"],
            )
        )
    return tools


# ---------------------------------------------------------------------------
# Budget manager
# ---------------------------------------------------------------------------


class BudgetManager:
    """Deterministic budget tracking and reasoning."""

    def __init__(self, config: BudgetConfig) -> None:
        self.config = config
        self.remaining = config.budget_usdc
        self.total_spent = 0
        self.total_refunded = 0
        self._steps: list[StepSpend] = []

    def can_afford(self, price: int) -> tuple[bool, str]:
        """Check if a tool call is within budget. Returns (ok, reason)."""
        if price > self.remaining:
            return False, f"BUDGET_EXCEEDED: price={price} > remaining={self.remaining}"
        if price > self.config.max_step_price:
            return False, f"MAX_STEP_PRICE_EXCEEDED: price={price} > max={self.config.max_step_price}"
        return True, "OK"

    def record_spend(self, price: int, refund: int) -> None:
        """Record a completed tool call spend."""
        net = price - refund
        self.total_spent += net
        self.total_refunded += refund
        self.remaining = self.config.budget_usdc - self.total_spent

    def summary(self) -> dict[str, Any]:
        return {
            "budget_initial": self.config.budget_usdc,
            "budget_remaining": self.remaining,
            "total_spent": self.total_spent,
            "total_refunded": self.total_refunded,
            "max_step_price": self.config.max_step_price,
        }


# ---------------------------------------------------------------------------
# Tool chain executor
# ---------------------------------------------------------------------------


class ToolChainExecutor:
    """Executes a multi-step paid tool chain with single-request authorization."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        seller_url: str = "http://localhost:8001",
        cdp_wallet: CDPWallet | None = None,
        budget: BudgetConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.seller_url = seller_url.rstrip("/")
        self.cdp_wallet = cdp_wallet
        self.budget_mgr = BudgetManager(budget or BudgetConfig.default())
        self.timeout = timeout
        self._chain_id = f"chain_{int(time.time() * 1000)}"

    def _make_payment_header(self, max_price: str) -> tuple[dict[str, str], str]:
        """Create payment header. Returns (headers, payment_nonce).

        If CDP wallet is available and PAYMENT_MODE=x402, uses CDP signing.
        Otherwise falls back to HMAC.
        """
        payment_mode = os.getenv("PAYMENT_MODE", "hmac")

        if payment_mode == "x402" and self.cdp_wallet:
            chain_id = int(os.getenv("CHAIN_ID", "11155111"))
            asset = os.getenv("PAYMENT_TOKEN_ADDRESS", "")
            if not asset:
                raise RuntimeError("PAYMENT_MODE=x402 requires PAYMENT_TOKEN_ADDRESS")
            token_name = os.getenv("SLA_TOKEN_NAME", "Tether USD")
            token_version = os.getenv("SLA_TOKEN_VERSION", "")
            seller_address = os.getenv("SELLER_ADDRESS", "0x" + "2" * 40)

            sign_result = self.cdp_wallet.sign_payment(
                to_address=seller_address,
                value=max_price,
                asset=asset,
                chain_id=chain_id,
                token_name=token_name,
                token_version=token_version,
            )

            return (
                {"X-PAYMENT": sign_result.signature},
                f"cdp_{sign_result.wallet_id}_{sign_result.metadata.get('sign_count', 0)}",
            )

        # HMAC fallback
        nonce = str(int(time.time() * 1000))
        token = create_payment_token(path="/v1/call", max_price=max_price, nonce=nonce)
        buyer_address = self.cdp_wallet.address if self.cdp_wallet else os.getenv("BUYER_ADDRESS", "0x" + "1" * 40)
        header_val = json.dumps({
            "token": token,
            "nonce": nonce,
            "max_price": max_price,
            "buyer": buyer_address,
        })
        return {"X-PAYMENT": header_val}, nonce

    def _build_mandate_for_tool(self, tool: ToolDef) -> dict[str, Any]:
        """Build a mandate tailored to the tool's price and SLA."""
        from gateway.app.offers import get_offer

        offer = get_offer(tool.offer_id)
        buyer_address = self.cdp_wallet.address if self.cdp_wallet else os.getenv("BUYER_ADDRESS", "0x" + "1" * 40)
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
            mandate = {
                "version": "1.0",
                "buyer": buyer_address,
                "seller": seller_address,
                "max_price": tool.price,
                "base_pay": str(int(int(tool.price) * 0.6)),
                "bonus_rules": {
                    "type": "latency_tiers",
                    "tiers": [
                        {"lte_ms": tool.max_latency_ms, "payout": tool.price},
                        {"lte_ms": tool.max_latency_ms * 2, "payout": str(int(int(tool.price) * 0.8))},
                        {"lte_ms": 999999999, "payout": str(int(int(tool.price) * 0.6))},
                    ],
                },
                "validators": [{"type": "json_schema", "schema_id": tool.schema_id}],
                "timeout_ms": tool.max_latency_ms * 2,
                "dispute": {"window_seconds": 600, "bond_amount": str(int(int(tool.price) * 0.5))},
            }

        mandate["mandate_id"] = compute_mandate_id(mandate)
        return mandate

    async def _register_mandate(self, mandate: dict[str, Any]) -> str | None:
        """Register mandate with gateway. Returns mandate_id or None."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.gateway_url}/v1/mandates",
                    json=mandate,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("mandate_id", mandate.get("mandate_id"))
            except Exception as e:
                logger.warning("Mandate registration failed: %s", e)
        return mandate.get("mandate_id")

    async def execute_tool(
        self,
        tool: ToolDef,
        step_num: int,
        previous_output: dict[str, Any] | None = None,
    ) -> StepSpend:
        """Execute a single paid tool call and record the resulting spend.

        Args:
            tool: Tool definition from catalog
            step_num: Step number in the chain
            previous_output: Output from previous step (for chaining)

        Returns:
            StepSpend record
        """
        price = int(tool.price)
        budget_before = self.budget_mgr.remaining

        # Budget check
        ok, reason = self.budget_mgr.can_afford(price)
        if not ok:
            logger.warning("Step %d (%s): %s", step_num, tool.tool_id, reason)
            return StepSpend(
                step=step_num,
                tool_id=tool.tool_id,
                tool_name=tool.name,
                price=price,
                payout=0,
                refund=0,
                receipt_id="",
                receipt_hash="",
                payment_hash="",
                tx_hash=None,
                latency_ms=0,
                validation_passed=False,
                cdp_wallet_id=self.cdp_wallet.wallet_id if self.cdp_wallet else "",
                cdp_custody_mode=self.cdp_wallet.mode if self.cdp_wallet else "",
                budget_before=budget_before,
                budget_after=budget_before,
                status=reason.split(":")[0].lower(),
            )

        # Build per-tool mandate
        mandate = self._build_mandate_for_tool(tool)
        mandate_id = await self._register_mandate(mandate)

        call_body: dict[str, Any] = {
            "mode": tool.mode,
            "mandate_id": mandate_id,
        }
        if previous_output:
            call_body["input_context"] = previous_output

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers, payment_nonce = self._make_payment_header(tool.price)
            logger.info("Step %d (%s): submitting paid tool call for %s", step_num, tool.tool_id, tool.price)
            resp = await client.post(
                f"{self.gateway_url}/v1/call?mode={tool.mode}",
                json=call_body,
                headers=headers,
            )

            if resp.status_code != 200:
                logger.error(
                    "Step %d: Paid request failed: %d %s",
                    step_num,
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
                    payment_hash=payment_nonce,
                    tx_hash=None,
                    latency_ms=0,
                    validation_passed=False,
                    cdp_wallet_id=self.cdp_wallet.wallet_id if self.cdp_wallet else "",
                    cdp_custody_mode=self.cdp_wallet.mode if self.cdp_wallet else "",
                    budget_before=budget_before,
                    budget_after=budget_before,
                    status="failed",
                )

            data = resp.json()

        # Parse result
        payout = int(data.get("payout", "0"))
        refund = int(data.get("refund", "0"))
        receipt_hash = data.get("receipt_hash", "")
        request_id = data.get("request_id", "")
        tx_hash = data.get("tx_hash")
        latency = data.get("metrics", {}).get("latency_ms", 0)
        validation = data.get("validation_passed", False)

        # Record spend (net cost = price - refund)
        self.budget_mgr.record_spend(price, refund)

        step_spend = StepSpend(
            step=step_num,
            tool_id=tool.tool_id,
            tool_name=tool.name,
            price=price,
            payout=payout,
            refund=refund,
            receipt_id=request_id,
            receipt_hash=receipt_hash,
            payment_hash=payment_nonce,
            tx_hash=tx_hash,
            latency_ms=latency,
            validation_passed=validation,
            cdp_wallet_id=self.cdp_wallet.wallet_id if self.cdp_wallet else "",
            cdp_custody_mode=self.cdp_wallet.mode if self.cdp_wallet else "",
            budget_before=budget_before,
            budget_after=self.budget_mgr.remaining,
            status="success" if validation else "failed",
        )

        logger.info(
            "Step %d (%s): payout=%d, refund=%d, budget_remaining=%d, receipt=%s",
            step_num,
            tool.tool_id,
            payout,
            refund,
            self.budget_mgr.remaining,
            receipt_hash[:16],
        )

        return step_spend

    async def run_chain(self, tools: list[ToolDef] | None = None) -> ChainResult:
        """Execute the full tool chain: discover → decide → pay each → aggregate.

        Args:
            tools: Ordered list of tools to execute. If None, loads from catalog.

        Returns:
            ChainResult with per-step spend and budget summary.
        """
        if tools is None:
            tools = load_tool_catalog()

        logger.info(
            "Starting tool chain %s: %d tools, budget=%d",
            self._chain_id,
            len(tools),
            self.budget_mgr.config.budget_usdc,
        )

        steps: list[StepSpend] = []
        previous_output: dict[str, Any] | None = None
        abort_reason: str | None = None

        for i, tool in enumerate(tools):
            step = await self.execute_tool(tool, step_num=i + 1, previous_output=previous_output)
            steps.append(step)

            if step.status in ("budget_exceeded", "max_step_price_exceeded"):
                abort_reason = f"Step {i + 1} ({tool.tool_id}): {step.status}"
                logger.warning("Chain aborted: %s", abort_reason)
                break

            if step.status == "success":
                previous_output = {
                    "tool_id": tool.tool_id,
                    "receipt_id": step.receipt_id,
                    "receipt_hash": step.receipt_hash,
                }

        result = ChainResult(
            chain_id=self._chain_id,
            steps=steps,
            total_spent=self.budget_mgr.total_spent,
            total_refunded=self.budget_mgr.total_refunded,
            budget_initial=self.budget_mgr.config.budget_usdc,
            budget_remaining=self.budget_mgr.remaining,
            budget_config=asdict(self.budget_mgr.config),
            cdp_wallet_status=self.cdp_wallet.status() if self.cdp_wallet else {},
            completed=abort_reason is None,
            abort_reason=abort_reason,
        )

        logger.info(
            "Chain %s %s: %d steps, spent=%d, refunded=%d, remaining=%d",
            self._chain_id,
            "completed" if result.completed else "aborted",
            len(steps),
            result.total_spent,
            result.total_refunded,
            result.budget_remaining,
        )

        return result
