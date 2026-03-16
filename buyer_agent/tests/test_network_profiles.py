"""Tests for named network profile helpers."""

from __future__ import annotations

from shared.network_profiles import apply_network_profile, resolve_network_profile


def test_resolve_sepolia_profile_uses_explicit_overrides():
    env = {
        "SEPOLIA_RPC_URL": "https://example-sepolia-rpc",
        "SEPOLIA_PAYMENT_TOKEN_ADDRESS": "0x1111",
        "SEPOLIA_SETTLEMENT_CONTRACT_ADDRESS": "0x2222",
        "SEPOLIA_WDK_USDT_ADDRESS": "0x3333",
        "SEPOLIA_WDK_SETTLEMENT_ADDRESS": "0x4444",
        "SEPOLIA_EXPLORER_URL": "https://explorer.example",
    }

    profile = resolve_network_profile("sepolia", env)

    assert profile["CHAIN_ID"] == "11155111"
    assert profile["CHAIN_RPC_URL"] == "https://example-sepolia-rpc"
    assert profile["PAYMENT_TOKEN_ADDRESS"] == "0x1111"
    assert profile["SETTLEMENT_CONTRACT_ADDRESS"] == "0x2222"
    assert profile["WDK_USDT_ADDRESS"] == "0x3333"
    assert profile["WDK_SETTLEMENT_ADDRESS"] == "0x4444"
    assert profile["EXPLORER_URL"] == "https://explorer.example"


def test_apply_sepolia_profile_falls_back_to_generic_addresses():
    env = {
        "CHAIN_RPC_URL": "https://generic-rpc",
        "PAYMENT_TOKEN_ADDRESS": "0xaaaa",
        "SETTLEMENT_CONTRACT_ADDRESS": "0xbbbb",
        "WDK_USDT_ADDRESS": "0xcccc",
        "WDK_SETTLEMENT_ADDRESS": "0xdddd",
    }

    profile = apply_network_profile("sepolia", env)

    assert env["CHAIN_ID"] == "11155111"
    assert profile["CHAIN_RPC_URL"] == "https://generic-rpc"
    assert profile["PAYMENT_TOKEN_ADDRESS"] == "0xaaaa"
    assert profile["SETTLEMENT_CONTRACT_ADDRESS"] == "0xbbbb"
    assert profile["WDK_USDT_ADDRESS"] == "0xaaaa"
    assert profile["WDK_SETTLEMENT_ADDRESS"] == "0xbbbb"
