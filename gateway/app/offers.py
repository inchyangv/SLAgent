"""SLA Offer Catalog — predefined offer presets for demo negotiation."""

from __future__ import annotations

OFFERS: list[dict] = [
    {
        "offer_id": "offer_bronze_v1",
        "name": "Bronze",
        "description": "Budget tier — relaxed latency SLA, lower max price",
        "max_price": "50000",
        "base_pay": "30000",
        "bonus_rules": {
            "type": "latency_tiers",
            "tiers": [
                {"lte_ms": 5000, "payout": "50000"},
                {"lte_ms": 10000, "payout": "40000"},
                {"lte_ms": 999999999, "payout": "30000"},
            ],
        },
        "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
        "timeout_ms": 15000,
        "dispute": {"window_seconds": 600, "bond_amount": "25000"},
    },
    {
        "offer_id": "offer_silver_v1",
        "name": "Silver",
        "description": "Standard tier — balanced SLA, matches PROJECT.md example",
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
    },
    {
        "offer_id": "offer_gold_v1",
        "name": "Gold",
        "description": "Premium tier — tight latency SLA, highest payout for speed",
        "max_price": "200000",
        "base_pay": "100000",
        "bonus_rules": {
            "type": "latency_tiers",
            "tiers": [
                {"lte_ms": 1000, "payout": "200000"},
                {"lte_ms": 2000, "payout": "160000"},
                {"lte_ms": 5000, "payout": "120000"},
                {"lte_ms": 999999999, "payout": "100000"},
            ],
        },
        "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
        "timeout_ms": 5000,
        "dispute": {"window_seconds": 600, "bond_amount": "100000"},
    },
]


def get_offers() -> list[dict]:
    """Return all available SLA offer presets."""
    return OFFERS


def get_offer(offer_id: str) -> dict | None:
    """Return a specific offer by ID."""
    for offer in OFFERS:
        if offer["offer_id"] == offer_id:
            return offer
    return None
