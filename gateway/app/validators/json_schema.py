"""JSON Schema validator for seller responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

SCHEMAS_DIR = Path(__file__).parent / "schemas"

# Cache loaded schemas
_schema_cache: dict[str, dict] = {}


def _load_schema(schema_id: str) -> dict:
    """Load a JSON schema by ID from the schemas directory."""
    if schema_id in _schema_cache:
        return _schema_cache[schema_id]

    schema_path = SCHEMAS_DIR / f"{schema_id}.json"
    if not schema_path.exists():
        raise ValueError(f"Unknown schema_id: {schema_id}")

    with open(schema_path) as f:
        schema = json.load(f)

    _schema_cache[schema_id] = schema
    return schema


def validate_json_schema(
    response_data: Any,
    schema_id: str,
) -> dict[str, Any]:
    """Validate response data against a JSON schema.

    Returns a structured result:
        {
            "type": "json_schema",
            "schema_id": "...",
            "pass": True/False,
            "details": null or error message
        }
    """
    try:
        schema = _load_schema(schema_id)
    except ValueError as e:
        return {
            "type": "json_schema",
            "schema_id": schema_id,
            "pass": False,
            "details": str(e),
        }

    try:
        jsonschema.validate(instance=response_data, schema=schema)
        return {
            "type": "json_schema",
            "schema_id": schema_id,
            "pass": True,
            "details": None,
        }
    except jsonschema.ValidationError as e:
        return {
            "type": "json_schema",
            "schema_id": schema_id,
            "pass": False,
            "details": e.message,
        }
