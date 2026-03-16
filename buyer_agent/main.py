#!/usr/bin/env python3
"""SLAgent-402 Buyer Agent — autonomous buyer CLI.

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
import os
import sys

import httpx

from buyer_agent.client import BuyerAgent, BuyerResult, InvariantViolation, NegotiationResult
from buyer_agent.loop import (
    AutonomousBuyerLoop,
    AutonomousLoopResult,
    AutonomousRound,
    AutonomousSellerTarget,
)
from gateway.app.demo_keys import inject_demo_env
from shared.env import bootstrap_env

# Load repo-root .env, then inject demo keys (if configured).
bootstrap_env()
inject_demo_env()


SCENARIOS = [
    {"mode": "fast", "label": "Fast + Valid", "expect": "full payout"},
    {"mode": "slow", "label": "Slow + Valid", "expect": "base pay only"},
    {"mode": "invalid", "label": "Invalid Output", "expect": "zero payout (full refund)"},
]


def _token_symbol() -> str:
    return os.getenv("SLA_TOKEN_SYMBOL", "USDT")


def _format_amount(value: int) -> str:
    token_symbol = _token_symbol()
    return f"{value:>8} ({value / 1_000_000:.6f} {token_symbol})"


def print_header() -> None:
    print("=" * 64)
    print("  SLAgent-402 — Autonomous Buyer Agent")
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
    print(f"  payout:            {_format_amount(result.payout)}")
    print(f"  refund:            {_format_amount(result.refund)}")
    print(f"  receipt_hash:      {result.receipt_hash[:24]}...")
    print(f"  tx_hash:           {result.tx_hash or 'mock (no chain)'}")

    print("\n  Invariant Checks:")
    for check in result.invariant_checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"    [{status}] {check['name']}: {check['detail']}")

    # Attestation status
    attest = result.attestation_status
    if attest:
        status_info = attest.get("status", {})
        count = status_info.get("count", 0)
        complete = status_info.get("complete", False)
        parties = status_info.get("parties_signed", [])
        print(f"\n  Attestations: {count}/3 {'(COMPLETE)' if complete else ''}")
        for party in parties:
            print(f"    [{party}] signed")


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


def print_autonomous_round(round_result: AutonomousRound) -> None:
    latency_value = round_result.latency_ms if round_result.latency_ms is not None else "-"
    print(f"\n{'─'*64}")
    print(f"  Round {round_result.round_number}: {round_result.seller_id}")
    print(f"{'─'*64}")
    print(f"  seller_url:         {round_result.seller_url}")
    print(f"  seller_score:       {round_result.seller_score:.2f}")
    print(f"  request_id:         {round_result.request_id or '-'}")
    print(f"  latency_ms:         {latency_value}")
    print(f"  validation_passed:  {round_result.validation_passed}")
    print(f"  payout:             {_format_amount(round_result.payout)}")
    print(f"  refund:             {_format_amount(round_result.refund)}")
    print(f"  budget_before:      {round_result.budget_before}")
    print(f"  budget_after:       {round_result.budget_after}")
    print(f"  disputed:           {round_result.disputed}")
    if round_result.dispute_reasons:
        print(f"  dispute_reasons:    {', '.join(round_result.dispute_reasons)}")
    print(f"  status:             {round_result.status}")
    if round_result.error:
        print(f"  error:              {round_result.error}")


def print_autonomous_summary(result: AutonomousLoopResult) -> None:
    print(f"\n{'='*64}")
    print("  AUTONOMOUS LOOP SUMMARY")
    print(f"{'='*64}")
    print(f"  Rounds completed:   {len(result.rounds)}")
    print(f"  Budget initial:     {result.budget_initial}")
    print(f"  Budget remaining:   {result.budget_remaining}")
    print(f"  Sellers seen:       {', '.join(result.sellers_seen) if result.sellers_seen else '-'}")
    print(f"  Disputes opened:    {result.disputes_opened}")
    print(f"  Stop reason:        {result.stop_reason}")
    print()


def print_negotiation(neg: NegotiationResult) -> None:
    print(f"\n{'─'*64}")
    print("  NEGOTIATION PHASE")
    print(f"{'─'*64}")
    caps = neg.seller_capabilities
    print(f"  Seller address:    {caps.get('seller_address', 'N/A')}")
    print(f"  LLM provider:      {caps.get('llm_provider', 'N/A')}")
    print(f"  LLM model:         {caps.get('llm_model', 'N/A')}")
    print(f"  LLM available:     {caps.get('llm_available', False)}")
    print(f"  Supported schemas: {caps.get('supported_schemas', [])}")
    print(f"  Mandate ID:        {neg.mandate_id[:24]}...")
    print(f"  Max price:         {neg.mandate.get('max_price', 'N/A')}")
    print(f"  Seller accepted:   {neg.seller_accepted}")
    print(f"  Summary:           {neg.summary}")


def parse_seller_targets(raw: str | None, default_url: str) -> list[AutonomousSellerTarget]:
    """Parse `url|mode|delay_ms|label` targets from CLI input."""
    entries = [item.strip() for item in (raw.split(",") if raw else [default_url]) if item.strip()]
    targets: list[AutonomousSellerTarget] = []

    for entry in entries:
        parts = [part.strip() for part in entry.split("|")]
        seller_url = parts[0]
        mode = parts[1] if len(parts) >= 2 and parts[1] else "fast"
        delay_ms = int(parts[2]) if len(parts) >= 3 and parts[2] else 0
        label = parts[3] if len(parts) >= 4 else ""
        targets.append(
            AutonomousSellerTarget(
                seller_url=seller_url,
                mode=mode,
                delay_ms=delay_ms,
                label=label,
            )
        )

    return targets


async def run_agent(
    gateway_url: str,
    seller_url: str = "http://localhost:8001",
    modes: list[str] | None = None,
    buyer_address: str = "0xBUYER_AGENT_0000000000000000000000000001",
    buyer_private_key: str | None = None,
) -> list[dict]:
    """Run the buyer agent for given scenarios."""
    agent = BuyerAgent(
        gateway_url=gateway_url,
        seller_url=seller_url,
        buyer_address=buyer_address,
        buyer_private_key=buyer_private_key,
    )

    # Phase 1: Negotiate
    try:
        negotiation = await agent.negotiate_mandate()
        print_negotiation(negotiation)
        if not negotiation.seller_accepted:
            print("  WARNING: Seller did not accept mandate. Proceeding anyway for demo.")
    except Exception as exc:
        print(f"\n  Negotiation skipped (seller unavailable): {exc}")

    # Phase 2: Execute scenarios
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
    print(f"  Seller:  {args.seller_url}")
    print(f"  Buyer:   {args.buyer_address}")

    buyer_key = args.buyer_private_key or os.getenv("BUYER_PRIVATE_KEY")

    if args.autonomous:
        seller_targets = parse_seller_targets(args.seller_urls, args.seller_url)
        loop = AutonomousBuyerLoop(
            gateway_url=args.gateway_url,
            seller_targets=seller_targets,
            buyer_address=args.buyer_address,
            buyer_private_key=buyer_key,
            budget_tokens=args.budget,
            max_rounds=args.max_rounds,
        )
        loop_result = await loop.run()
        for round_result in loop_result.rounds:
            print_autonomous_round(round_result)
        print_autonomous_summary(loop_result)
        return 0 if loop_result.rounds else 1

    modes = args.modes.split(",") if args.modes else None
    results = await run_agent(
        gateway_url=args.gateway_url,
        seller_url=args.seller_url,
        modes=modes,
        buyer_address=args.buyer_address,
        buyer_private_key=buyer_key,
    )
    print_summary(results)

    failed = sum(1 for r in results if not r.get("result") or not r["result"].success)
    return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SLAgent-402 Buyer Agent")
    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8000",
        help="Gateway URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--seller-url",
        default="http://localhost:8001",
        help="Seller URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--buyer-address",
        default="0xBUYER_AGENT_0000000000000000000000000001",
        help="Buyer EVM address",
    )
    parser.add_argument(
        "--buyer-private-key",
        default=None,
        help="Buyer private key for attestation signing (or BUYER_PRIVATE_KEY env)",
    )
    parser.add_argument(
        "--modes",
        default=None,
        help="Comma-separated modes to run (default: all — fast,slow,invalid)",
    )
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Run the budgeted autonomous loop instead of the fixed preset scenarios",
    )
    parser.add_argument(
        "--seller-urls",
        default=None,
        help="Comma-separated sellers as url|mode|delay_ms|label entries for autonomous mode",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=int(os.getenv("AUTONOMOUS_BUDGET", "1000000")),
        help="Autonomous budget in token base units (default: 1000000)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=int(os.getenv("AUTONOMOUS_MAX_ROUNDS", "10")),
        help="Maximum autonomous rounds to execute (default: 10)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
