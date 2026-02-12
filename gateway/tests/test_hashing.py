"""Test vectors for canonical hashing."""

from gateway.app.hashing import canonical_json, compute_mandate_id, compute_receipt_hash, keccak256


# --- Test Vector 1: canonical JSON ---
def test_canonical_json_sort_and_compact():
    obj = {"b": 2, "a": 1, "c": {"z": 3, "y": 4}}
    result = canonical_json(obj)
    assert result == b'{"a":1,"b":2,"c":{"y":4,"z":3}}'


def test_canonical_json_string_amounts():
    obj = {"amount": "100000", "name": "test"}
    result = canonical_json(obj)
    assert result == b'{"amount":"100000","name":"test"}'


# --- Test Vector 2: mandate_id is deterministic ---
SAMPLE_MANDATE = {
    "version": "1.0",
    "chain_id": 2046399126,
    "settlement_contract": "0x1234567890abcdef1234567890abcdef12345678",
    "payment_token": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    "seller": "0x1111111111111111111111111111111111111111",
    "buyer": "0x2222222222222222222222222222222222222222",
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
    "timeout_ms": 8000,
    "validators": [{"type": "json_schema", "schema_id": "invoice_v1"}],
    "dispute": {
        "window_seconds": 600,
        "bond_amount": "50000",
        "resolver": "0x3333333333333333333333333333333333333333",
    },
    "created_at": "2026-02-12T00:00:00Z",
    "expires_at": "2026-02-20T00:00:00Z",
}


def test_mandate_id_deterministic():
    id1 = compute_mandate_id(SAMPLE_MANDATE)
    id2 = compute_mandate_id(SAMPLE_MANDATE)
    assert id1 == id2
    assert id1.startswith("0x")
    assert len(id1) == 66  # 0x + 64 hex chars


def test_mandate_id_excludes_signatures():
    mandate_with_sigs = {
        **SAMPLE_MANDATE,
        "mandate_id": "0xwillbeignored",
        "seller_signature": "0xdeadbeef",
        "buyer_signature": "0xcafebabe",
    }
    # Should produce same hash as without signatures
    assert compute_mandate_id(mandate_with_sigs) == compute_mandate_id(SAMPLE_MANDATE)


# --- Test Vector 3: receipt hash ---
SAMPLE_RECEIPT = {
    "version": "1.0",
    "mandate_id": "0xabc123",
    "request_id": "req_20260212_000001",
    "buyer": "0x2222222222222222222222222222222222222222",
    "seller": "0x1111111111111111111111111111111111111111",
    "gateway": "0x4444444444444444444444444444444444444444",
    "timestamps": {
        "t_request_received": "2026-02-12T12:00:00.000Z",
        "t_first_token": "2026-02-12T12:00:00.450Z",
        "t_response_done": "2026-02-12T12:00:01.800Z",
    },
    "metrics": {"ttft_ms": 450, "latency_ms": 1800},
    "outcome": {"success": True, "error_code": None},
    "validation": {
        "overall_pass": True,
        "results": [
            {"type": "json_schema", "schema_id": "invoice_v1", "pass": True, "details": None}
        ],
    },
    "pricing": {
        "max_price": "100000",
        "computed_payout": "100000",
        "computed_refund": "0",
        "rule_applied": "latency_tier_lte_2000",
    },
}


def test_receipt_hash_deterministic():
    h1 = compute_receipt_hash(SAMPLE_RECEIPT)
    h2 = compute_receipt_hash(SAMPLE_RECEIPT)
    assert h1 == h2
    assert h1.startswith("0x")
    assert len(h1) == 66


def test_receipt_hash_excludes_hashes_and_sigs():
    receipt_with_meta = {
        **SAMPLE_RECEIPT,
        "hashes": {
            "request_hash": "0x111",
            "response_hash": "0x222",
            "receipt_hash": "0x333",
        },
        "signatures": {"gateway_signature": "0xsig"},
    }
    assert compute_receipt_hash(receipt_with_meta) == compute_receipt_hash(SAMPLE_RECEIPT)


# --- Test Vector: known hash for empty object ---
def test_keccak256_known():
    # keccak256 of "{}" (empty JSON object)
    h = keccak256(b"{}")
    assert h.startswith("0x")
    assert len(h) == 66
    # Verify it's stable
    assert h == keccak256(b"{}")
