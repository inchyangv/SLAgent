"""Tests for single-secret demo key derivation."""

from __future__ import annotations

import os
from unittest.mock import patch

from eth_account import Account

from gateway.app.demo_keys import (
    ROLES,
    _derive_from_mnemonic,
    _derive_from_private_key,
    get_demo_keys,
    inject_demo_env,
)

# Test key (DO NOT use in production)
_TEST_KEY = "0x" + "ab" * 32

# Standard BIP-39 test mnemonic (DO NOT use in production)
_TEST_MNEMONIC = "test test test test test test test test test test test junk"


# ── _derive_from_private_key ────────────────────────────────────────────────


def test_derive_private_key_all_roles():
    """All roles get the same key and address."""
    result = _derive_from_private_key(_TEST_KEY)
    acct = Account.from_key(_TEST_KEY)

    for role in ROLES:
        assert result[f"{role}_private_key"] == _TEST_KEY
        assert result[f"{role}_address"] == acct.address


def test_derive_private_key_valid_addresses():
    """Derived addresses are valid EVM checksummed addresses."""
    result = _derive_from_private_key(_TEST_KEY)
    for role in ROLES:
        addr = result[f"{role}_address"]
        assert addr.startswith("0x")
        assert len(addr) == 42


# ── _derive_from_mnemonic ──────────────────────────────────────────────────


def test_derive_mnemonic_different_keys():
    """Each role gets a different key from mnemonic derivation."""
    result = _derive_from_mnemonic(_TEST_MNEMONIC)

    keys = [result[f"{role}_private_key"] for role in ROLES]
    assert len(set(keys)) == len(ROLES), "All role keys should be unique"

    addrs = [result[f"{role}_address"] for role in ROLES]
    assert len(set(addrs)) == len(ROLES), "All role addresses should be unique"


def test_derive_mnemonic_deterministic():
    """Same mnemonic always produces same keys."""
    r1 = _derive_from_mnemonic(_TEST_MNEMONIC)
    r2 = _derive_from_mnemonic(_TEST_MNEMONIC)
    assert r1 == r2


def test_derive_mnemonic_valid_addresses():
    """Derived addresses are valid EVM checksummed addresses."""
    result = _derive_from_mnemonic(_TEST_MNEMONIC)
    for role in ROLES:
        addr = result[f"{role}_address"]
        assert addr.startswith("0x")
        assert len(addr) == 42


# ── get_demo_keys ──────────────────────────────────────────────────────────


@patch.dict(os.environ, {}, clear=True)
def test_get_demo_keys_no_env():
    """Returns None when no demo env is set."""
    result = get_demo_keys()
    assert result is None


@patch.dict(os.environ, {"DEMO_PRIVATE_KEY": _TEST_KEY}, clear=True)
def test_get_demo_keys_auto_detect_private_key():
    """Auto-detects private_key mode."""
    result = get_demo_keys()
    assert result is not None
    assert result["buyer_private_key"] == _TEST_KEY


@patch.dict(os.environ, {"DEMO_MNEMONIC": _TEST_MNEMONIC}, clear=True)
def test_get_demo_keys_auto_detect_mnemonic():
    """Auto-detects mnemonic mode."""
    result = get_demo_keys()
    assert result is not None
    assert result["buyer_private_key"] != result["seller_private_key"]


@patch.dict(
    os.environ,
    {"DEMO_SECRET_MODE": "private_key", "DEMO_PRIVATE_KEY": _TEST_KEY},
    clear=True,
)
def test_get_demo_keys_explicit_mode():
    """Explicit mode takes effect."""
    result = get_demo_keys()
    assert result is not None
    for role in ROLES:
        assert result[f"{role}_private_key"] == _TEST_KEY


# ── inject_demo_env ──────────────────────────────────────────────────────────


@patch.dict(os.environ, {"DEMO_PRIVATE_KEY": _TEST_KEY}, clear=True)
def test_inject_demo_env_sets_vars():
    """inject_demo_env populates role env vars."""
    assert inject_demo_env() is True
    assert os.environ.get("BUYER_PRIVATE_KEY") == _TEST_KEY
    assert os.environ.get("SELLER_PRIVATE_KEY") == _TEST_KEY
    assert os.environ.get("GATEWAY_PRIVATE_KEY") == _TEST_KEY
    assert os.environ.get("BUYER_ADDRESS") != ""


@patch.dict(
    os.environ,
    {"DEMO_PRIVATE_KEY": _TEST_KEY, "BUYER_PRIVATE_KEY": "0x" + "ff" * 32},
    clear=True,
)
def test_inject_demo_env_explicit_takes_precedence():
    """Explicit role env var is NOT overwritten."""
    inject_demo_env()
    assert os.environ["BUYER_PRIVATE_KEY"] == "0x" + "ff" * 32
    # Other roles still get demo key
    assert os.environ["SELLER_PRIVATE_KEY"] == _TEST_KEY


@patch.dict(os.environ, {}, clear=True)
def test_inject_demo_env_no_secret():
    """Returns False when no demo secret."""
    assert inject_demo_env() is False
