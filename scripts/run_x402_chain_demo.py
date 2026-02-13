#!/usr/bin/env python3
"""x402 Agentic Tool Chain Demo — multi-step paid workflow.

Demonstrates:
1. Tool catalog discovery
2. CDP Wallet initialization
3. Budget reasoning (deterministic)
4. 2+ paid tool calls (each 402 → pay → retry)
5. Per-step spend tracking + final report

Usage:
    # Start gateway + seller first, then:
    python scripts/run_x402_chain_demo.py

    # With custom budget:
    python scripts/run_x402_chain_demo.py --budget 150000

    # x402 mode (requires BUYER_PRIVATE_KEY):
    PAYMENT_MODE=x402 python scripts/run_x402_chain_demo.py

Prerequisites:
    - Gateway running on http://localhost:8000
    - Seller running on http://localhost:8001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.app.demo_keys import inject_demo_env  # noqa: E402

inject_demo_env()

from buyer_agent.cdp_wallet import CDPWallet  # noqa: E402
from buyer_agent.tools import (  # noqa: E402
    BudgetConfig,
    ToolChainExecutor,
    load_tool_catalog,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-18s %(levelname)-5s %(message)s",
)
logger = logging.getLogger("x402-chain-demo")


def _sep(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


async def run_demo(
    gateway_url: str,
    seller_url: str,
    budget_usdc: int,
    max_step_price: int,
) -> None:
    # ── Step 1: Discover tools ────────────────────────────────────────────
    _sep("STEP 1: Tool Catalog Discovery")
    tools = load_tool_catalog()
    print(f"Loaded {len(tools)} paid tools:")
    for t in tools:
        print(f"  [{t.tool_id}] {t.name} — price={t.price}, quality={t.quality}, SLA={t.max_latency_ms}ms")
    print()

    # ── Step 2: Initialize CDP Wallet ─────────────────────────────────────
    _sep("STEP 2: CDP Wallet Initialization")
    buyer_key = os.getenv("BUYER_PRIVATE_KEY", "")
    buyer_address = os.getenv("BUYER_ADDRESS", "")
    if not buyer_key:
        print("WARNING: No BUYER_PRIVATE_KEY — using demo key derivation")
        buyer_key = "0x" + "a1" * 32
        buyer_address = "0x1111111111111111111111111111111111111111"

    cdp_wallet = CDPWallet(private_key=buyer_key, address=buyer_address or None)
    wallet_status = cdp_wallet.status()
    print(f"CDP Wallet ready:")
    print(f"  wallet_id:  {wallet_status['wallet_id']}")
    print(f"  address:    {wallet_status['address']}")
    print(f"  mode:       {wallet_status['mode']}")
    print(f"  custody:    {wallet_status['custody']}")
    print()

    # ── Step 3: Budget reasoning ──────────────────────────────────────────
    _sep("STEP 3: Budget Reasoning")
    budget = BudgetConfig(budget_usdc=budget_usdc, max_step_price=max_step_price)
    total_tool_cost = sum(int(t.price) for t in tools)
    print(f"Budget config:")
    print(f"  total_budget:   {budget.budget_usdc} ({budget.budget_usdc / 1_000_000:.2f} USDC)")
    print(f"  max_step_price: {budget.max_step_price} ({budget.max_step_price / 1_000_000:.2f} USDC)")
    print(f"  total tool cost: {total_tool_cost} ({total_tool_cost / 1_000_000:.2f} USDC)")
    if total_tool_cost > budget.budget_usdc:
        print(f"  WARNING: Total tool cost exceeds budget — chain will abort mid-way")
    else:
        print(f"  OK: Budget sufficient for all tools")
    print()

    # ── Step 4: Execute tool chain ────────────────────────────────────────
    _sep("STEP 4: Execute Tool Chain (402 → Pay → Outcome per step)")
    executor = ToolChainExecutor(
        gateway_url=gateway_url,
        seller_url=seller_url,
        cdp_wallet=cdp_wallet,
        budget=budget,
    )

    result = await executor.run_chain(tools)

    # ── Step 5: Per-step spend report ─────────────────────────────────────
    _sep("STEP 5: Spend Report")
    print(f"Chain ID: {result.chain_id}")
    print(f"Status:   {'COMPLETED' if result.completed else 'ABORTED'}")
    if result.abort_reason:
        print(f"Abort:    {result.abort_reason}")
    print()

    header = f"{'Step':>4} {'Tool':<22} {'Price':>8} {'Payout':>8} {'Refund':>8} {'Net':>8} {'Latency':>8} {'Valid':>6} {'Status':<12} {'Receipt':<18}"
    print(header)
    print("-" * len(header))

    for s in result.steps:
        net = s.price - s.refund
        receipt_short = s.receipt_hash[:16] + "..." if s.receipt_hash else "-"
        print(
            f"{s.step:>4} {s.tool_name:<22} {s.price:>8} {s.payout:>8} {s.refund:>8} {net:>8} "
            f"{s.latency_ms:>7}ms {str(s.validation_passed):>6} {s.status:<12} {receipt_short:<18}"
        )

    print()
    print(f"Total spent (net):  {result.total_spent:>8} ({result.total_spent / 1_000_000:.4f} USDC)")
    print(f"Total refunded:     {result.total_refunded:>8} ({result.total_refunded / 1_000_000:.4f} USDC)")
    print(f"Budget initial:     {result.budget_initial:>8}")
    print(f"Budget remaining:   {result.budget_remaining:>8}")

    # ── CDP Wallet audit ──────────────────────────────────────────────────
    _sep("CDP Wallet Audit")
    ws = result.cdp_wallet_status
    if ws:
        print(f"  wallet_id:   {ws.get('wallet_id', '-')}")
        print(f"  address:     {ws.get('address', '-')}")
        print(f"  custody:     {ws.get('custody', '-')}")
        print(f"  sign_count:  {ws.get('sign_count', 0)}")
    else:
        print("  (no CDP wallet used)")

    # ── JSON export ───────────────────────────────────────────────────────
    _sep("JSON Export (for submission evidence)")
    export = result.to_dict()
    print(json.dumps(export, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="x402 Agentic Tool Chain Demo")
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--seller-url", default=os.getenv("SELLER_URL", "http://localhost:8001"))
    parser.add_argument("--budget", type=int, default=int(os.getenv("BUDGET_USDC", "200000")),
                        help="Total budget in smallest token unit (default: 200000 = $0.20)")
    parser.add_argument("--max-step-price", type=int, default=int(os.getenv("MAX_STEP_PRICE", "100000")),
                        help="Max price per tool call (default: 100000 = $0.10)")
    args = parser.parse_args()

    asyncio.run(run_demo(
        gateway_url=args.gateway_url,
        seller_url=args.seller_url,
        budget_usdc=args.budget,
        max_step_price=args.max_step_price,
    ))


if __name__ == "__main__":
    main()
