"""Buyer agent HTTP client — handles 402 challenge and paid request flow.

This module encapsulates the autonomous buyer's interaction with the SLA-Pay gateway:
1. Send unpaid request → receive 402 with payment details
2. Generate payment authorization
3. Send paid request → receive response with receipt
4. Verify receipt invariants (fail-closed)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from gateway.app.x402 import create_payment_token

logger = logging.getLogger("buyer-agent")


@dataclass
class BuyerResult:
    """Result of a single buyer agent call."""

    request_id: str
    mode: str
    success: bool
    metrics: dict[str, Any]
    validation_passed: bool
    payout: int
    refund: int
    max_price: int
    receipt_hash: str
    tx_hash: str | None
    seller_response: dict[str, Any]
    invariant_checks: list[dict[str, Any]]
    error: str | None = None


class InvariantViolation(Exception):
    """Raised when a receipt invariant check fails (fail-closed)."""


class BuyerAgent:
    """Autonomous buyer agent that interacts with SLA-Pay gateway."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        buyer_address: str = "0xBUYER_AGENT_0000000000000000000000000001",
        max_price: str = "100000",
        timeout: float = 30.0,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.buyer_address = buyer_address
        self.max_price = max_price
        self.timeout = timeout

    def _make_payment_header(self, path: str = "/v1/call") -> dict[str, str]:
        """Create x402-compatible payment header."""
        nonce = str(int(time.time() * 1000))
        token = create_payment_token(
            path=path,
            max_price=self.max_price,
            nonce=nonce,
        )
        header_val = json.dumps({
            "token": token,
            "nonce": nonce,
            "max_price": self.max_price,
            "buyer": self.buyer_address,
        })
        return {"X-PAYMENT": header_val}

    async def call(self, mode: str = "fast") -> BuyerResult:
        """Execute the full buyer flow: 402 challenge → paid request → verify.

        Args:
            mode: Seller mode (fast, slow, invalid)

        Returns:
            BuyerResult with all details.

        Raises:
            InvariantViolation: If receipt invariants fail (fail-closed behavior).
        """
        max_price_int = int(self.max_price)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Step 1: Unpaid request → expect 402
            resp_402 = await client.post(
                f"{self.gateway_url}/v1/call",
                json={"mode": mode},
            )

            if resp_402.status_code != 402:
                return BuyerResult(
                    request_id="",
                    mode=mode,
                    success=False,
                    metrics={},
                    validation_passed=False,
                    payout=0,
                    refund=0,
                    max_price=max_price_int,
                    receipt_hash="",
                    tx_hash=None,
                    seller_response={},
                    invariant_checks=[],
                    error=f"Expected 402, got {resp_402.status_code}",
                )

            # Step 2: Paid request
            headers = self._make_payment_header()
            resp = await client.post(
                f"{self.gateway_url}/v1/call?mode={mode}",
                json={"mode": mode},
                headers=headers,
            )

            if resp.status_code != 200:
                return BuyerResult(
                    request_id="",
                    mode=mode,
                    success=False,
                    metrics={},
                    validation_passed=False,
                    payout=0,
                    refund=0,
                    max_price=max_price_int,
                    receipt_hash="",
                    tx_hash=None,
                    seller_response={},
                    invariant_checks=[],
                    error=f"Paid request failed: {resp.status_code} {resp.text[:200]}",
                )

            data = resp.json()

        # Parse response
        request_id = data.get("request_id", "")
        metrics = data.get("metrics", {})
        validation_passed = data.get("validation_passed", False)
        payout = int(data.get("payout", "0"))
        refund = int(data.get("refund", "0"))
        receipt_hash = data.get("receipt_hash", "")
        tx_hash = data.get("tx_hash")
        seller_response = data.get("seller_response", {})

        # Step 3: Verify invariants (fail-closed)
        checks = self._check_invariants(
            payout=payout,
            refund=refund,
            max_price=max_price_int,
            validation_passed=validation_passed,
            mode=mode,
        )

        violations = [c for c in checks if not c["passed"]]

        result = BuyerResult(
            request_id=request_id,
            mode=mode,
            success=len(violations) == 0,
            metrics=metrics,
            validation_passed=validation_passed,
            payout=payout,
            refund=refund,
            max_price=max_price_int,
            receipt_hash=receipt_hash,
            tx_hash=tx_hash,
            seller_response=seller_response,
            invariant_checks=checks,
            error=f"Invariant violations: {violations}" if violations else None,
        )

        if violations:
            raise InvariantViolation(
                f"Receipt for {request_id} failed {len(violations)} invariant(s): {violations}"
            )

        return result

    def _check_invariants(
        self,
        *,
        payout: int,
        refund: int,
        max_price: int,
        validation_passed: bool,
        mode: str,
    ) -> list[dict[str, Any]]:
        """Verify receipt invariants. Returns list of check results."""
        checks = []

        # I1: payout <= max_price
        checks.append({
            "name": "payout_le_max_price",
            "passed": payout <= max_price,
            "detail": f"payout={payout} <= max_price={max_price}",
        })

        # I2: refund = max_price - payout
        expected_refund = max_price - payout
        checks.append({
            "name": "refund_correctness",
            "passed": refund == expected_refund,
            "detail": f"refund={refund} == max_price-payout={expected_refund}",
        })

        # I3: payout + refund = max_price
        checks.append({
            "name": "total_conservation",
            "passed": (payout + refund) == max_price,
            "detail": f"payout+refund={payout + refund} == max_price={max_price}",
        })

        # I4: invalid mode should have zero payout
        if mode == "invalid":
            checks.append({
                "name": "invalid_zero_payout",
                "passed": payout == 0,
                "detail": f"invalid mode: payout={payout} should be 0",
            })

        # I5: payout >= 0
        checks.append({
            "name": "payout_non_negative",
            "passed": payout >= 0,
            "detail": f"payout={payout} >= 0",
        })

        # I6: refund >= 0
        checks.append({
            "name": "refund_non_negative",
            "passed": refund >= 0,
            "detail": f"refund={refund} >= 0",
        })

        return checks
