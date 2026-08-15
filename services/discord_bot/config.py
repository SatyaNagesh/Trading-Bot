"""Discord bot configuration."""

from pydantic_settings import BaseSettings


class DiscordBotConfig(BaseSettings):
    token: str = ""
    api_base_url: str = "http://localhost:8000"
    api_secret: str = "dev-secret-change-in-production"
    command_prefix: str = "!quantlab"
    admin_role: str = "QuantLab Admin"
    status_update_interval_seconds: int = 30

    model_config = {"env_prefix": "QUANTLAB_DISCORD_", "env_file": ".env"}
