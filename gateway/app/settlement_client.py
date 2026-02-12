"""Gateway settlement client — bridges gateway to facilitator/chain.

Wraps the facilitator's SettlementClient for use from gateway endpoints.
Signs receipt, submits settlement, returns tx hash.
"""

from __future__ import annotations

import logging
from typing import Any

from web3 import Web3

from facilitator.settlement import SettlementClient
from gateway.app.config import settings

logger = logging.getLogger("sla-gateway.settlement")

# Settlement contract ABI (minimal — just the settle function)
SETTLEMENT_ABI = [
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
    }
]

# Singleton settlement client
_client: SettlementClient | None = None


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
    """Sign and submit a settlement transaction.

    Returns:
        {
            "tx_hash": "0x..." or None,
            "gateway_signature": "0x...",
            "gateway_address": "0x...",
        }
    """
    client = get_settlement_client()

    # Convert hex strings to bytes32
    mandate_id_bytes = bytes.fromhex(mandate_id[2:]) if mandate_id.startswith("0x") else Web3.keccak(text=mandate_id)
    request_id_bytes = Web3.keccak(text=request_id)
    receipt_hash_bytes = bytes.fromhex(receipt_hash[2:]) if receipt_hash.startswith("0x") else Web3.keccak(text=receipt_hash)

    # Normalize addresses
    buyer_addr = buyer if buyer.startswith("0x") and len(buyer) == 42 else "0x" + "00" * 20
    seller_addr = seller if seller.startswith("0x") and len(seller) == 42 else "0x" + "00" * 20

    try:
        # Sign
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
        # No private key configured → mock mode
        logger.info(f"Settlement signing skipped (no key): {request_id}")
        return {
            "tx_hash": None,
            "gateway_signature": "",
            "gateway_address": "",
        }

    sig_hex = "0x" + gateway_sig.hex()

    # Submit
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
