"""Robust JSON extraction and validation utilities.

Handles common LLM output quirks:
- JSON wrapped in markdown fences (```json ... ```)
- Leading/trailing whitespace
- Schema validation with detailed error reporting
"""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema


# Regex to extract JSON from markdown fences
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def extract_json(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from raw LLM output.

    Tries in order:
    1. Direct JSON.parse
    2. Extract from markdown fences
    3. Find first { ... } block

    Raises:
        JSONExtractionError: If no valid JSON can be extracted.
    """
    text = raw.strip()

    # 1) Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) Fenced code block
    match = _FENCED_JSON_RE.search(text)
    if match:
        try:
            obj = json.loads(match.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3) Find first { ... } (greedy from first { to last })
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            obj = json.loads(text[first_brace : last_brace + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise JSONExtractionError(f"Could not extract valid JSON from response: {text[:200]}")


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate data against a JSON schema.

    Returns:
        List of error messages (empty if valid).
    """
    validator = jsonschema.Draft202012Validator(schema)
    return [err.message for err in validator.iter_errors(data)]


class JSONExtractionError(Exception):
    """Raised when JSON cannot be extracted from LLM output."""
