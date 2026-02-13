"""AP2 Authorization store — tracks intent → authorization → settlement state.

Enforces the AP2 pattern:
  intent.create → intent.authorize → settlement.execute → receipt.issue

State transitions:
  CREATED → AUTHORIZED → SETTLED → RECEIPT_ISSUED
  CREATED → REJECTED (terminal)
  AUTHORIZED → EXPIRED (terminal, if past expires_at)
  AUTHORIZED → REVOKED (terminal)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


class AuthorizationError(Exception):
    """Raised when an authorization state transition is invalid."""


@dataclass
class Intent:
    """An AP2 intent — a proposal for settlement."""

    intent_id: str
    mandate_id: str
    buyer: str
    seller: str
    max_price: str
    status: str = "CREATED"  # CREATED | AUTHORIZED | SETTLED | RECEIPT_ISSUED | REJECTED
    created_at: float = field(default_factory=time.time)
    created_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Authorization:
    """An AP2 authorization — grants permission to execute settlement."""

    authorization_id: str
    intent_id: str
    authorizer: str  # who authorized (buyer address or agent id)
    policy_id: str  # mandate_id or policy reference
    status: str = "ACTIVE"  # ACTIVE | EXPIRED | REJECTED | REVOKED | CONSUMED
    expires_at: float = 0.0  # epoch seconds; 0 = no expiry
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        return self.status == "ACTIVE" and not self.is_expired()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_expired"] = self.is_expired()
        d["is_valid"] = self.is_valid()
        return d


class AuthorizationStore:
    """In-memory store for AP2 intents and authorizations."""

    def __init__(self) -> None:
        self._intents: dict[str, Intent] = {}
        self._authorizations: dict[str, Authorization] = {}
        # Index: intent_id → authorization_id
        self._intent_to_auth: dict[str, str] = {}

    # ── Intent lifecycle ──────────────────────────────────────────────────

    def create_intent(
        self,
        *,
        mandate_id: str,
        buyer: str,
        seller: str,
        max_price: str,
        created_by: str = "",
    ) -> Intent:
        """Create a new intent (CREATED state)."""
        intent_id = f"intent_{uuid.uuid4().hex[:12]}"
        intent = Intent(
            intent_id=intent_id,
            mandate_id=mandate_id,
            buyer=buyer,
            seller=seller,
            max_price=max_price,
            created_by=created_by,
        )
        self._intents[intent_id] = intent
        return intent

    def get_intent(self, intent_id: str) -> Intent | None:
        return self._intents.get(intent_id)

    # ── Authorization lifecycle ───────────────────────────────────────────

    def authorize_intent(
        self,
        *,
        intent_id: str,
        authorizer: str,
        policy_id: str = "",
        expires_at: float = 0.0,
    ) -> Authorization:
        """Authorize an intent. Intent must be in CREATED state."""
        intent = self._intents.get(intent_id)
        if intent is None:
            raise AuthorizationError(f"Intent not found: {intent_id}")
        if intent.status != "CREATED":
            raise AuthorizationError(
                f"Intent {intent_id} is in state {intent.status}, expected CREATED"
            )

        authorization_id = f"auth_{uuid.uuid4().hex[:12]}"
        auth = Authorization(
            authorization_id=authorization_id,
            intent_id=intent_id,
            authorizer=authorizer,
            policy_id=policy_id or intent.mandate_id,
            expires_at=expires_at,
        )

        intent.status = "AUTHORIZED"
        self._authorizations[authorization_id] = auth
        self._intent_to_auth[intent_id] = authorization_id
        return auth

    def reject_intent(self, intent_id: str, reason: str = "") -> Intent:
        """Reject an intent. Terminal state."""
        intent = self._intents.get(intent_id)
        if intent is None:
            raise AuthorizationError(f"Intent not found: {intent_id}")
        if intent.status != "CREATED":
            raise AuthorizationError(
                f"Intent {intent_id} is in state {intent.status}, expected CREATED"
            )
        intent.status = "REJECTED"
        return intent

    def get_authorization(self, authorization_id: str) -> Authorization | None:
        return self._authorizations.get(authorization_id)

    def get_authorization_for_intent(self, intent_id: str) -> Authorization | None:
        auth_id = self._intent_to_auth.get(intent_id)
        if auth_id:
            return self._authorizations.get(auth_id)
        return None

    # ── Settlement gate ───────────────────────────────────────────────────

    def validate_for_settlement(
        self, intent_id: str, authorization_id: str
    ) -> tuple[bool, str]:
        """Check if settlement can proceed. Returns (ok, reason)."""
        intent = self._intents.get(intent_id)
        if intent is None:
            return False, f"Intent not found: {intent_id}"

        if intent.status != "AUTHORIZED":
            return False, f"Intent {intent_id} is {intent.status}, expected AUTHORIZED"

        auth = self._authorizations.get(authorization_id)
        if auth is None:
            return False, f"Authorization not found: {authorization_id}"

        if auth.intent_id != intent_id:
            return False, f"Authorization {authorization_id} does not match intent {intent_id}"

        if auth.is_expired():
            auth.status = "EXPIRED"
            return False, f"Authorization {authorization_id} has expired"

        if auth.status != "ACTIVE":
            return False, f"Authorization {authorization_id} is {auth.status}, expected ACTIVE"

        return True, "OK"

    def mark_settled(self, intent_id: str, authorization_id: str) -> None:
        """Mark intent as settled and authorization as consumed."""
        intent = self._intents.get(intent_id)
        if intent:
            intent.status = "SETTLED"
        auth = self._authorizations.get(authorization_id)
        if auth:
            auth.status = "CONSUMED"

    def mark_receipt_issued(self, intent_id: str) -> None:
        """Mark intent as receipt issued (final state)."""
        intent = self._intents.get(intent_id)
        if intent:
            intent.status = "RECEIPT_ISSUED"

    # ── Query ─────────────────────────────────────────────────────────────

    def list_intents(self, limit: int = 50) -> list[Intent]:
        return sorted(
            self._intents.values(),
            key=lambda i: i.created_at,
            reverse=True,
        )[:limit]

    def list_authorizations(self, limit: int = 50) -> list[Authorization]:
        return sorted(
            self._authorizations.values(),
            key=lambda a: a.created_at,
            reverse=True,
        )[:limit]

    def clear(self) -> None:
        self._intents.clear()
        self._authorizations.clear()
        self._intent_to_auth.clear()


# Singleton
auth_store = AuthorizationStore()
