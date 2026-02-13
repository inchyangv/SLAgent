#!/usr/bin/env python3
"""SLA-Pay v2 End-to-End Demo Script.

Runs three scenarios against the gateway:
1. Fast + valid   → full payout ($0.10)
2. Slow + valid   → base pay ($0.06)
3. Invalid output  → zero payout (full refund)

Prerequisites:
    # Terminal 1: Start demo seller
    uvicorn gateway.demo_seller.main:app --port 8001

    # Terminal 2: Start gateway
    uvicorn gateway.app.main:app --port 8000

    # Terminal 3: Run this script
    python scripts/run_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

from gateway.app.demo_keys import inject_demo_env
from gateway.app.x402 import create_payment_token, create_x402_payment

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


def _default_address(fill: str) -> str:
    return "0x" + (fill * 40)


def make_payment_header(path: str = "/v1/call") -> dict[str, str]:
    """Create a valid payment header for the demo.

    Supports two modes:
    - PAYMENT_MODE=hmac (default): JSON header with HMAC token
    - PAYMENT_MODE=x402: Base64 header with EIP-712 signed authorization (see gateway/app/x402.py)
    """
    payment_mode = os.getenv("PAYMENT_MODE", "hmac")

    buyer_address = os.getenv("BUYER_ADDRESS", "") or _default_address("1")
    seller_address = os.getenv("SELLER_ADDRESS", "") or _default_address("2")

    if payment_mode == "x402":
        buyer_private_key = os.getenv("BUYER_PRIVATE_KEY", "")
        if not buyer_private_key:
            raise RuntimeError("PAYMENT_MODE=x402 requires BUYER_PRIVATE_KEY")

        # Default to SKALE hackathon chain (BITE v2 Sandbox 2) unless overridden.
        chain_id = int(os.getenv("CHAIN_ID", "103698795"))
        # Default to predeployed USDC on the hackathon chain if not provided.
        asset = os.getenv("PAYMENT_TOKEN_ADDRESS", "") or "0xc4083B1E81ceb461Ccef3FDa8A9F24F0d764B6D8"
        token_name = os.getenv("SLA_TOKEN_NAME", "USDC")
        token_version = os.getenv("SLA_TOKEN_VERSION", "")

        header_val = create_x402_payment(
            private_key=buyer_private_key,
            from_address=buyer_address,
            to_address=seller_address,
            value=MAX_PRICE,
            asset=asset,
            chain_id=chain_id,
            token_name=token_name,
            token_version=token_version,
        )
        return {"X-PAYMENT": header_val}

    # Default: HMAC mode
    nonce = str(int(time.time() * 1000))
    token = create_payment_token(path=path, max_price=MAX_PRICE, nonce=nonce)
    header_val = json.dumps(
        {
            "token": token,
            "nonce": nonce,
            "max_price": MAX_PRICE,
            "buyer": buyer_address,
        }
    )
    return {"X-PAYMENT": header_val}


def run_scenario(client: httpx.Client, scenario: dict) -> dict | None:
    """Run a single demo scenario."""
    name = scenario["name"]
    mode = scenario["mode"]

    print(f"\n{'='*60}")
    print(f"  Scenario: {name} (mode={mode})")
    print(f"{'='*60}")

    # Step 1: Unpaid request → expect 402
    print("\n  [1] Sending unpaid request...")
    resp = client.post(
        f"{GATEWAY_URL}/v1/call",
        json={"mode": mode},
    )
    if resp.status_code != 402:
        print(f"  ERROR: Expected 402, got {resp.status_code}")
        return None
    print(f"  ✓ Got 402 Payment Required")
    payment_details = resp.json()
    print(f"    max_price: {payment_details['accepts'][0]['maxAmountRequired']}")

    # Step 2: Paid request
    print("\n  [2] Sending paid request...")
    headers = make_payment_header()
    resp = client.post(
        f"{GATEWAY_URL}/v1/call?mode={mode}",
        json={"mode": mode},
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

    print(f"\n  Results:")
    print(f"    request_id:       {request_id}")
    print(f"    latency_ms:       {metrics.get('latency_ms', '-')}")
    print(f"    ttft_ms:          {metrics.get('ttft_ms', '-')}")
    print(f"    validation_passed: {validation_passed}")
    print(f"    payout:           {payout} ({payout/1_000_000:.6f} USDC)")
    print(f"    refund:           {refund} ({refund/1_000_000:.6f} USDC)")
    print(f"    receipt_hash:     {receipt_hash[:20]}...")
    print(f"    tx_hash:          {tx_hash or 'mock (no chain)'}")

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
    print("  SLA-Pay v2 — End-to-End Demo")
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
        print("    uvicorn gateway.demo_seller.main:app --port 8001")
        print("    uvicorn gateway.app.main:app --port 8000")
        sys.exit(1)

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
