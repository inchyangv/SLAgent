#!/usr/bin/env python3
"""SLAgent-402 End-to-End Demo Script."""

from __future__ import annotations

import os
import sys
import time
import uuid

import httpx

from buyer_agent.client import BuyerAgent
from shared.env import bootstrap_env

from gateway.app.demo_keys import inject_demo_env

# Load repo-root .env, then inject demo keys (if configured).
bootstrap_env()

# Inject demo keys before anything reads env vars
inject_demo_env()

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
SELLER_URL = os.getenv("SELLER_URL", "http://localhost:8001")
MAX_PRICE = "100000"

SCENARIOS = [
    {"name": "Fast + Valid", "mode": "fast", "expected_payout_range": (80000, 100000)},
    {"name": "Slow + Valid", "mode": "slow", "expected_payout_range": (60000, 60000)},
    {"name": "Invalid Output", "mode": "invalid", "expected_payout_range": (0, 0)},
]


def _token_symbol() -> str:
    return os.getenv("SLA_TOKEN_SYMBOL", "USDT")


def _default_address(fill: str) -> str:
    return "0x" + (fill * 40)


def _make_request_id(mode: str) -> str:
    ts_ms = int(time.time() * 1000)
    return f"req_{mode}_{ts_ms}_{uuid.uuid4().hex[:8]}"


def _maybe_submit_deposit(request_id: str, buyer_address: str) -> str | None:
    buyer_private_key = os.getenv("BUYER_PRIVATE_KEY", "")
    if not buyer_private_key:
        return None

    agent = BuyerAgent(
        gateway_url=GATEWAY_URL,
        seller_url=SELLER_URL,
        buyer_address=buyer_address,
        max_price=MAX_PRICE,
        buyer_private_key=buyer_private_key,
    )
    return agent._submit_buyer_deposit(request_id, int(MAX_PRICE))


def run_scenario(client: httpx.Client, scenario: dict) -> dict | None:
    """Run a single demo scenario."""
    name = scenario["name"]
    mode = scenario["mode"]
    token_symbol = _token_symbol()
    buyer_address = os.getenv("BUYER_ADDRESS", "") or _default_address("1")
    request_id = _make_request_id(mode)
    headers: dict[str, str] = {}
    call_body: dict[str, object] = {"mode": mode, "buyer": buyer_address, "request_id": request_id}

    print(f"\n{'='*60}")
    print(f"  Scenario: {name} (mode={mode})")
    print(f"{'='*60}")

    print("\n  [1] Preparing deposit context...")
    try:
        deposit_tx_hash = _maybe_submit_deposit(request_id, buyer_address)
    except Exception as e:
        print(f"  ERROR: Deposit failed: {e}")
        return None

    if deposit_tx_hash:
        headers["X-DEPOSIT-TX-HASH"] = deposit_tx_hash
        call_body["deposit_tx_hash"] = deposit_tx_hash
        print(f"  ✓ Deposit submitted: {deposit_tx_hash}")
    else:
        print("  ✓ No chain deposit submitted (mock/no-chain mode)")

    print("\n  [2] Sending request...")
    resp = client.post(
        f"{GATEWAY_URL}/v1/call?mode={mode}",
        json=call_body,
        headers=headers,
    )

    if resp.status_code != 200:
        print(f"  ERROR: Expected 200, got {resp.status_code}")
        print(f"  Body: {resp.text}")
        return None

    data = resp.json()
    print(f"  ✓ Got 200 OK")

    # Parse results
    request_id = data.get("request_id", "")
    metrics = data.get("metrics", {})
    validation_passed = data.get("validation_passed", False)
    payout = int(data.get("payout", "0"))
    refund = int(data.get("refund", "0"))
    receipt_hash = data.get("receipt_hash", "")
    tx_hash = data.get("tx_hash")
    deposit_tx_hash = data.get("deposit_tx_hash")

    # LLM evidence: check seller response headers (forwarded via gateway response)
    breach_reasons = data.get("breach_reasons", [])

    print(f"\n  Results:")
    print(f"    request_id:       {request_id}")
    print(f"    latency_ms:       {metrics.get('latency_ms', '-')}")
    print(f"    ttft_ms:          {metrics.get('ttft_ms', '-')}")
    print(f"    validation_passed: {validation_passed}")
    print(f"    payout:           {payout} ({payout/1_000_000:.6f} {token_symbol})")
    print(f"    refund:           {refund} ({refund/1_000_000:.6f} {token_symbol})")
    print(f"    receipt_hash:     {receipt_hash[:20]}...")
    print(f"    deposit_tx_hash:  {deposit_tx_hash or 'mock (no chain)'}")
    print(f"    tx_hash:          {tx_hash or 'mock (no chain)'}")
    if breach_reasons:
        print(f"    breach_reasons:   {', '.join(breach_reasons)}")

    # Verify expected payout range
    lo, hi = scenario["expected_payout_range"]
    if lo <= payout <= hi:
        print(f"  ✓ Payout {payout} is within expected range [{lo}, {hi}]")
    else:
        print(f"  ✗ Payout {payout} is OUTSIDE expected range [{lo}, {hi}]")

    # Submit attestations (buyer + seller)
    submit_attestations(client, request_id, receipt_hash)

    return data


def submit_attestations(client: httpx.Client, request_id: str, receipt_hash: str) -> None:
    """Submit buyer + seller attestations for a receipt."""
    buyer_private_key = os.getenv("BUYER_PRIVATE_KEY", "")
    seller_private_key = os.getenv("SELLER_PRIVATE_KEY", "")

    if not buyer_private_key and not seller_private_key:
        print(f"\n  [Attestation] Skipped (no signing keys set)")
        return

    print(f"\n  [3] Submitting attestations...")

    # Buyer attestation
    if buyer_private_key:
        try:
            from gateway.app.attestation import sign_receipt_hash

            buyer_sig = sign_receipt_hash(receipt_hash, buyer_private_key)
            buyer_address = os.getenv("BUYER_ADDRESS", "")
            if not buyer_address:
                from eth_account import Account

                buyer_address = Account.from_key(buyer_private_key).address
            resp = client.post(
                f"{GATEWAY_URL}/v1/receipts/{request_id}/attest",
                json={"role": "buyer", "signature": buyer_sig, "address": buyer_address},
            )
            if resp.status_code == 200:
                print(f"  ✓ Buyer attestation submitted")
            else:
                print(f"  ✗ Buyer attestation failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ Buyer attestation error: {e}")

    # Seller attestation (request signature from seller service)
    if seller_private_key:
        try:
            resp = client.post(
                f"{SELLER_URL}/seller/receipts/attest",
                json={"receipt_hash": receipt_hash},
            )
            if resp.status_code == 200:
                seller_data = resp.json()
                resp2 = client.post(
                    f"{GATEWAY_URL}/v1/receipts/{request_id}/attest",
                    json={
                        "role": "seller",
                        "signature": seller_data["signature"],
                        "address": seller_data.get("seller_address"),
                    },
                )
                if resp2.status_code == 200:
                    print(f"  ✓ Seller attestation submitted")
                else:
                    print(f"  ✗ Seller attestation submit failed: {resp2.status_code}")
            else:
                print(f"  ✗ Seller signing failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ Seller attestation error: {e}")

    # Check final status
    try:
        resp = client.get(f"{GATEWAY_URL}/v1/receipts/{request_id}/attestations")
        if resp.status_code == 200:
            status = resp.json()
            count = status.get("count", 0)
            complete = status.get("complete", False)
            parties = status.get("parties_signed", [])
            print(f"  Attestations: {count}/3 {'(COMPLETE)' if complete else ''} — {parties}")
    except Exception:
        pass


def main() -> None:
    print("=" * 60)
    print("  SLAgent-402 — End-to-End Demo")
    print("  Pay by proof, not upfront.")
    print("=" * 60)

    # Check services are running
    client = httpx.Client(timeout=30.0)

    try:
        health = client.get(f"{GATEWAY_URL}/v1/health")
        if health.status_code != 200:
            print(f"\nERROR: Gateway not responding at {GATEWAY_URL}")
            sys.exit(1)
        print(f"\n✓ Gateway is healthy at {GATEWAY_URL}")
    except httpx.ConnectError:
        print(f"\nERROR: Cannot connect to gateway at {GATEWAY_URL}")
        print("  Start the services first:")
        print("    GEMINI_API_KEY=... uvicorn seller.main:app --port 8001")
        print("    uvicorn gateway.app.main:app --port 8000")
        sys.exit(1)

    # Check seller capabilities (LLM evidence)
    try:
        caps = client.get(f"{SELLER_URL}/seller/capabilities")
        if caps.status_code == 200:
            caps_data = caps.json()
            llm_provider = caps_data.get("llm_provider", "unknown")
            llm_model = caps_data.get("llm_model", "unknown")
            llm_available = caps_data.get("llm_available", False)
            seller_type = "Gemini LLM" if llm_available else "Fallback (deterministic)"
            print(f"✓ Seller: {seller_type} ({llm_provider}/{llm_model})")
            if not llm_available:
                print("  ⚠ GEMINI_API_KEY not set — using deterministic fallback responses")
        else:
            print(f"✓ Seller at {SELLER_URL} (capabilities endpoint not available)")
    except httpx.ConnectError:
        print(f"  ⚠ Cannot reach seller at {SELLER_URL} — gateway will proxy to upstream")

    # Run scenarios
    results = []
    for scenario in SCENARIOS:
        result = run_scenario(client, scenario)
        results.append({"scenario": scenario["name"], "result": result})

    # Summary
    print(f"\n{'='*60}")
    print("  DEMO SUMMARY")
    print(f"{'='*60}")
    print(f"\n  {'Scenario':<20} {'Payout':>10} {'Refund':>10} {'Valid':>8}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*8}")

    for r in results:
        name = r["scenario"]
        d = r["result"]
        if d:
            payout = d.get("payout", "0")
            refund = d.get("refund", "0")
            valid = "PASS" if d.get("validation_passed") else "FAIL"
        else:
            payout = refund = "ERROR"
            valid = "N/A"
        print(f"  {name:<20} {payout:>10} {refund:>10} {valid:>8}")

    print(f"\n  Total scenarios: {len(results)}")
    print(f"  Successful: {sum(1 for r in results if r['result'] is not None)}")
    print()


if __name__ == "__main__":
    main()
