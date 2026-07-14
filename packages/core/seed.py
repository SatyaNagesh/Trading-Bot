"""Seed data and test fixtures for development."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from packages.core.database import async_session
from packages.core.logging import get_logger
from packages.core.models import Strategy, Hypothesis, MarketData
from packages.domain.models import StrategyStatus, HypothesisStatus

logger = get_logger("seed")


SEED_STRATEGIES = [
    {"name": "SMA Crossover", "author": "system", "dsl": "sma_20 crosses above sma_50", "tags": ["momentum", "trend"]},
    {"name": "RSI Mean Reversion", "author": "system", "dsl": "rsi < 30 then buy, rsi > 70 then sell", "tags": ["mean-reversion"]},
    {"name": "Bollinger Squeeze", "author": "system", "dsl": "bb_width < threshold then breakout", "tags": ["volatility"]},
]

SEED_HYPOTHESES = [
    {"title": "Momentum persists 5 days after SMA crossover", "description": "Testing post-crossover drift", "keywords": ["momentum", "sma"]},
    {"title": "RSI oversold bounces have 60%+ win rate", "description": "Testing mean reversion in NSE 500", "keywords": ["rsi", "oversold"]},
    {"title": "Low volatility regimes favor trend following", "description": "Regime-dependent strategy performance", "keywords": ["volatility", "regime"]},
]


async def seed_database():
    async with async_session() as session:
        for s in SEED_STRATEGIES:
            existing = await session.get(Strategy, s["name"])
            if not existing:
                session.add(Strategy(**s))
        for h in SEED_HYPOTHESES:
            session.add(Hypothesis(**h))
        await session.commit()
    logger.info("database_seeded", strategies=len(SEED_STRATEGIES), hypotheses=len(SEED_HYPOTHESES))
