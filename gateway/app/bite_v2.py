"""BITE v2 Encrypted Conditional Settlement — privacy + trigger.

Demonstrates encrypted conditions/pricing/policy that are revealed and settled
only when conditions are met. Shows why privacy matters in agent commerce.

Encrypted fields: max_price, latency_tiers, buyer_policy, tool_choice
Condition: SLA validation pass + budget/policy satisfied
On failure: no decrypt, no settlement, reason code logged

Lifecycle:
  1. ENCRYPT — sender encrypts sensitive settlement terms
  2. CONDITION_CHECK — gateway evaluates SLA/policy conditions
  3. DECRYPT (if pass) — reveal terms and proceed to settlement
  4. SETTLE (if pass) — execute settlement with revealed terms
  5. NO_DECRYPT (if fail) — keep encrypted, log reason, no settlement

For hackathon demo: uses AES-GCM via Fernet-like wrapper.
Production: would integrate with BITE v2 SDK for on-chain encryption.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("bite-v2")

# Use a simple symmetric encryption for demo (AES-GCM via cryptography or
# fallback to XOR-based obfuscation if cryptography is not available).
try:
    from cryptography.fernet import Fernet

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a secret string."""
    raw = hashlib.sha256(secret.encode()).digest()
    return b64encode(raw)


def _encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt plaintext and return base64-encoded ciphertext."""
    if _HAS_CRYPTO:
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    # Fallback: base64 encode (NOT secure, demo only)
    return b64encode(plaintext.encode()).decode()


def _decrypt(ciphertext: str, key: bytes) -> str:
    """Decrypt base64-encoded ciphertext."""
    if _HAS_CRYPTO:
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    # Fallback: base64 decode
    return b64decode(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class EncryptedPayload:
    """An encrypted settlement payload with condition metadata."""

    payload_id: str
    encrypted_data: str  # base64-encoded encrypted JSON
    encrypted_hash: str  # SHA-256 of encrypted_data (for audit)
    encrypted_fields: list[str]  # which fields are encrypted
    condition_type: str  # "sla_validation" | "budget_policy" | "composite"
    condition_params: dict[str, Any]  # condition evaluation parameters
    status: str = "ENCRYPTED"  # ENCRYPTED | DECRYPTED | SETTLED | CONDITION_FAILED
    created_at: float = field(default_factory=time.time)
    decrypted_at: float | None = None
    settled_at: float | None = None
    condition_result: dict[str, Any] = field(default_factory=dict)
    triggered_by: str = ""
    reason_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConditionResult:
    """Result of a condition evaluation."""

    passed: bool
    condition_type: str
    checks: list[dict[str, Any]]
    reason_code: str = ""
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------


def evaluate_sla_condition(
    *,
    validation_passed: bool,
    latency_ms: int,
    max_latency_ms: int = 8000,
    success: bool = True,
) -> ConditionResult:
    """Evaluate SLA validation condition for decrypt trigger."""
    checks = []

    checks.append({
        "name": "success",
        "passed": success,
        "detail": f"success={success}",
    })

    checks.append({
        "name": "schema_validation",
        "passed": validation_passed,
        "detail": f"validation_passed={validation_passed}",
    })

    checks.append({
        "name": "latency_within_sla",
        "passed": latency_ms <= max_latency_ms,
        "detail": f"latency={latency_ms}ms <= max={max_latency_ms}ms",
    })

    all_passed = all(c["passed"] for c in checks)
    reason = "" if all_passed else next(
        (c["name"] for c in checks if not c["passed"]), "UNKNOWN"
    )

    return ConditionResult(
        passed=all_passed,
        condition_type="sla_validation",
        checks=checks,
        reason_code=f"CONDITION_FAILED:{reason}" if not all_passed else "",
    )


def evaluate_budget_condition(
    *,
    price: int,
    budget_remaining: int,
    max_step_price: int = 0,
) -> ConditionResult:
    """Evaluate budget/policy condition for decrypt trigger."""
    checks = []

    checks.append({
        "name": "within_budget",
        "passed": price <= budget_remaining,
        "detail": f"price={price} <= budget={budget_remaining}",
    })

    if max_step_price > 0:
        checks.append({
            "name": "within_step_limit",
            "passed": price <= max_step_price,
            "detail": f"price={price} <= max_step={max_step_price}",
        })

    all_passed = all(c["passed"] for c in checks)
    reason = "" if all_passed else next(
        (c["name"] for c in checks if not c["passed"]), "UNKNOWN"
    )

    return ConditionResult(
        passed=all_passed,
        condition_type="budget_policy",
        checks=checks,
        reason_code=f"CONDITION_FAILED:{reason}" if not all_passed else "",
    )


# ---------------------------------------------------------------------------
# BITE v2 Engine
# ---------------------------------------------------------------------------


class BiteV2Engine:
    """BITE v2 encrypted conditional settlement engine.

    Manages the lifecycle: encrypt → condition check → decrypt/settle or reject.
    """

    def __init__(self, secret: str | None = None) -> None:
        self._secret = secret or os.getenv("BITE_V2_SECRET", "bite-v2-demo-secret")
        self._key = _derive_key(self._secret)
        self._payloads: dict[str, EncryptedPayload] = {}

    def encrypt_terms(
        self,
        *,
        terms: dict[str, Any],
        encrypted_fields: list[str] | None = None,
        condition_type: str = "sla_validation",
        condition_params: dict[str, Any] | None = None,
    ) -> EncryptedPayload:
        """Encrypt sensitive settlement terms.

        Args:
            terms: Full settlement terms (max_price, latency_tiers, etc.)
            encrypted_fields: Which keys to encrypt (default: all sensitive ones)
            condition_type: What condition triggers decryption
            condition_params: Parameters for condition evaluation

        Returns:
            EncryptedPayload with encrypted data and metadata.
        """
        if encrypted_fields is None:
            encrypted_fields = ["max_price", "latency_tiers", "buyer_policy", "tool_choice"]

        # Extract and encrypt only the specified fields
        sensitive = {k: v for k, v in terms.items() if k in encrypted_fields}
        plaintext = json.dumps(sensitive, sort_keys=True)
        encrypted_data = _encrypt(plaintext, self._key)
        encrypted_hash = hashlib.sha256(encrypted_data.encode()).hexdigest()

        payload_id = f"bite_{uuid.uuid4().hex[:12]}"
        payload = EncryptedPayload(
            payload_id=payload_id,
            encrypted_data=encrypted_data,
            encrypted_hash=encrypted_hash,
            encrypted_fields=encrypted_fields,
            condition_type=condition_type,
            condition_params=condition_params or {},
        )

        self._payloads[payload_id] = payload

        logger.info(
            "BITE v2 encrypted: %s, fields=%s, hash=%s",
            payload_id,
            encrypted_fields,
            encrypted_hash[:16],
        )

        return payload

    def evaluate_and_decrypt(
        self,
        payload_id: str,
        condition_result: ConditionResult,
        triggered_by: str = "gateway",
    ) -> tuple[EncryptedPayload, dict[str, Any] | None]:
        """Evaluate condition and decrypt if passed.

        Args:
            payload_id: ID of the encrypted payload
            condition_result: Pre-evaluated condition result
            triggered_by: Who triggered the evaluation

        Returns:
            (updated_payload, decrypted_terms or None)
        """
        payload = self._payloads.get(payload_id)
        if payload is None:
            raise ValueError(f"Payload not found: {payload_id}")

        if payload.status != "ENCRYPTED":
            raise ValueError(f"Payload {payload_id} already processed: {payload.status}")

        payload.condition_result = condition_result.to_dict()
        payload.triggered_by = triggered_by

        if condition_result.passed:
            # Condition met → decrypt
            try:
                decrypted_json = _decrypt(payload.encrypted_data, self._key)
                decrypted_terms = json.loads(decrypted_json)
            except Exception as e:
                payload.status = "CONDITION_FAILED"
                payload.reason_code = f"DECRYPT_ERROR:{e}"
                logger.error("BITE v2 decrypt failed: %s — %s", payload_id, e)
                return payload, None

            payload.status = "DECRYPTED"
            payload.decrypted_at = time.time()

            logger.info(
                "BITE v2 decrypted: %s (condition passed, triggered_by=%s)",
                payload_id,
                triggered_by,
            )
            return payload, decrypted_terms
        else:
            # Condition failed → no decrypt
            payload.status = "CONDITION_FAILED"
            payload.reason_code = condition_result.reason_code

            logger.info(
                "BITE v2 NOT decrypted: %s (condition failed: %s)",
                payload_id,
                condition_result.reason_code,
            )
            return payload, None

    def mark_settled(self, payload_id: str) -> EncryptedPayload | None:
        """Mark payload as settled after successful settlement."""
        payload = self._payloads.get(payload_id)
        if payload and payload.status == "DECRYPTED":
            payload.status = "SETTLED"
            payload.settled_at = time.time()
            logger.info("BITE v2 settled: %s", payload_id)
        return payload

    def get_payload(self, payload_id: str) -> EncryptedPayload | None:
        return self._payloads.get(payload_id)

    def list_payloads(self, limit: int = 50) -> list[EncryptedPayload]:
        return sorted(
            self._payloads.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )[:limit]

    def clear(self) -> None:
        self._payloads.clear()


# Singleton
bite_engine = BiteV2Engine()
