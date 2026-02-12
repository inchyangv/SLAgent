#!/usr/bin/env python3
"""Resolver CLI — open or resolve disputes on-chain.

Usage:
    # Open dispute for a request
    python scripts/resolve_dispute.py open --request-id req_20260212_...

    # Resolve dispute with final payout
    python scripts/resolve_dispute.py resolve --request-id req_20260212_... --final-payout 60000

Note: In MVP without live chain, this operates in mock mode and logs actions.
"""

import argparse
import json
import sys

import httpx


def open_dispute(gateway_url: str, request_id: str) -> None:
    """Open a dispute via gateway API."""
    resp = httpx.post(
        f"{gateway_url}/v1/disputes/open",
        json={"request_id": request_id},
    )
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))


def resolve_dispute(gateway_url: str, request_id: str, final_payout: int) -> None:
    """Resolve a dispute via gateway API."""
    resp = httpx.post(
        f"{gateway_url}/v1/disputes/resolve",
        json={"request_id": request_id, "final_payout": final_payout},
    )
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="SLA-Pay v2 Dispute Resolver CLI")
    parser.add_argument("--gateway-url", default="http://localhost:8000", help="Gateway URL")

    subparsers = parser.add_subparsers(dest="command", required=True)

    open_parser = subparsers.add_parser("open", help="Open a dispute")
    open_parser.add_argument("--request-id", required=True, help="Request ID to dispute")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve a dispute")
    resolve_parser.add_argument("--request-id", required=True, help="Request ID to resolve")
    resolve_parser.add_argument("--final-payout", type=int, required=True, help="Final payout amount")

    args = parser.parse_args()

    if args.command == "open":
        open_dispute(args.gateway_url, args.request_id)
    elif args.command == "resolve":
        resolve_dispute(args.gateway_url, args.request_id, args.final_payout)


if __name__ == "__main__":
    main()
