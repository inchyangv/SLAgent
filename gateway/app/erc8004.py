"""ERC-8004 orchestration adapter for SLA-Pay gateway.

Provides a Python interface for interacting with the SLAOrchestrator contract,
which maps SLA-Pay settlement lifecycle events to ERC-8004 registries:
  - Identity Registry: agent registration
  - Validation Registry: receipt verification tracking
  - Reputation Registry: post-settlement feedback

Usage:
  - Set ORCHESTRATOR_CONTRACT_ADDRESS env var to enable
  - When not configured, all operations gracefully no-op (mock mode)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from web3 import Web3

from gateway.app.config import settings

logger = logging.getLogger("sla-gateway.erc8004")

ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_CONTRACT_ADDRESS", "")

# Minimal ABI for SLAOrchestrator
ORCHESTRATOR_ABI = [
    {
        "inputs": [{"name": "agentURI", "type": "string"}],
        "name": "registerAgent",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requestId", "type": "bytes32"},
            {"name": "receiptHash", "type": "bytes32"},
        ],
        "name": "recordValidation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "receiptHash", "type": "bytes32"},
            {"name": "pass", "type": "bool"},
            {"name": "tag", "type": "string"},
        ],
        "name": "submitValidationResult",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "requestId", "type": "bytes32"}],
        "name": "recordReputation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "getAgentId",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ERC8004Adapter:
    """Adapter for ERC-8004 orchestration hooks.

    When orchestrator contract is configured, submits on-chain transactions.
    Otherwise operates in mock mode logging operations for demo visibility.
    """

    def __init__(self) -> None:
        self.mock_mode = True
        self.w3 = None
        self.contract = None
        self.account = None
        self._mock_agents: dict[str, int] = {}
        self._mock_validations: dict[str, dict[str, Any]] = {}
        self._mock_reputations: list[dict[str, Any]] = []
        self._next_mock_id = 1

        if ORCHESTRATOR_ADDRESS and settings.chain_rpc_url and settings.gateway_private_key:
            try:
                self.w3 = Web3(Web3.HTTPProvider(settings.chain_rpc_url))
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(ORCHESTRATOR_ADDRESS),
                    abi=ORCHESTRATOR_ABI,
                )
                from eth_account import Account
                self.account = Account.from_key(settings.gateway_private_key)
                self.mock_mode = False
                logger.info(f"ERC-8004 adapter: chain mode (orchestrator={ORCHESTRATOR_ADDRESS})")
            except Exception as e:
                logger.warning(f"ERC-8004 adapter: failed to init chain mode: {e}")
        else:
            logger.info("ERC-8004 adapter: mock mode (no orchestrator configured)")

    def register_agent(self, agent_uri: str) -> dict[str, Any]:
        """Register an agent on the Identity Registry."""
        if self.mock_mode:
            agent_id = self._next_mock_id
            self._next_mock_id += 1
            self._mock_agents[agent_uri] = agent_id
            logger.info(f"ERC-8004 mock: registered agent {agent_uri} → id={agent_id}")
            return {"agent_id": agent_id, "tx_hash": None, "mode": "mock"}

        return self._submit_tx("registerAgent", [agent_uri])

    def record_validation(
        self, request_id: str, receipt_hash: str
    ) -> dict[str, Any]:
        """Record a receipt validation request on the Validation Registry."""
        request_id_bytes = Web3.keccak(text=request_id)
        receipt_hash_bytes = (
            bytes.fromhex(receipt_hash[2:])
            if receipt_hash.startswith("0x")
            else Web3.keccak(text=receipt_hash)
        )

        if self.mock_mode:
            self._mock_validations[request_id] = {
                "receipt_hash": receipt_hash,
                "response": None,
                "tag": None,
            }
            logger.info(f"ERC-8004 mock: validation recorded for {request_id}")
            return {"tx_hash": None, "mode": "mock"}

        return self._submit_tx("recordValidation", [request_id_bytes, receipt_hash_bytes])

    def submit_validation_result(
        self, receipt_hash: str, passed: bool, tag: str = "sla-compliance"
    ) -> dict[str, Any]:
        """Submit validation result (pass/fail) to the Validation Registry."""
        receipt_hash_bytes = (
            bytes.fromhex(receipt_hash[2:])
            if receipt_hash.startswith("0x")
            else Web3.keccak(text=receipt_hash)
        )

        if self.mock_mode:
            for v in self._mock_validations.values():
                if v["receipt_hash"] == receipt_hash:
                    v["response"] = 100 if passed else 0
                    v["tag"] = tag
            logger.info(f"ERC-8004 mock: validation result {receipt_hash} → {passed} ({tag})")
            return {"tx_hash": None, "mode": "mock"}

        return self._submit_tx("submitValidationResult", [receipt_hash_bytes, passed, tag])

    def record_reputation(self, request_id: str) -> dict[str, Any]:
        """Record reputation feedback after settlement finalization."""
        request_id_bytes = Web3.keccak(text=request_id)

        if self.mock_mode:
            self._mock_reputations.append({"request_id": request_id})
            logger.info(f"ERC-8004 mock: reputation recorded for {request_id}")
            return {"tx_hash": None, "mode": "mock"}

        return self._submit_tx("recordReputation", [request_id_bytes])

    def get_agent_id(self, address: str) -> int:
        """Look up an agent's ERC-8004 ID by address."""
        if self.mock_mode:
            return 0

        try:
            addr = Web3.to_checksum_address(address)
            return self.contract.functions.getAgentId(addr).call()
        except Exception as e:
            logger.error(f"ERC-8004 getAgentId failed: {e}")
            return 0

    def get_status(self) -> dict[str, Any]:
        """Return adapter status for health/debug endpoints."""
        return {
            "enabled": not self.mock_mode,
            "mode": "chain" if not self.mock_mode else "mock",
            "orchestrator_address": ORCHESTRATOR_ADDRESS or None,
            "mock_agents": len(self._mock_agents) if self.mock_mode else None,
            "mock_validations": len(self._mock_validations) if self.mock_mode else None,
            "mock_reputations": len(self._mock_reputations) if self.mock_mode else None,
        }

    def _submit_tx(self, fn_name: str, args: list) -> dict[str, Any]:
        """Submit a transaction to the orchestrator contract."""
        try:
            tx = getattr(self.contract.functions, fn_name)(*args).build_transaction({
                "chainId": int(self.w3.eth.chain_id),
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 300_000,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed = self.w3.eth.account.sign_transaction(tx, settings.gateway_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            hex_hash = tx_hash.hex()
            logger.info(f"ERC-8004 {fn_name} tx: {hex_hash}")
            return {"tx_hash": hex_hash, "mode": "chain"}
        except Exception as e:
            logger.error(f"ERC-8004 {fn_name} tx failed: {e}")
            return {"tx_hash": None, "mode": "error", "error": str(e)}


# Singleton
erc8004_adapter = ERC8004Adapter()
