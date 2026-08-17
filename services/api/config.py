"""API configuration — loaded from environment variables with Pydantic."""

from pydantic_settings import BaseSettings


class APIConfig(BaseSettings):
    title: str = "QuantLab AI"
    version: str = "0.1.0-rc1"
    description: str = "Unified REST API for QuantLab AI trading engine"
    host: str = "0.0.0.0"
    port: int = 8000

    api_secret: str = "dev-secret-change-in-production"

    rate_limit_per_minute: int = 120
    rate_limit_window_seconds: int = 60

    db_path: str = "data/quantlab.db"
    bot_initial_capital: float = 100000.0

    max_websocket_clients: int = 50
    dashboard_refresh_seconds: int = 2

    model_config = {"env_prefix": "QUANTLAB_API_", "env_file": ".env", "extra": "ignore"}
