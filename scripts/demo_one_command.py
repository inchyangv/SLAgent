#!/usr/bin/env python3
"""SLA-Pay v2 — One-Command Demo Orchestration.

Starts all services, runs the full demo flow, and shuts down cleanly.

Steps:
  1. Inject demo keys (DEMO_PRIVATE_KEY or DEMO_MNEMONIC)
  2. Start seller service (port 8001)
  3. Start gateway service (port 8000)
  4. Health check both services
  5. Run buyer agent (negotiate → 3 scenarios → attestations)
  6. Print presentation-friendly summary
  7. Shut down services

Usage:
    # Minimal: one secret
    DEMO_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \\
        python scripts/demo_one_command.py

    # With Gemini (for real LLM calls):
    DEMO_PRIVATE_KEY=0x... GEMINI_API_KEY=... python scripts/demo_one_command.py

    # With mnemonic (role-separated keys):
    DEMO_MNEMONIC="test test test test test test test test test test test junk" \\
        python scripts/demo_one_command.py

WARNING: Hackathon demo only — never use production keys!
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

# Ensure project root is in path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import httpx

# Inject demo keys before anything else
from gateway.app.demo_keys import inject_demo_env

demo_injected = inject_demo_env()

GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))
SELLER_PORT = int(os.getenv("SELLER_PORT", "8001"))
GATEWAY_URL = f"http://localhost:{GATEWAY_PORT}"
SELLER_URL = f"http://localhost:{SELLER_PORT}"


def log(step: str, msg: str) -> None:
    print(f"  [{step}] {msg}")


def wait_for_health(url: str, name: str, timeout: int = 15) -> bool:
    """Wait for a service to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"{url}", timeout=3.0)
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    print("=" * 64)
    print("  SLA-Pay v2 — One-Command Demo")
    print("  Pay by proof, not upfront.")
    print("=" * 64)

    # Check demo keys
    if demo_injected:
        log("KEYS", "Demo keys injected from env")
        buyer_key = os.getenv("BUYER_PRIVATE_KEY", "")
        if buyer_key:
            from eth_account import Account
            addr = Account.from_key(buyer_key).address
            log("KEYS", f"Buyer address: {addr}")
    else:
        log("KEYS", "No DEMO_PRIVATE_KEY or DEMO_MNEMONIC set")
        log("KEYS", "Attestations will be skipped (no signing keys)")

    # Check if services are already running
    gateway_already_running = False
    seller_already_running = False

    try:
        resp = httpx.get(f"{GATEWAY_URL}/v1/health", timeout=2.0)
        if resp.status_code == 200:
            gateway_already_running = True
            log("CHECK", f"Gateway already running at {GATEWAY_URL}")
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass

    try:
        resp = httpx.get(f"{SELLER_URL}/seller/health", timeout=2.0)
        if resp.status_code == 200:
            seller_already_running = True
            log("CHECK", f"Seller already running at {SELLER_URL}")
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass

    processes: list[subprocess.Popen] = []

    try:
        # Step 1: Start seller
        if not seller_already_running:
            log("START", f"Starting seller on port {SELLER_PORT}...")
            env = {**os.environ, "SELLER_FALLBACK": os.getenv("SELLER_FALLBACK", "true")}
            seller_proc = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "seller.main:app",
                    "--port", str(SELLER_PORT),
                    "--host", "127.0.0.1",
                    "--log-level", "warning",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(seller_proc)

            if not wait_for_health(f"{SELLER_URL}/seller/health", "seller"):
                log("FAIL", "Seller failed to start")
                return 1
            log("START", "Seller is healthy")

        # Step 2: Start gateway
        if not gateway_already_running:
            log("START", f"Starting gateway on port {GATEWAY_PORT}...")
            env = {**os.environ, "SELLER_UPSTREAM_URL": SELLER_URL}
            gateway_proc = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "gateway.app.main:app",
                    "--port", str(GATEWAY_PORT),
                    "--host", "127.0.0.1",
                    "--log-level", "warning",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(gateway_proc)

            if not wait_for_health(f"{GATEWAY_URL}/v1/health", "gateway"):
                log("FAIL", "Gateway failed to start")
                return 1
            log("START", "Gateway is healthy")

        # Step 3: Run buyer agent
        print(f"\n{'='*64}")
        print("  RUNNING BUYER AGENT")
        print(f"{'='*64}")

        import asyncio
        from buyer_agent.main import run_agent, print_header, print_result, print_summary
        from buyer_agent.main import print_negotiation
        from buyer_agent.client import InvariantViolation

        buyer_key = os.getenv("BUYER_PRIVATE_KEY")

        async def run_demo():
            from buyer_agent.client import BuyerAgent

            agent = BuyerAgent(
                gateway_url=GATEWAY_URL,
                seller_url=SELLER_URL,
                buyer_address=os.getenv("BUYER_ADDRESS", "0xDEMO_BUYER"),
                buyer_private_key=buyer_key,
            )

            # Phase 1: Negotiate
            try:
                negotiation = await agent.negotiate_mandate()
                print_negotiation(negotiation)
                if not negotiation.seller_accepted:
                    log("WARN", "Seller did not accept mandate")
            except Exception as exc:
                log("WARN", f"Negotiation skipped: {exc}")

            # Phase 2: Execute scenarios
            scenarios = [
                {"mode": "fast", "label": "Fast + Valid", "expect": "full payout"},
                {"mode": "slow", "label": "Slow + Valid", "expect": "base pay only"},
                {"mode": "invalid", "label": "Invalid Output", "expect": "zero payout"},
            ]

            results = []
            for scenario in scenarios:
                try:
                    result = await agent.call(mode=scenario["mode"])
                    print_result(scenario, result)
                    results.append({"label": scenario["label"], "result": result})
                except InvariantViolation as exc:
                    log("REFUSED", str(exc))
                    results.append({"label": scenario["label"], "result": None})

            return results

        results = asyncio.run(run_demo())
        print_summary(results)

        # Step 4: Final summary
        print(f"{'='*64}")
        print("  DEMO COMPLETE")
        print(f"{'='*64}")

        success_count = sum(1 for r in results if r.get("result") and r["result"].success)
        print(f"\n  Scenarios: {len(results)} total, {success_count} passed")

        # Check attestation status
        has_attestations = any(
            r.get("result") and r["result"].attestation_status.get("status", {}).get("count", 0) > 0
            for r in results
            if r.get("result")
        )
        if has_attestations:
            for r in results:
                res = r.get("result")
                if res and res.attestation_status:
                    status = res.attestation_status.get("status", {})
                    count = status.get("count", 0)
                    complete = status.get("complete", False)
                    parties = status.get("parties_signed", [])
                    tag = "COMPLETE" if complete else f"{count}/3"
                    print(f"  Attestations ({r['label']}): {tag} — {parties}")
        else:
            print("  Attestations: skipped (set DEMO_PRIVATE_KEY for signing)")

        print(f"\n  Dashboard: open dashboard/index.html (set gateway URL to {GATEWAY_URL})")
        print()

        return 0

    except KeyboardInterrupt:
        log("STOP", "Interrupted by user")
        return 130

    finally:
        # Shut down started services
        for proc in processes:
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                proc.kill()
        if processes:
            log("STOP", f"Shut down {len(processes)} service(s)")


if __name__ == "__main__":
    sys.exit(main())
