"""Tests for JSON extraction and validation utilities."""

import pytest

from seller.json_extractor import JSONExtractionError, extract_json, validate_against_schema

INVOICE_SCHEMA = {
    "type": "object",
    "required": ["invoice_id", "amount", "currency", "line_items"],
    "properties": {
        "invoice_id": {"type": "string", "minLength": 1},
        "amount": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
        "line_items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["description", "quantity", "unit_price"],
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_price": {"type": "number", "minimum": 0},
                },
            },
        },
    },
}


def test_extract_direct_json():
    raw = '{"invoice_id": "INV-001", "amount": 100}'
    result = extract_json(raw)
    assert result["invoice_id"] == "INV-001"


def test_extract_fenced_json():
    raw = '```json\n{"invoice_id": "INV-002", "amount": 200}\n```'
    result = extract_json(raw)
    assert result["invoice_id"] == "INV-002"


def test_extract_fenced_no_lang():
    raw = '```\n{"invoice_id": "INV-003", "amount": 300}\n```'
    result = extract_json(raw)
    assert result["invoice_id"] == "INV-003"


def test_extract_embedded_braces():
    raw = 'Here is the invoice:\n{"invoice_id": "INV-004", "amount": 400}\nEnd.'
    result = extract_json(raw)
    assert result["invoice_id"] == "INV-004"


def test_extract_with_whitespace():
    raw = '  \n  {"invoice_id": "INV-005", "amount": 500}  \n  '
    result = extract_json(raw)
    assert result["invoice_id"] == "INV-005"


def test_extract_invalid_raises():
    with pytest.raises(JSONExtractionError):
        extract_json("This is not JSON at all")


def test_extract_empty_raises():
    with pytest.raises(JSONExtractionError):
        extract_json("")


def test_validate_valid_invoice():
    data = {
        "invoice_id": "INV-001",
        "amount": 100.0,
        "currency": "USD",
        "line_items": [
            {"description": "Service", "quantity": 1, "unit_price": 100.0}
        ],
    }
    errors = validate_against_schema(data, INVOICE_SCHEMA)
    assert errors == []


def test_validate_missing_field():
    data = {"invoice_id": "INV-001", "amount": 100.0}
    errors = validate_against_schema(data, INVOICE_SCHEMA)
    assert len(errors) > 0
    assert any("currency" in e or "line_items" in e for e in errors)


def test_validate_bad_currency():
    data = {
        "invoice_id": "INV-001",
        "amount": 100.0,
        "currency": "JPY",
        "line_items": [
            {"description": "Service", "quantity": 1, "unit_price": 100.0}
        ],
    }
    errors = validate_against_schema(data, INVOICE_SCHEMA)
    assert len(errors) > 0
