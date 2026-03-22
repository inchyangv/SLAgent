"""Gateway settlement client — bridges gateway to facilitator/chain.

Wraps the facilitator's SettlementClient for use from gateway endpoints.
Signs receipt, submits settlement, handles disputes.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from eth_account import Account
from web3 import Web3

from buyer_agent.wdk_wallet import WDKWallet
from facilitator.settlement import SettlementClient
from facilitator.settlement import compute_settlement_hash
from gateway.app.config import settings
from shared.load_abi import load_settlement_abi

logger = logging.getLogger("sla-gateway.settlement")

# Settlement contract ABI — loaded from shared/abi/settlement.json (single source of truth)
SETTLEMENT_ABI = load_settlement_abi()

# Singleton settlement client
_client: SettlementClient | None = None
_gateway_wdk_wallet: WDKWallet | None = None
_gateway_wdk_lock = threading.Lock()  # thread-safe singleton initialization


def _normalize_addr(addr: str, label: str) -> str | None:
    """Normalize an EVM address with checksum, return None on invalid."""
    if addr.startswith("0x") and len(addr) == 42:
        return Web3.to_checksum_address(addr)
    logger.warning(f"{label} is not a valid EVM address: {addr}")
    return None


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


def _expected_gateway_address() -> str | None:
    env_address = os.getenv("GATEWAY_ADDRESS", "").strip()
    if env_address and Web3.is_address(env_address):
        return Web3.to_checksum_address(env_address)

    if settings.gateway_private_key:
        try:
            return Account.from_key(settings.gateway_private_key).address
        except Exception:
            return None
    return None


def _get_gateway_wdk_wallet() -> WDKWallet | None:
    global _gateway_wdk_wallet
    with _gateway_wdk_lock:
        if _gateway_wdk_wallet is None:
            _gateway_wdk_wallet = WDKWallet.from_env(
                role="gateway",
                expected_address=_expected_gateway_address(),
            )
    return _gateway_wdk_wallet


def submit_deposit(
    *,
    request_id: str,
    buyer: str,
    amount: int,
) -> dict[str, Any]:
    """Submit a deposit transaction to escrow buyer funds before settlement.

    Returns dict with tx_hash (str|None) and mode ("chain"|"mock"|"error").
    """
    client = get_settlement_client()
    request_id_bytes = Web3.keccak(text=request_id)
    buyer_addr = _normalize_addr(buyer, "buyer")
    if buyer_addr is None:
        logger.info(f"Deposit skipped (invalid buyer): req={request_id} buyer={buyer}")
        return {"tx_hash": None, "mode": "mock"}

    try:
        tx_hash = client.submit_deposit(
            request_id_str=request_id,
            request_id=request_id_bytes,
            buyer=buyer_addr,
            amount=amount,
        )
        mode = "chain" if tx_hash else "mock"
        logger.info(f"Deposit: req={request_id} buyer={buyer_addr} amount={amount} mode={mode} tx={tx_hash}")
        return {"tx_hash": tx_hash, "mode": mode}
    except Exception as e:
        logger.error(f"Deposit failed: req={request_id} error={e}")
        return {"tx_hash": None, "mode": "error", "error": str(e)}


async def _sign_settlement(
    *,
    client: SettlementClient,
    mandate_id_bytes: bytes,
    request_id_bytes: bytes,
    buyer_addr: str,
    seller_addr: str,
    max_price: int,
    payout: int,
    receipt_hash_bytes: bytes,
) -> tuple[bytes, str]:
    """Sign settlement hash using WDK → local key → raise.

    Returns (gateway_sig_bytes, gateway_address).
    Raises RuntimeError if no signing key is configured.
    """
    digest = compute_settlement_hash(
        mandate_id=mandate_id_bytes,
        request_id=request_id_bytes,
        buyer=buyer_addr,
        seller=seller_addr,
        max_price=max_price,
        payout=payout,
        receipt_hash=receipt_hash_bytes,
    )
    gateway_wallet = _get_gateway_wdk_wallet()
    if gateway_wallet:
        try:
            sig_hex = await gateway_wallet.sign_bytes(Web3.to_hex(digest))
            gateway_address = await gateway_wallet.ensure_wallet_loaded()
            sig = bytes.fromhex(sig_hex[2:] if sig_hex.startswith("0x") else sig_hex)
            return sig, gateway_address
        except Exception as exc:
            logger.warning("WDK signing failed, falling back to local key: %s", exc)

    # Local key fallback
    sig = client.sign_settlement(
        mandate_id=mandate_id_bytes,
        request_id=request_id_bytes,
        buyer=buyer_addr,
        seller=seller_addr,
        max_price=max_price,
        payout=payout,
        receipt_hash=receipt_hash_bytes,
    )
    return sig, client.gateway_address


async def settle_request(
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
    if buyer_addr is None or seller_addr is None:
        logger.info(
            f"Settlement skipped (invalid address): req={request_id} "
            f"buyer={buyer} seller={seller}"
        )
        return {
            "tx_hash": None,
            "mode": "mock",
            "gateway_signature": "",
            "gateway_address": client.gateway_address,
        }

    try:
        gateway_sig, gateway_address = await _sign_settlement(
            client=client,
            mandate_id_bytes=mandate_id_bytes,
            request_id_bytes=request_id_bytes,
            buyer_addr=buyer_addr,
            seller_addr=seller_addr,
            max_price=max_price,
            payout=payout,
            receipt_hash_bytes=receipt_hash_bytes,
        )
    except RuntimeError:
        logger.info(f"Settlement signing skipped (no key): {request_id}")
        return {"tx_hash": None, "gateway_signature": "", "gateway_address": ""}

    sig_hex = "0x" + gateway_sig.hex()

    try:
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
    except Exception as e:
        logger.error(f"Settlement failed: req={request_id} error={e}")
        return {
            "tx_hash": None,
            "mode": "error",
            "error": str(e),
            "gateway_signature": sig_hex,
            "gateway_address": gateway_address,
        }
    mode = "chain" if tx_hash else "mock"

    return {
        "tx_hash": tx_hash,
        "mode": mode,
        "gateway_signature": sig_hex,
        "gateway_address": gateway_address,
    }


def submit_dispute_open(*, request_id: str) -> dict[str, Any]:
    """Submit openDispute transaction on-chain."""
    client = get_settlement_client()
    request_id_bytes = Web3.keccak(text=request_id)

    if not client.contract or not client.w3 or not client.gateway_account:
        logger.info(f"Dispute open mock: req={request_id} (no chain)")
        return {"tx_hash": None, "mode": "mock"}

    try:
        lock = getattr(client, "_tx_lock", None)
        with (lock if lock else nullcontext()):
            nonce_fn = getattr(client, "_next_nonce", None)
            nonce = nonce_fn() if callable(nonce_fn) else client.w3.eth.get_transaction_count(client.gateway_account.address, "pending")
            tx = client.contract.functions.openDispute(
                request_id_bytes,
            ).build_transaction({
                "chainId": int(client.w3.eth.chain_id),
                "from": client.gateway_account.address,
                "nonce": nonce,
                "gas": 200_000,
                "gasPrice": client.w3.eth.gas_price,
            })

            signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            hex_hash = tx_hash.hex()
        logger.info(f"Dispute open tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        if hasattr(client, "_last_nonce"):
            client._last_nonce = None
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
        lock = getattr(client, "_tx_lock", None)
        with (lock if lock else nullcontext()):
            nonce_fn = getattr(client, "_next_nonce", None)
            nonce = nonce_fn() if callable(nonce_fn) else client.w3.eth.get_transaction_count(client.gateway_account.address, "pending")
            tx = client.contract.functions.resolveDispute(
                request_id_bytes,
                final_payout,
            ).build_transaction({
                "chainId": int(client.w3.eth.chain_id),
                "from": client.gateway_account.address,
                "nonce": nonce,
                "gas": 300_000,
                "gasPrice": client.w3.eth.gas_price,
            })

            signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            hex_hash = tx_hash.hex()
        logger.info(f"Dispute resolve tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        if hasattr(client, "_last_nonce"):
            client._last_nonce = None
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
        lock = getattr(client, "_tx_lock", None)
        with (lock if lock else nullcontext()):
            nonce_fn = getattr(client, "_next_nonce", None)
            nonce = nonce_fn() if callable(nonce_fn) else client.w3.eth.get_transaction_count(client.gateway_account.address, "pending")
            tx = client.contract.functions.finalize(
                request_id_bytes,
            ).build_transaction({
                "chainId": int(client.w3.eth.chain_id),
                "from": client.gateway_account.address,
                "nonce": nonce,
                "gas": 200_000,
                "gasPrice": client.w3.eth.gas_price,
            })

            signed_tx = client.w3.eth.account.sign_transaction(tx, client.gateway_private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            hex_hash = tx_hash.hex()
        logger.info(f"Finalize tx submitted: {hex_hash}")
        return {"tx_hash": hex_hash, "mode": "chain"}
    except Exception as e:
        if hasattr(client, "_last_nonce"):
            client._last_nonce = None
        logger.error(f"Finalize tx failed: {e}")
        return {"tx_hash": None, "mode": "error", "error": str(e)}
