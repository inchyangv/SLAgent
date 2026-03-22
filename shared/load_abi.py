"""Utility for loading shared ABI definitions."""

from __future__ import annotations

import json
import os
from typing import Any

_ABI_DIR = os.path.join(os.path.dirname(__file__), "abi")


def load_abi(name: str) -> list[dict[str, Any]]:
    """Load an ABI by filename (without .json extension).

    Args:
        name: ABI file name without extension, e.g. "settlement"

    Returns:
        Parsed ABI as a list of dicts.
    """
    path = os.path.join(_ABI_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def load_settlement_abi() -> list[dict[str, Any]]:
    """Load the SLASettlement contract ABI."""
    return load_abi("settlement")
