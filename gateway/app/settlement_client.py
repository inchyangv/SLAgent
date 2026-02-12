"""Gateway settlement client — bridges gateway to facilitator/chain.

Wraps the facilitator's SettlementClient for use from gateway endpoints.
Signs receipt, submits settlement, handles disputes.
"""

from __future__ import annotations

import logging
from typing import Any

from web3 import Web3

from facilitator.settlement import SettlementClient
from gateway.app.config import settings

logger = logging.getLogger("sla-gateway.settlement")

# Settlement contract ABI (deposit, settle, dispute functions)
SETTLEMENT_ABI = [
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
        "inputs": [
            {"name": "mandateId", "type": "bytes32"},
            {"name": "requestId", "type": "bytes32"},
            {"name": "buyer", "type": "address"},
            {"name": "seller", "type": "address"},
            {"name": "maxPrice", "type": "uint256"},
            {"name": "payout", "type": "uint256"},
            {"name": "receiptHash", "type": "bytes32"},
            {"name": "gatewaySig", "type": "bytes"},
        ],
        "name": "settle",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "requestId", "type": "bytes32"}],
        "name": "openDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requestId", "type": "bytes32"},
            {"name": "finalPayout", "type": "uint256"},
        ],
        "name": "resolveDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "requestId", "type": "bytes32"}],
        "name": "finalize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Singleton settlement client
_client: SettlementClient | None = None


def _normalize_addr(addr: str, label: str) -> str:
    """Normalize an EVM address with checksum, warn on invalid."""
    if addr.startswith("0x") and len(addr) == 42:
        return Web3.to_checksum_address(addr)
    logger.warning(f"{label} is not a valid EVM address: {addr}, using zero-address")
    return "0x" + "00" * 20


def get_settlement_client() -> SettlementClient:
    global _client
    if _client is None:
        _client = SettlementClient(
            rpc_url=settings.chain_rpc_url,
            contract_address=settings.settlement_contract,
            gateway_private_key=settings.gateway_private_key,
            settlement_abi=SETTLEMENT_ABI,
        )
    return _client


def settle_request(
    *,
    request_id: str,
    mandate_id: str,
    buyer: str,
    seller: str,
    max_price: int,
    payout: int,
    receipt_hash: str,
) -> dict[str, Any]:
    """Sign and submit a settlement transaction."""
    client = get_settlement_client()

    mandate_id_bytes = bytes.fromhex(mandate_id[2:]) if mandate_id.startswith("0x") else Web3.keccak(text=mandate_id)
    request_id_bytes = Web3.keccak(text=request_id)
    receipt_hash_bytes = bytes.fromhex(receipt_hash[2:]) if receipt_hash.startswith("0x") else Web3.keccak(text=receipt_hash)

    buyer_addr = _normalize_addr(buyer, "buyer")
    seller_addr = _normalize_addr(seller, "seller")

    try:
        gateway_sig = client.sign_settlement(
            mandate_id=mandate_id_bytes,
            request_id=request_id_bytes,
            buyer=buyer_addr,
            seller=seller_addr,
            max_price=max_price,
            payout=payout,
            receipt_hash=receipt_hash_bytes,
        )
    except RuntimeError:
        logger.info(f"Settlement signing skipped (no key): {request_id}")
        return {"tx_hash": None, "gateway_signature": "", "gateway_address": ""}

    sig_hex = "0x" + gateway_sig.hex()

    tx_hash = client.submit_settlement(
        mandate_id=mandate_id_bytes,
        request_id_str=request_id,
        request_id=request_id_bytes,
        buyer=buyer_addr,
        seller=seller_addr,
        max_price=max_price,
        payout=payout,
        receipt_hash=receipt_hash_bytes,
        gateway_sig=gateway_sig,
    )

    return {
        "tx_hash": tx_hash,
        "gateway_signature": sig_hex,
        "gateway_address": client.gateway_address,
    }


def submit_dispute_open(*, request_id: str) -> dict[str, Any]:
    """Submit openDispute transaction on-chain."""
    client = get_settlement_client()
    request_id_bytes = Web3.keccak(text=request_id)

    if not client.contract or not client.w3 or not client.gateway_account:
        logger.info(f"Dispute open mock: req={request_id} (no chain)")
        return {"tx_hash": None, "mode": "mock"}

    try:
        tx = client.contract.functions.openDispute(
            request_id_bytes,
        ).build_transaction({
            "chainId": int(client.w3.eth.chain_id),
            "from": client.gateway_account.address,
            "nonce": client.w3.eth.get_transaction_count(client.gateway_account.address),
            "gas": 200_000,
            "gasPrice": client.w3.eth.gas_price,
        })

        signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
        tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        hex_hash = tx_hash.hex()
        logger.info(f"Dispute open tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        logger.error(f"Dispute open tx failed: {e}")
        return {"tx_hash": None, "mode": "error", "error": str(e)}


def submit_dispute_resolve(*, request_id: str, final_payout: int) -> dict[str, Any]:
    """Submit resolveDispute transaction on-chain."""
    client = get_settlement_client()
    request_id_bytes = Web3.keccak(text=request_id)

    if not client.contract or not client.w3 or not client.gateway_account:
        logger.info(f"Dispute resolve mock: req={request_id} final={final_payout} (no chain)")
        return {"tx_hash": None, "mode": "mock"}

    try:
        tx = client.contract.functions.resolveDispute(
            request_id_bytes,
            final_payout,
        ).build_transaction({
            "chainId": int(client.w3.eth.chain_id),
            "from": client.gateway_account.address,
            "nonce": client.w3.eth.get_transaction_count(client.gateway_account.address),
            "gas": 300_000,
            "gasPrice": client.w3.eth.gas_price,
        })

        signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
        tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        hex_hash = tx_hash.hex()
        logger.info(f"Dispute resolve tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        logger.error(f"Dispute resolve tx failed: {e}")
        return {"tx_hash": None, "mode": "error", "error": str(e)}


def submit_finalize(*, request_id: str) -> dict[str, Any]:
    """Submit finalize transaction on-chain."""
    client = get_settlement_client()
    request_id_bytes = Web3.keccak(text=request_id)

    if not client.contract or not client.w3 or not client.gateway_account:
        logger.info(f"Finalize mock: req={request_id} (no chain)")
        return {"tx_hash": None, "mode": "mock"}

    try:
        tx = client.contract.functions.finalize(
            request_id_bytes,
        ).build_transaction({
            "chainId": int(client.w3.eth.chain_id),
            "from": client.gateway_account.address,
            "nonce": client.w3.eth.get_transaction_count(client.gateway_account.address),
            "gas": 200_000,
            "gasPrice": client.w3.eth.gas_price,
        })

        signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
        tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        hex_hash = tx_hash.hex()
        logger.info(f"Finalize tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        logger.error(f"Finalize tx failed: {e}")
        return {"tx_hash": None, "mode": "error", "error": str(e)}
