"""Tests for the deposit-first verifier."""

from gateway.app.deposit_verifier import verify_deposit_submission


def test_verify_deposit_mock_mode_without_chain_config():
    result = verify_deposit_submission(
        request_id="req_1",
        buyer="0x1111111111111111111111111111111111111111",
        max_price="100000",
        deposit_tx_hash=None,
        chain_rpc_url="",
        settlement_contract="",
        source="missing",
    )
    assert result is not None
    assert result["mode"] == "mock_no_chain"
    assert result["tx_hash"] is None


def test_verify_deposit_requires_tx_hash_when_chain_is_enabled():
    result = verify_deposit_submission(
        request_id="req_1",
        buyer="0x1111111111111111111111111111111111111111",
        max_price="100000",
        deposit_tx_hash=None,
        chain_rpc_url="https://rpc.test",
        settlement_contract="0x9999999999999999999999999999999999999999",
        source="missing",
    )
    assert result is None


def test_verify_deposit_accepts_well_formed_tx_hash_stub(monkeypatch):
    def fake_load_chain_deposit(**kwargs):
        return {
            "request_id_hash": "0x" + "ab" * 32,
            "event_request_id_hash": "0x" + "ab" * 32,
            "buyer": "0x1111111111111111111111111111111111111111",
            "event_buyer": "0x1111111111111111111111111111111111111111",
            "amount": 100000,
            "event_amount": 100000,
            "depositor": "0x2222222222222222222222222222222222222222",
            "block_number": 123,
        }

    import gateway.app.deposit_verifier as deposit_verifier

    monkeypatch.setattr(deposit_verifier, "_load_chain_deposit", fake_load_chain_deposit)
    monkeypatch.setattr(
        deposit_verifier.Web3,
        "keccak",
        staticmethod(lambda text: bytes.fromhex("ab" * 32)),
    )

    result = verify_deposit_submission(
        request_id="req_1",
        buyer="0x1111111111111111111111111111111111111111",
        max_price="100000",
        deposit_tx_hash="0x" + "a" * 64,
        chain_rpc_url="https://rpc.test",
        settlement_contract="0x9999999999999999999999999999999999999999",
        source="header",
    )
    assert result is not None
    assert result["mode"] == "deposit_onchain"
    assert result["source"] == "header"
    assert result["amount"] == "100000"


def test_verify_deposit_rejects_mismatched_onchain_request(monkeypatch):
    import gateway.app.deposit_verifier as deposit_verifier

    monkeypatch.setattr(
        deposit_verifier,
        "_load_chain_deposit",
        lambda **kwargs: {
            "request_id_hash": "0x" + "cd" * 32,
            "event_request_id_hash": "0x" + "cd" * 32,
            "buyer": "0x1111111111111111111111111111111111111111",
            "event_buyer": "0x1111111111111111111111111111111111111111",
            "amount": 100000,
            "event_amount": 100000,
            "depositor": "0x2222222222222222222222222222222222222222",
            "block_number": 123,
        },
    )
    monkeypatch.setattr(
        deposit_verifier.Web3,
        "keccak",
        staticmethod(lambda text: bytes.fromhex("ab" * 32)),
    )

    result = verify_deposit_submission(
        request_id="req_1",
        buyer="0x1111111111111111111111111111111111111111",
        max_price="100000",
        deposit_tx_hash="0x" + "a" * 64,
        chain_rpc_url="https://rpc.test",
        settlement_contract="0x9999999999999999999999999999999999999999",
        source="header",
    )
    assert result is None


def test_verify_deposit_rejects_underfunded_deposit(monkeypatch):
    import gateway.app.deposit_verifier as deposit_verifier

    monkeypatch.setattr(
        deposit_verifier,
        "_load_chain_deposit",
        lambda **kwargs: {
            "request_id_hash": "0x" + "ab" * 32,
            "event_request_id_hash": "0x" + "ab" * 32,
            "buyer": "0x1111111111111111111111111111111111111111",
            "event_buyer": "0x1111111111111111111111111111111111111111",
            "amount": 50000,
            "event_amount": 50000,
            "depositor": "0x2222222222222222222222222222222222222222",
            "block_number": 123,
        },
    )
    monkeypatch.setattr(
        deposit_verifier.Web3,
        "keccak",
        staticmethod(lambda text: bytes.fromhex("ab" * 32)),
    )

    result = verify_deposit_submission(
        request_id="req_1",
        buyer="0x1111111111111111111111111111111111111111",
        max_price="100000",
        deposit_tx_hash="0x" + "a" * 64,
        chain_rpc_url="https://rpc.test",
        settlement_contract="0x9999999999999999999999999999999999999999",
        source="header",
    )
    assert result is None
