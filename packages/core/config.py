from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "DEBUG"
    secret_key: str = ""

    postgres_dsn: str = ""
    redis_dsn: str = ""
    qdrant_url: str = ""
    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""
    rabbitmq_dsn: str = ""
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    cors_origins: list[str] = ["http://localhost:8501"]

    default_initial_capital: float = 1_000_000.0
    default_commission: float = 0.0005
    default_slippage: float = 0.001

    agent_default_model: str = "claude-sonnet-4-20250514"
    agent_max_turns: int = 50
    agent_timeout_seconds: int = 120


settings = Settings()
