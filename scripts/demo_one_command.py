#!/usr/bin/env python3
"""SLAgent-402 — One-Command Demo Orchestration.

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

import argparse
import os
import signal
import subprocess
import sys
import time

# Ensure project root is in path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import httpx  # noqa: E402

# Inject demo keys before anything else
from gateway.app.demo_keys import inject_demo_env  # noqa: E402

demo_injected = inject_demo_env()

GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))
SELLER_PORT = int(os.getenv("SELLER_PORT", "8001"))
WDK_PORT = int(os.getenv("WDK_PORT", "3100"))
GATEWAY_URL = f"http://localhost:{GATEWAY_PORT}"
SELLER_URL = f"http://localhost:{SELLER_PORT}"
WDK_URL = os.getenv("WDK_SERVICE_URL", f"http://localhost:{WDK_PORT}")


def log(step: str, msg: str) -> None:
    print(f"  [{step}] {msg}")


def wait_for_health(
    url: str,
    name: str,
    timeout: int = 15,
    request_timeout: float = 3.0,
) -> bool:
    """Wait for a service to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"{url}", timeout=request_timeout)
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SLAgent-402 one-command demo")
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Run the autonomous buyer loop instead of the fixed three scenarios",
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
        help="Autonomous budget in token base units",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=int(os.getenv("AUTONOMOUS_MAX_ROUNDS", "10")),
        help="Maximum autonomous rounds to execute",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 64)
    print("  SLAgent-402 — One-Command Demo")
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
    wdk_already_running = False

    try:
        resp = httpx.get(f"{WDK_URL}/health", timeout=2.0)
        if resp.status_code == 200:
            wdk_already_running = True
            log("CHECK", f"WDK sidecar already running at {WDK_URL}")
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass

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
        # Step 1: Start WDK sidecar
        if not wdk_already_running:
            log("START", f"Starting WDK sidecar on port {WDK_PORT}...")
            wdk_proc = subprocess.Popen(
                [
                    "node",
                    "src/server.mjs",
                ],
                cwd=os.path.join(_project_root, "wdk-service"),
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(wdk_proc)

            if not wait_for_health(
                f"{WDK_URL}/health",
                "wdk-service",
                request_timeout=6.0,
            ):
                log("FAIL", "WDK sidecar failed to start")
                return 1
            log("START", "WDK sidecar is reachable")

        # Step 2: Start seller
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

        # Step 3: Start gateway
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

        # Step 4: Run buyer agent
        print(f"\n{'='*64}")
        print("  RUNNING BUYER AGENT")
        print(f"{'='*64}")

        import asyncio

        from buyer_agent.client import InvariantViolation
        from buyer_agent.main import (
            parse_seller_targets,
            print_autonomous_round,
            print_autonomous_summary,
            print_negotiation,
            print_result,
            print_summary,
        )

        buyer_key = os.getenv("BUYER_PRIVATE_KEY")

        async def run_demo():
            if args.autonomous:
                from buyer_agent.loop import AutonomousBuyerLoop

                loop = AutonomousBuyerLoop(
                    gateway_url=GATEWAY_URL,
                    seller_targets=parse_seller_targets(args.seller_urls, SELLER_URL),
                    buyer_address=os.getenv("BUYER_ADDRESS", "0xDEMO_BUYER"),
                    buyer_private_key=buyer_key,
                    budget_tokens=args.budget,
                    max_rounds=args.max_rounds,
                )
                return await loop.run()

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

        demo_result = asyncio.run(run_demo())

        if args.autonomous:
            for round_result in demo_result.rounds:
                print_autonomous_round(round_result)
            print_autonomous_summary(demo_result)
            results = demo_result.rounds
        else:
            print_summary(demo_result)
            results = demo_result

        # Step 5: Final summary
        print(f"{'='*64}")
        print("  DEMO COMPLETE")
        print(f"{'='*64}")

        if args.autonomous:
            success_count = sum(1 for round_result in results if round_result.status == "success")
            print(f"\n  Rounds: {len(results)} total, {success_count} successful")
            print(f"  Disputes opened: {demo_result.disputes_opened}")
        else:
            success_count = sum(1 for r in results if r.get("result") and r["result"].success)
            print(f"\n  Scenarios: {len(results)} total, {success_count} passed")

            has_attestations = any(
                (
                    r.get("result")
                    and r["result"].attestation_status.get("status", {}).get("count", 0) > 0
                )
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

        if args.autonomous:
            print(f"  Stop reason: {demo_result.stop_reason}")
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
