"""Deposit-first verification helpers for the gateway."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from web3 import Web3

_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
logger = logging.getLogger("sla-gateway.deposit")

_DEPOSIT_ABI = [
    {
        "inputs": [
            {"name": "requestId", "type": "bytes32"},
            {"name": "buyer", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "requestId", "type": "bytes32"},
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "depositor", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "Deposited",
        "type": "event",
    },
]


@lru_cache(maxsize=4)
def _get_web3(rpc_url: str) -> Web3:
    return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 6}))


def _checksum_address(address: str, *, label: str) -> str:
    if not Web3.is_address(address):
        raise ValueError(f"{label} is not a valid EVM address: {address}")
    return Web3.to_checksum_address(address)


def _load_chain_deposit(
    *,
    tx_hash: str,
    chain_rpc_url: str,
    settlement_contract: str,
) -> dict[str, Any]:
    w3 = _get_web3(chain_rpc_url)
    if not w3.is_connected():
        raise RuntimeError("failed to connect to chain RPC")

    contract_address = _checksum_address(settlement_contract, label="settlement_contract")
    contract = w3.eth.contract(address=contract_address, abi=_DEPOSIT_ABI)

    tx = w3.eth.get_transaction(tx_hash)
    receipt = w3.eth.get_transaction_receipt(tx_hash)

    if receipt is None or int(receipt["status"]) != 1:
        raise RuntimeError("deposit transaction is missing or failed")

    tx_to = tx.get("to")
    if not tx_to or tx_to.lower() != contract_address.lower():
        raise RuntimeError("deposit transaction target mismatch")

    function, args = contract.decode_function_input(tx.get("input", "0x"))
    if function.fn_name != "deposit":
        raise RuntimeError("transaction did not call deposit()")

    events = contract.events.Deposited().process_receipt(receipt)
    if not events:
        raise RuntimeError("deposit event not found in receipt")
    event_args = events[0]["args"]

    return {
        "tx_hash": tx_hash,
        "request_id_hash": Web3.to_hex(args["requestId"]),
        "buyer": Web3.to_checksum_address(args["buyer"]),
        "amount": int(args["amount"]),
        "depositor": Web3.to_checksum_address(event_args["depositor"]),
        "event_request_id_hash": Web3.to_hex(event_args["requestId"]),
        "event_buyer": Web3.to_checksum_address(event_args["buyer"]),
        "event_amount": int(event_args["amount"]),
        "block_number": int(receipt["blockNumber"]),
    }


def verify_deposit_submission(
    *,
    request_id: str,
    buyer: str,
    max_price: str,
    deposit_tx_hash: str | None,
    chain_rpc_url: str,
    settlement_contract: str,
    source: str,
) -> dict[str, Any] | None:
    """Verify that a request is backed by a matching on-chain deposit."""
    tx_hash = (deposit_tx_hash or "").strip() or None
    has_chain_config = bool(chain_rpc_url and settlement_contract)

    if not tx_hash:
        if not has_chain_config:
            return {
                "request_id": request_id,
                "buyer": buyer,
                "amount": max_price,
                "tx_hash": None,
                "mode": "mock_no_chain",
                "source": "no_chain_config",
            }
        # In demo mode, allow calls without deposit for easier demonstration
        import os
        if os.getenv("DEMO_MODE", "").lower() == "true":
            return {
                "request_id": request_id,
                "buyer": buyer,
                "amount": max_price,
                "tx_hash": None,
                "mode": "demo_bypass",
                "source": source,
            }
        return None

    # Normalize: add 0x prefix if missing
    if tx_hash and not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    if not _TX_HASH_RE.fullmatch(tx_hash):
        return None

    try:
        chain_deposit = _load_chain_deposit(
            tx_hash=tx_hash,
            chain_rpc_url=chain_rpc_url,
            settlement_contract=settlement_contract,
        )
        expected_request_id_hash = Web3.to_hex(Web3.keccak(text=request_id))
        expected_buyer = _checksum_address(buyer, label="buyer")
        amount = int(chain_deposit["amount"])
        min_amount = int(max_price)
        if chain_deposit["request_id_hash"] != expected_request_id_hash:
            raise RuntimeError("requestId hash mismatch")
        if chain_deposit["event_request_id_hash"] != expected_request_id_hash:
            raise RuntimeError("deposit event requestId mismatch")
        if chain_deposit["buyer"] != expected_buyer:
            raise RuntimeError("buyer mismatch")
        if chain_deposit["event_buyer"] != expected_buyer:
            raise RuntimeError("deposit event buyer mismatch")
        if chain_deposit["event_amount"] != amount:
            raise RuntimeError("deposit event amount mismatch")
        if amount < min_amount:
            raise RuntimeError("deposit amount below mandate max_price")
    except Exception as exc:
        logger.warning("Deposit verification failed for %s: %s", tx_hash, exc)
        return None

    return {
        "request_id": request_id,
        "buyer": expected_buyer,
        "amount": str(amount),
        "tx_hash": tx_hash,
        "mode": "deposit_onchain",
        "source": source,
        "depositor": chain_deposit["depositor"],
        "block_number": chain_deposit["block_number"],
    }
