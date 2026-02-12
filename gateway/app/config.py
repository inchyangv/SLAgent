"""Gateway configuration loaded from environment variables."""

import os


class Settings:
    seller_upstream_url: str = os.getenv("SELLER_UPSTREAM_URL", "http://localhost:8001")
    chain_rpc_url: str = os.getenv("CHAIN_RPC_URL", "")
    settlement_contract: str = os.getenv("SETTLEMENT_CONTRACT_ADDRESS", "")
    payment_token: str = os.getenv("PAYMENT_TOKEN_ADDRESS", "")
    gateway_private_key: str = os.getenv("GATEWAY_PRIVATE_KEY", "")
    host: str = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port: int = int(os.getenv("GATEWAY_PORT", "8000"))


settings = Settings()
