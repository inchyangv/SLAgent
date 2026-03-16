#!/usr/bin/env python3
"""Agentic tool-chain demo over deposit-first settlement."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.app.demo_keys import inject_demo_env  # noqa: E402

inject_demo_env()

from buyer_agent.tools import BudgetConfig, ToolChainExecutor, load_tool_catalog  # noqa: E402
from buyer_agent.wdk_wallet import WDKWallet  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-18s %(levelname)-5s %(message)s",
)


def _token_symbol() -> str:
    return os.getenv("SLA_TOKEN_SYMBOL", "USDT")


def _sep(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def run_demo(
    gateway_url: str,
    seller_url: str,
    budget_tokens: int,
    max_step_price: int,
) -> None:
    token_symbol = _token_symbol()
    tools = load_tool_catalog()

    _sep("STEP 1: Tool Catalog Discovery")
    print(f"Loaded {len(tools)} paid tools:")
    for tool in tools:
        print(
            f"  [{tool.tool_id}] {tool.name} "
            f"price={tool.price} quality={tool.quality} sla={tool.max_latency_ms}ms"
        )

    _sep("STEP 2: WDK Wallet Initialization")
    buyer_address = os.getenv("BUYER_ADDRESS", "").strip() or None
    wallet = WDKWallet.from_env(role="buyer", expected_address=buyer_address)
    if wallet:
        address = wallet.ensure_wallet_loaded()
        print(f"WDK wallet ready:")
        print(f"  address:       {address}")
        print(f"  service_url:   {wallet.service_url}")
        print(f"  account_index: {wallet.account_index}")
    else:
        print("No WDK seed phrase configured. Running in mock/no-chain mode.")

    _sep("STEP 3: Budget Reasoning")
    budget = BudgetConfig(budget_tokens=budget_tokens, max_step_price=max_step_price)
    total_tool_cost = sum(int(tool.price) for tool in tools)
    print(f"Budget config:")
    print(f"  total_budget:   {budget.budget_tokens} ({budget.budget_tokens / 1_000_000:.2f} {token_symbol})")
    print(f"  max_step_price: {budget.max_step_price} ({budget.max_step_price / 1_000_000:.2f} {token_symbol})")
    print(f"  total tool cost:{total_tool_cost:>10} ({total_tool_cost / 1_000_000:.2f} {token_symbol})")

    _sep("STEP 4: Execute Deposit-First Chain")
    executor = ToolChainExecutor(
        gateway_url=gateway_url,
        seller_url=seller_url,
        wallet=wallet,
        budget=budget,
    )
    result = await executor.run_chain(tools)

    _sep("STEP 5: Spend Report")
    print(f"Chain ID: {result.chain_id}")
    print(f"Status:   {'COMPLETED' if result.completed else 'ABORTED'}")
    if result.abort_reason:
        print(f"Abort:    {result.abort_reason}")
    print()

    header = (
        f"{'Step':>4} {'Tool':<22} {'Price':>8} {'Payout':>8} {'Refund':>8} "
        f"{'Net':>8} {'Latency':>8} {'Valid':>6} {'Status':<12} {'Deposit':<14}"
    )
    print(header)
    print("-" * len(header))

    for step in result.steps:
        net = step.price - step.refund
        deposit_short = (step.deposit_tx_hash or "-")[:12]
        print(
            f"{step.step:>4} {step.tool_name:<22} {step.price:>8} {step.payout:>8} {step.refund:>8} "
            f"{net:>8} {step.latency_ms:>7}ms {str(step.validation_passed):>6} "
            f"{step.status:<12} {deposit_short:<14}"
        )

    _sep("STEP 6: Wallet Audit")
    if result.wallet_status:
        print(json.dumps(result.wallet_status, indent=2))
    else:
        print("(no WDK wallet configured)")

    _sep("STEP 7: JSON Export")
    print(json.dumps(result.to_dict(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Deposit-first tool-chain demo")
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--seller-url", default=os.getenv("SELLER_URL", "http://localhost:8001"))
    parser.add_argument(
        "--budget",
        type=int,
        default=int(os.getenv("BUDGET_USDT", os.getenv("BUDGET_TOKENS", "200000"))),
        help="Total budget in smallest token unit",
    )
    parser.add_argument(
        "--max-step-price",
        type=int,
        default=int(os.getenv("MAX_STEP_PRICE", "100000")),
        help="Max price per tool call in smallest token unit",
    )
    args = parser.parse_args()

    asyncio.run(
        run_demo(
            gateway_url=args.gateway_url,
            seller_url=args.seller_url,
            budget_tokens=args.budget,
            max_step_price=args.max_step_price,
        )
    )


if __name__ == "__main__":
    main()
