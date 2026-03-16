"""Buyer agent HTTP client — handles deposit-first request and receipt verification.

This module encapsulates the autonomous buyer's interaction with the SLAgent-402 gateway:
1. Discover seller capabilities
2. Negotiate mandate (construct + submit for seller acceptance)
3. Submit deposit() when chain settlement is configured
4. Call the gateway with request_id + optional deposit tx hash
5. Receive response with receipt
6. Verify receipt invariants (fail-closed)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from eth_account import Account
from web3 import Web3

from gateway.app.hashing import compute_mandate_id
from gateway.app.x402 import create_payment_token, create_x402_payment

logger = logging.getLogger("buyer-agent")

# Default mandate template matching PROJECT.md
DEFAULT_MANDATE_TEMPLATE: dict[str, Any] = {
    "version": "1.0",
    "max_price": "100000",
    "base_pay": "60000",
    "bonus_rules": {
        "type": "latency_tiers",
        "tiers": [
            {"lte_ms": 2000, "payout": "100000"},
            {"lte_ms": 5000, "payout": "80000"},
            {"lte_ms": 999999999, "payout": "60000"},
        ],
    },
    "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
    "timeout_ms": 8000,
    "dispute": {"window_seconds": 600, "bond_amount": "50000"},
}


@dataclass
class NegotiationResult:
    """Result of the negotiation phase."""

    seller_capabilities: dict[str, Any]
    mandate: dict[str, Any]
    mandate_id: str
    seller_accepted: bool
    summary: str


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
    deposit_tx_hash: str | None = None
    settle_tx_hash: str | None = None
    llm_policy: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attestation_status: dict[str, Any] = field(default_factory=dict)


class InvariantViolation(Exception):
    """Raised when a receipt invariant check fails (fail-closed)."""


class BuyerAgent:
    """Autonomous buyer agent that interacts with SLAgent-402 gateway."""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        seller_url: str = "http://localhost:8001",
        buyer_address: str = "0x1111111111111111111111111111111111111111",
        max_price: str = "100000",
        timeout: float = 30.0,
        buyer_private_key: str | None = None,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.seller_url = seller_url.rstrip("/")
        self.buyer_address = buyer_address
        self.buyer_private_key = buyer_private_key
        self.max_price = max_price
        self.timeout = timeout
        self.negotiation: NegotiationResult | None = None
        self._buyer_w3: Web3 | None = None
        self._buyer_account: Any | None = None
        self._last_nonce: int | None = None

    async def discover_seller(self) -> dict[str, Any]:
        """Discover seller capabilities via GET /seller/capabilities."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.seller_url}/seller/capabilities")
            if resp.status_code != 200:
                raise RuntimeError(f"Seller capabilities unavailable: {resp.status_code}")
            return resp.json()

    async def negotiate_mandate(
        self,
        seller_capabilities: dict[str, Any] | None = None,
        scenario_tag: str = "",
    ) -> NegotiationResult:
        """Negotiate a mandate: build from template, submit to seller for acceptance.

        1. Discover seller capabilities (if not provided)
        2. Construct mandate from buyer's template + seller info
        3. Submit to seller POST /seller/mandates/accept
        4. Return negotiation result
        """
        if seller_capabilities is None:
            seller_capabilities = await self.discover_seller()

        seller_address = seller_capabilities.get("seller_address", "")
        supported_schemas = seller_capabilities.get("supported_schemas", [])

        # Build mandate from template
        mandate = {**DEFAULT_MANDATE_TEMPLATE}
        mandate["buyer"] = self.buyer_address
        mandate["seller"] = seller_address
        mandate["max_price"] = self.max_price

        # Optional: ask gateway LLM policy for SLA/price negotiation suggestion.
        # This is fail-open; if unavailable we keep the original buyer mandate.
        if os.getenv("LLM_NEGOTIATION_ENABLED", "false").lower() in ("1", "true", "yes", "on"):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    sugg = await client.post(
                        f"{self.gateway_url}/v1/negotiation/suggest",
                        json={
                            "mandate": mandate,
                            "seller_capabilities": seller_capabilities,
                            "scenario_tag": scenario_tag,
                        },
                    )
                if sugg.status_code == 200:
                    data = sugg.json()
                    terms = data.get("suggested_terms", {})
                    if isinstance(terms, dict):
                        if "max_price" in terms:
                            mandate["max_price"] = str(terms["max_price"])
                            self.max_price = str(terms["max_price"])
                        if "base_pay" in terms:
                            mandate["base_pay"] = str(terms["base_pay"])
                        if isinstance(terms.get("bonus_rules"), dict):
                            mandate["bonus_rules"] = terms["bonus_rules"]
            except Exception as e:
                logger.info("LLM negotiation suggestion skipped: %s", e)

        # Verify seller supports required schema
        required_schemas = {v["schema_id"] for v in mandate.get("validators", []) if "schema_id" in v}
        if not required_schemas.issubset(set(supported_schemas)):
            missing = required_schemas - set(supported_schemas)
            raise RuntimeError(f"Seller does not support required schemas: {missing}")

        # Compute mandate ID
        mandate_id = compute_mandate_id(mandate)
        mandate["mandate_id"] = mandate_id

        # Submit to seller for acceptance
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.seller_url}/seller/mandates/accept",
                json=mandate,
            )

        accepted = False
        if resp.status_code == 200:
            accept_data = resp.json()
            accepted = accept_data.get("accepted", False)

        summary = (
            f"Negotiation complete. "
            f"Seller={seller_address}, LLM={seller_capabilities.get('llm_model', 'unknown')}. "
            f"Mandate max_price={mandate['max_price']}, schemas={list(required_schemas)}. "
            f"Seller accepted={accepted}."
        )

        self.negotiation = NegotiationResult(
            seller_capabilities=seller_capabilities,
            mandate=mandate,
            mandate_id=mandate_id,
            seller_accepted=accepted,
            summary=summary,
        )

        logger.info("Negotiation: %s", summary)
        return self.negotiation

    def _make_payment_header(self, path: str = "/v1/call") -> dict[str, str]:
        """Create payment header based on PAYMENT_MODE."""
        payment_mode = os.getenv("PAYMENT_MODE", "hmac")

        if payment_mode == "x402":
            if not self.buyer_private_key:
                raise RuntimeError("PAYMENT_MODE=x402 requires BUYER_PRIVATE_KEY")

            chain_id = int(os.getenv("CHAIN_ID", "11155111"))
            asset = os.getenv("PAYMENT_TOKEN_ADDRESS", "")
            if not asset:
                raise RuntimeError("PAYMENT_MODE=x402 requires PAYMENT_TOKEN_ADDRESS")
            token_name = os.getenv("SLA_TOKEN_NAME", "Tether USD")
            token_version = os.getenv("SLA_TOKEN_VERSION", "")
            # payTo should match seller EVM address used by gateway challenge payload
            to_address = (
                os.getenv("SELLER_ADDRESS", "")
                or (self.negotiation.mandate.get("seller", "") if self.negotiation else "")
                or "0x" + "2" * 40
            )

            header_val = create_x402_payment(
                private_key=self.buyer_private_key,
                from_address=self.buyer_address,
                to_address=to_address,
                value=self.max_price,
                asset=asset,
                chain_id=chain_id,
                token_name=token_name,
                token_version=token_version,
            )
            return {"X-PAYMENT": header_val}

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

    def _make_request_id(self, mode: str) -> str:
        ts_ms = int(time.time() * 1000)
        return f"req_{mode}_{ts_ms}_{uuid.uuid4().hex[:8]}"

    def _init_buyer_chain(self) -> bool:
        rpc_url = os.getenv("CHAIN_RPC_URL", "")
        settlement = os.getenv("SETTLEMENT_CONTRACT_ADDRESS", "")
        if not all([rpc_url, settlement, self.buyer_private_key]):
            return False

        if self._buyer_w3 is None:
            self._buyer_w3 = Web3(Web3.HTTPProvider(rpc_url))
        if self._buyer_account is None:
            self._buyer_account = Account.from_key(self.buyer_private_key)
        return True

    def _next_buyer_nonce(self) -> int:
        if not self._buyer_w3 or not self._buyer_account:
            raise RuntimeError("buyer chain client not initialized")

        chain_nonce = self._buyer_w3.eth.get_transaction_count(self._buyer_account.address, "pending")
        if self._last_nonce is None:
            nonce = chain_nonce
        else:
            nonce = max(chain_nonce, self._last_nonce + 1)
        self._last_nonce = nonce
        return nonce

    def _submit_buyer_deposit(self, request_id: str, amount: int) -> str | None:
        """Submit buyer-funded deposit tx before the gateway call."""
        if not self._init_buyer_chain():
            return None

        assert self._buyer_w3 is not None
        assert self._buyer_account is not None

        settlement_addr = os.getenv("SETTLEMENT_CONTRACT_ADDRESS", "")
        if not settlement_addr:
            return None

        abi = [{
            "inputs": [
                {"name": "requestId", "type": "bytes32"},
                {"name": "buyer", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "deposit",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        }]

        request_id_bytes = Web3.keccak(text=request_id)
        contract = self._buyer_w3.eth.contract(
            address=Web3.to_checksum_address(settlement_addr),
            abi=abi,
        )

        chain_id = int(os.getenv("CHAIN_ID", str(self._buyer_w3.eth.chain_id)))
        tx = contract.functions.deposit(
            request_id_bytes,
            Web3.to_checksum_address(self.buyer_address),
            amount,
        ).build_transaction({
            "chainId": chain_id,
            "from": self._buyer_account.address,
            "nonce": self._next_buyer_nonce(),
            "gas": 220_000,
            # Use legacy gas fields for SKALE compatibility.
            "gasPrice": self._buyer_w3.eth.gas_price,
        })

        signed = self._buyer_w3.eth.account.sign_transaction(tx, self.buyer_private_key)
        tx_hash = self._buyer_w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self._buyer_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if int(receipt.status) != 1:
            raise RuntimeError(f"buyer deposit tx failed: {tx_hash.hex()}")
        return tx_hash.hex()

    async def call(
        self,
        mode: str = "fast",
        delay_ms: int = 0,
        scenario_tag: str = "",
    ) -> BuyerResult:
        """Execute the full buyer flow: deposit (optional) → call → verify.

        Args:
            mode: Seller mode (fast, slow, invalid, error, timeout)
            delay_ms: Additional delay in ms applied by seller (simulator control)

        Returns:
            BuyerResult with all details.

        Raises:
            InvariantViolation: If receipt invariants fail (fail-closed behavior).
        """
        max_price_int = int(self.max_price)
        request_id_hint = self._make_request_id(mode)
        call_body: dict = {
            "mode": mode,
            "request_id": request_id_hint,
            "buyer": self.buyer_address,
        }
        if delay_ms > 0:
            call_body["delay_ms"] = delay_ms
        if scenario_tag:
            call_body["scenario_tag"] = scenario_tag

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Step 1: Buyer-funded on-chain deposit (if chain env is configured)
            try:
                deposit_tx_hash = self._submit_buyer_deposit(request_id_hint, max_price_int)
            except Exception as e:
                return BuyerResult(
                    request_id=request_id_hint,
                    mode=mode,
                    success=False,
                    metrics={},
                    validation_passed=False,
                    payout=0,
                    refund=0,
                    max_price=max_price_int,
                    receipt_hash="",
                    tx_hash=None,
                    deposit_tx_hash=None,
                    settle_tx_hash=None,
                    seller_response={},
                    invariant_checks=[],
                    error=f"Buyer deposit failed: {e}",
                )

            # Step 2: Gateway call (deposit-backed when tx hash is present)
            headers: dict[str, str] = {}
            if deposit_tx_hash:
                headers["X-DEPOSIT-TX-HASH"] = deposit_tx_hash
                call_body["deposit_tx_hash"] = deposit_tx_hash
            query_params = f"mode={mode}"
            if delay_ms > 0:
                query_params += f"&delay_ms={delay_ms}"
            resp = await client.post(
                f"{self.gateway_url}/v1/call?{query_params}",
                json=call_body,
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
                    deposit_tx_hash=deposit_tx_hash,
                    settle_tx_hash=None,
                    seller_response={},
                    invariant_checks=[],
                    error=f"Gateway request failed: {resp.status_code} {resp.text[:200]}",
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
        deposit_tx_hash = data.get("deposit_tx_hash") or deposit_tx_hash
        settle_tx_hash = data.get("settle_tx_hash")
        llm_policy = data.get("llm_policy", {})
        if not isinstance(llm_policy, dict):
            llm_policy = {}
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
            deposit_tx_hash=deposit_tx_hash,
            settle_tx_hash=settle_tx_hash,
            llm_policy=llm_policy,
            seller_response=seller_response,
            invariant_checks=checks,
            error=f"Invariant violations: {violations}" if violations else None,
        )

        if violations:
            raise InvariantViolation(
                f"Receipt for {request_id} failed {len(violations)} invariant(s): {violations}"
            )

        # Auto-submit attestations if buyer has a signing key
        if self.buyer_private_key and receipt_hash and request_id:
            try:
                attest_result = await self.submit_attestations(request_id, receipt_hash)
                result.attestation_status = attest_result
            except Exception as e:
                logger.warning("Attestation submission failed: %s", e)
                result.attestation_status = {"error": str(e)}

        return result

    async def submit_attestations(
        self,
        request_id: str,
        receipt_hash: str,
    ) -> dict[str, Any]:
        """Submit buyer + seller attestations for a receipt.

        1. Signs receipt_hash with buyer key -> submits to gateway as buyer
        2. Requests seller signature -> submits to gateway as seller
        3. Returns final attestation status
        """
        results: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Buyer attestation
            if self.buyer_private_key:
                try:
                    from gateway.app.attestation import sign_receipt_hash

                    buyer_sig = sign_receipt_hash(receipt_hash, self.buyer_private_key)
                    resp = await client.post(
                        f"{self.gateway_url}/v1/receipts/{request_id}/attest",
                        json={
                            "role": "buyer",
                            "signature": buyer_sig,
                            "address": self.buyer_address,
                        },
                    )
                    results["buyer"] = resp.json() if resp.status_code == 200 else {
                        "error": resp.text
                    }
                except Exception as e:
                    logger.warning("Buyer attestation failed: %s", e)
                    results["buyer"] = {"error": str(e)}

            # 2. Seller attestation (request signature from seller, then submit to gateway)
            try:
                resp = await client.post(
                    f"{self.seller_url}/seller/receipts/attest",
                    json={"receipt_hash": receipt_hash},
                )
                if resp.status_code == 200:
                    seller_data = resp.json()
                    resp2 = await client.post(
                        f"{self.gateway_url}/v1/receipts/{request_id}/attest",
                        json={
                            "role": "seller",
                            "signature": seller_data["signature"],
                            "address": seller_data.get("seller_address"),
                        },
                    )
                    results["seller"] = resp2.json() if resp2.status_code == 200 else {
                        "error": resp2.text
                    }
                else:
                    results["seller"] = {"error": f"Seller attest returned {resp.status_code}"}
            except Exception as e:
                logger.warning("Seller attestation failed: %s", e)
                results["seller"] = {"error": str(e)}

            # 3. Get final attestation status
            try:
                resp = await client.get(
                    f"{self.gateway_url}/v1/receipts/{request_id}/attestations",
                )
                if resp.status_code == 200:
                    results["status"] = resp.json()
            except Exception:
                pass

        return results

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
