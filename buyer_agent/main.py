#!/usr/bin/env python3
"""SLA-Pay v2 Buyer Agent — autonomous buyer CLI.

Demonstrates an agentic commerce flow:
1. Decides which scenarios to run
2. Handles 402 payment challenges autonomously
3. Verifies receipt invariants (fail-closed)
4. Prints structured summary for presentation

Prerequisites:
    # Terminal 1: Start seller (LLM or demo)
    uvicorn seller.main:app --port 8001
    # Terminal 2: Start gateway
    uvicorn gateway.app.main:app --port 8000
    # Terminal 3: Run buyer agent
    python -m buyer_agent.main
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from buyer_agent.client import BuyerAgent, BuyerResult, InvariantViolation


SCENARIOS = [
    {"mode": "fast", "label": "Fast + Valid", "expect": "full payout"},
    {"mode": "slow", "label": "Slow + Valid", "expect": "base pay only"},
    {"mode": "invalid", "label": "Invalid Output", "expect": "zero payout (full refund)"},
]


def print_header() -> None:
    print("=" * 64)
    print("  SLA-Pay v2 — Autonomous Buyer Agent")
    print("  Verifying receipts. Refusing bad deals.")
    print("=" * 64)


def print_result(scenario: dict, result: BuyerResult) -> None:
    label = scenario["label"]
    print(f"\n{'─'*64}")
    print(f"  Scenario: {label} (mode={scenario['mode']})")
    print(f"  Expected: {scenario['expect']}")
    print(f"{'─'*64}")

    if result.error and not result.success:
        print(f"  ERROR: {result.error}")
        return

    print(f"  request_id:        {result.request_id}")
    print(f"  latency_ms:        {result.metrics.get('latency_ms', '-')}")
    print(f"  ttft_ms:           {result.metrics.get('ttft_ms', '-')}")
    print(f"  validation_passed: {result.validation_passed}")
    print(f"  payout:            {result.payout:>8} ({result.payout / 1_000_000:.6f} SLAT)")
    print(f"  refund:            {result.refund:>8} ({result.refund / 1_000_000:.6f} SLAT)")
    print(f"  receipt_hash:      {result.receipt_hash[:24]}...")
    print(f"  tx_hash:           {result.tx_hash or 'mock (no chain)'}")

    print(f"\n  Invariant Checks:")
    for check in result.invariant_checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"    [{status}] {check['name']}: {check['detail']}")


def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*64}")
    print("  BUYER AGENT SUMMARY")
    print(f"{'='*64}")
    print(f"\n  {'Scenario':<20} {'Payout':>10} {'Refund':>10} {'Invariants':>12}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*12}")

    passed = 0
    failed = 0
    for r in results:
        name = r["label"]
        res: BuyerResult | None = r.get("result")
        if res and res.success:
            payout = str(res.payout)
            refund = str(res.refund)
            inv = "ALL PASS"
            passed += 1
        elif res:
            payout = str(res.payout)
            refund = str(res.refund)
            violations = sum(1 for c in res.invariant_checks if not c["passed"])
            inv = f"{violations} FAIL"
            failed += 1
        else:
            payout = refund = "ERROR"
            inv = "N/A"
            failed += 1
        print(f"  {name:<20} {payout:>10} {refund:>10} {inv:>12}")

    print(f"\n  Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    if failed > 0:
        print("  Buyer agent REFUSED responses with invariant violations (fail-closed).")
    else:
        print("  All receipts verified. Buyer agent accepts all settlements.")
    print()


async def run_agent(
    gateway_url: str,
    modes: list[str] | None = None,
    buyer_address: str = "0xBUYER_AGENT_0000000000000000000000000001",
) -> list[dict]:
    """Run the buyer agent for given scenarios."""
    agent = BuyerAgent(
        gateway_url=gateway_url,
        buyer_address=buyer_address,
    )

    scenarios = SCENARIOS if modes is None else [s for s in SCENARIOS if s["mode"] in modes]
    results = []

    for scenario in scenarios:
        try:
            result = await agent.call(mode=scenario["mode"])
            print_result(scenario, result)
            results.append({"label": scenario["label"], "result": result})
        except InvariantViolation as exc:
            # Buyer refuses — this is expected for bad receipts
            # The result is attached to the exception context
            # Build a partial result from what we know
            print(f"\n  REFUSED: {exc}")
            results.append({"label": scenario["label"], "result": None})

    return results


async def main_async(args: argparse.Namespace) -> int:
    # Check gateway health
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{args.gateway_url}/v1/health")
            if resp.status_code != 200:
                print(f"ERROR: Gateway not healthy at {args.gateway_url}")
                return 1
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to gateway at {args.gateway_url}")
        print("  Start the services first:")
        print("    uvicorn seller.main:app --port 8001")
        print("    uvicorn gateway.app.main:app --port 8000")
        return 1

    print_header()
    print(f"\n  Gateway: {args.gateway_url}")
    print(f"  Buyer:   {args.buyer_address}")

    modes = args.modes.split(",") if args.modes else None
    results = await run_agent(
        gateway_url=args.gateway_url,
        modes=modes,
        buyer_address=args.buyer_address,
    )
    print_summary(results)

    failed = sum(1 for r in results if not r.get("result") or not r["result"].success)
    return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SLA-Pay v2 Buyer Agent")
    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8000",
        help="Gateway URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--buyer-address",
        default="0xBUYER_AGENT_0000000000000000000000000001",
        help="Buyer EVM address",
    )
    parser.add_argument(
        "--modes",
        default=None,
        help="Comma-separated modes to run (default: all — fast,slow,invalid)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
