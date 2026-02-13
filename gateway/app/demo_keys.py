"""Single-secret demo mode — derive role keys from one env var.

Supports two modes:
- DEMO_SECRET_MODE=private_key  →  All roles share one EOA (simplest)
- DEMO_SECRET_MODE=mnemonic     →  BIP-44 derivation per role (recommended)

Role derivation paths (mnemonic mode):
    buyer:    m/44'/60'/0'/0/0
    seller:   m/44'/60'/0'/0/1
    gateway:  m/44'/60'/0'/0/2
    resolver: m/44'/60'/0'/0/3

Usage:
    from gateway.app.demo_keys import get_demo_keys

    keys = get_demo_keys()
    if keys:
        print(keys["buyer_private_key"], keys["buyer_address"])

WARNING: This module is for HACKATHON DEMO ONLY.
         Never use production keys with this system.
"""

from __future__ import annotations

import logging
import os

from eth_account import Account

logger = logging.getLogger("sla-gateway.demo-keys")

# BIP-44 derivation indices per role
ROLE_INDICES = {
    "buyer": 0,
    "seller": 1,
    "gateway": 2,
    "resolver": 3,
}

ROLES = list(ROLE_INDICES.keys())


def _derive_from_private_key(private_key: str) -> dict[str, str]:
    """All roles share the same private key and address."""
    acct = Account.from_key(private_key)
    result = {}
    for role in ROLES:
        result[f"{role}_private_key"] = private_key
        result[f"{role}_address"] = acct.address
    return result


def _derive_from_mnemonic(mnemonic: str) -> dict[str, str]:
    """Derive role-specific keys from a BIP-44 mnemonic."""
    Account.enable_unaudited_hdwallet_features()
    result = {}
    for role, idx in ROLE_INDICES.items():
        path = f"m/44'/60'/0'/0/{idx}"
        acct = Account.from_mnemonic(mnemonic, account_path=path)
        result[f"{role}_private_key"] = "0x" + acct.key.hex()
        result[f"{role}_address"] = acct.address
    return result


def get_demo_keys() -> dict[str, str] | None:
    """Read DEMO_* env vars and derive role keys.

    Returns:
        Dict with keys like buyer_private_key, buyer_address, etc.
        None if no demo secret is configured.
    """
    mode = os.getenv("DEMO_SECRET_MODE", "").lower()
    private_key = os.getenv("DEMO_PRIVATE_KEY", "")
    mnemonic = os.getenv("DEMO_MNEMONIC", "")

    # Auto-detect mode if not explicitly set
    if not mode:
        if mnemonic:
            mode = "mnemonic"
        elif private_key:
            mode = "private_key"
        else:
            return None

    if mode == "private_key":
        if not private_key:
            logger.warning("DEMO_SECRET_MODE=private_key but DEMO_PRIVATE_KEY not set")
            return None
        logger.warning(
            "DEMO MODE: All roles share one key. "
            "For hackathon demo only — never use production keys!"
        )
        return _derive_from_private_key(private_key)

    if mode == "mnemonic":
        if not mnemonic:
            logger.warning("DEMO_SECRET_MODE=mnemonic but DEMO_MNEMONIC not set")
            return None
        logger.warning(
            "DEMO MODE: Deriving role keys from mnemonic. "
            "For hackathon demo only — never use production keys!"
        )
        return _derive_from_mnemonic(mnemonic)

    logger.warning("Unknown DEMO_SECRET_MODE=%s", mode)
    return None


def inject_demo_env() -> bool:
    """Inject demo-derived keys into os.environ (lower priority than explicit vars).

    Returns True if demo keys were injected.
    """
    keys = get_demo_keys()
    if keys is None:
        return False

    env_mapping = {
        "buyer_private_key": "BUYER_PRIVATE_KEY",
        "buyer_address": "BUYER_ADDRESS",
        "seller_private_key": "SELLER_PRIVATE_KEY",
        "seller_address": "SELLER_ADDRESS",
        "gateway_private_key": "GATEWAY_PRIVATE_KEY",
        "gateway_address": "GATEWAY_ADDRESS",
        "resolver_private_key": "RESOLVER_PRIVATE_KEY",
        "resolver_address": "RESOLVER_ADDRESS",
    }

    injected = []
    for key_name, env_name in env_mapping.items():
        if key_name in keys:
            # Explicit env takes precedence
            if not os.getenv(env_name):
                os.environ[env_name] = keys[key_name]
                injected.append(env_name)

    if injected:
        logger.info("Demo keys injected: %s", ", ".join(injected))

    return True
