"""Helpers for applying named chain/network profiles to environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping

DEFAULT_SEPOLIA_RPC_URL = "https://rpc.sepolia.org"
DEFAULT_SEPOLIA_EXPLORER_URL = "https://sepolia.etherscan.io"


def resolve_network_profile(
    network: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Resolve a network profile without mutating process environment."""
    env = environ or os.environ
    normalized = network.strip().lower()

    if normalized != "sepolia":
        raise ValueError(f"Unsupported network profile: {network}")

    chain_rpc_url = (
        env.get("SEPOLIA_RPC_URL")
        or env.get("CHAIN_RPC_URL")
        or DEFAULT_SEPOLIA_RPC_URL
    )
    payment_token = (
        env.get("SEPOLIA_PAYMENT_TOKEN_ADDRESS")
        or env.get("PAYMENT_TOKEN_ADDRESS", "")
    )
    settlement_contract = (
        env.get("SEPOLIA_SETTLEMENT_CONTRACT_ADDRESS")
        or env.get("SETTLEMENT_CONTRACT_ADDRESS", "")
    )

    return {
        "CHAIN_ID": "11155111",
        "CHAIN_RPC_URL": chain_rpc_url,
        "EXPLORER_URL": (
            env.get("SEPOLIA_EXPLORER_URL")
            or env.get("EXPLORER_URL")
            or DEFAULT_SEPOLIA_EXPLORER_URL
        ),
        "WDK_CHAIN_NAME": "ethereum",
        "WDK_EVM_RPC_URL": (
            env.get("SEPOLIA_WDK_RPC_URL")
            or chain_rpc_url
        ),
        "PAYMENT_TOKEN_ADDRESS": payment_token,
        "SETTLEMENT_CONTRACT_ADDRESS": settlement_contract,
        "WDK_USDT_ADDRESS": (
            env.get("SEPOLIA_WDK_USDT_ADDRESS")
            or payment_token
            or env.get("WDK_USDT_ADDRESS", "")
        ),
        "WDK_SETTLEMENT_ADDRESS": (
            env.get("SEPOLIA_WDK_SETTLEMENT_ADDRESS")
            or settlement_contract
            or env.get("WDK_SETTLEMENT_ADDRESS", "")
        ),
    }


def apply_network_profile(
    network: str,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Apply a named network profile to the target environment mapping."""
    target_env = environ or os.environ
    profile = resolve_network_profile(network, target_env)
    for key, value in profile.items():
        target_env[key] = value
    return profile
