"""Tests for the deposit-first verification stub."""

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


def test_verify_deposit_accepts_well_formed_tx_hash_stub():
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
    assert result["mode"] == "deposit_stub"
    assert result["source"] == "header"
