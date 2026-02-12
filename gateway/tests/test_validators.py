"""Tests for JSON schema validator."""

from gateway.app.validators.json_schema import validate_json_schema


VALID_INVOICE = {
    "invoice_id": "INV-001",
    "amount": 150.00,
    "currency": "USD",
    "line_items": [
        {"description": "Widget A", "quantity": 3, "unit_price": 50.00},
    ],
}


def test_valid_invoice_passes():
    result = validate_json_schema(VALID_INVOICE, "invoice_v1")
    assert result["pass"] is True
    assert result["type"] == "json_schema"
    assert result["schema_id"] == "invoice_v1"
    assert result["details"] is None


def test_missing_required_field_fails():
    bad = {"invoice_id": "INV-002", "amount": 100.00}
    result = validate_json_schema(bad, "invoice_v1")
    assert result["pass"] is False
    assert "currency" in result["details"] or "line_items" in result["details"]


def test_wrong_type_fails():
    bad = {**VALID_INVOICE, "amount": "not a number"}
    result = validate_json_schema(bad, "invoice_v1")
    assert result["pass"] is False


def test_invalid_currency_fails():
    bad = {**VALID_INVOICE, "currency": "JPY"}
    result = validate_json_schema(bad, "invoice_v1")
    assert result["pass"] is False


def test_empty_line_items_fails():
    bad = {**VALID_INVOICE, "line_items": []}
    result = validate_json_schema(bad, "invoice_v1")
    assert result["pass"] is False


def test_unknown_schema_id_fails():
    result = validate_json_schema({}, "nonexistent_schema")
    assert result["pass"] is False
    assert "Unknown schema_id" in result["details"]


def test_valid_invoice_with_notes():
    data = {**VALID_INVOICE, "notes": "Thank you for your business"}
    result = validate_json_schema(data, "invoice_v1")
    assert result["pass"] is True


def test_deterministic():
    """Same input always produces same output."""
    r1 = validate_json_schema(VALID_INVOICE, "invoice_v1")
    r2 = validate_json_schema(VALID_INVOICE, "invoice_v1")
    assert r1 == r2
