"""Gateway configuration loaded from environment variables.

If DEMO_PRIVATE_KEY or DEMO_MNEMONIC is set, role-specific keys are
auto-derived before reading settings (see demo_keys module).
"""

import os

# Load repo-root .env first, then inject demo-derived role keys.
from shared.env import bootstrap_env

bootstrap_env()

# Inject demo-derived keys before reading config
from gateway.app.demo_keys import inject_demo_env

inject_demo_env()


class Settings:
    seller_upstream_url: str = os.getenv("SELLER_UPSTREAM_URL", "http://localhost:8001")
    seller_address: str = os.getenv("SELLER_ADDRESS", "")
    buyer_address: str = os.getenv("BUYER_ADDRESS", "")
    # Ethereum Sepolia is the default target for the USDT + WDK flow.
    chain_id: int = int(os.getenv("CHAIN_ID", "11155111"))
    chain_rpc_url: str = os.getenv(
        "CHAIN_RPC_URL",
        "https://rpc.sepolia.org",
    )
    settlement_contract: str = os.getenv("SETTLEMENT_CONTRACT_ADDRESS", "")
    payment_token: str = os.getenv("PAYMENT_TOKEN_ADDRESS", "")
    gateway_private_key: str = os.getenv("GATEWAY_PRIVATE_KEY", "")
    host: str = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port: int = int(os.getenv("GATEWAY_PORT", "8000"))


settings = Settings()
