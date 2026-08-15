"""Dependency injection — provides the singleton IntegratedBot to route handlers."""

from decimal import Decimal
from typing import AsyncIterator

from fastapi import Request

from packages.integration.pipeline import IntegratedBot, IntegrationConfig

_bot: IntegratedBot | None = None


async def get_bot(request: Request) -> IntegratedBot:
    global _bot
    if _bot is None:
        cfg = IntegrationConfig()
        _bot = IntegratedBot(config=cfg)
    return _bot


async def get_bot_started(request: Request) -> IntegratedBot:
    bot = await get_bot(request)
    if not bot._running:
        bot.start()
    return bot


def create_bot(config: IntegrationConfig | None = None) -> IntegratedBot:
    global _bot
    if _bot is None:
        _bot = IntegratedBot(config=config)
    return _bot


def shutdown_bot() -> None:
    global _bot
    if _bot is not None and _bot._running:
        try:
            _bot.stop()
        except Exception:
            pass
    _bot = None


def get_bot_instance() -> IntegratedBot | None:
    return _bot
