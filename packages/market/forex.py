"""Forex data pipeline — currency pair market data."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from packages.core.logging import get_logger
from packages.domain.models import Bar

logger = get_logger("forex_pipeline")

FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/INR", "AUD/USD"]


async def fetch_forex_bars(symbol: str, start: date, end: date) -> list[Bar]:
    try:
        from packages.market.data_pipeline import fetch_bars
        fx_symbol = symbol.replace("/", "").upper()
        bars = await fetch_bars(f"{fx_symbol}=X", start, end)
        for b in bars:
            b.symbol = symbol
        logger.info("forex_fetched", symbol=symbol, bars=len(bars))
        return bars
    except Exception as e:
        logger.warning("forex_fallback", error=str(e))
        return _simulate_forex(symbol, start, end)


def _simulate_forex(symbol: str, start: date, end: date) -> list[Bar]:
    import random
    bars = []
    price = {"EUR/USD": 1.08, "GBP/USD": 1.27, "USD/JPY": 150.0, "USD/INR": 83.0, "AUD/USD": 0.66}.get(symbol, 1.0)
    current = start
    while current <= end:
        change = random.uniform(-0.005, 0.005)
        price *= (1 + change)
        bars.append(Bar(
            timestamp=datetime.combine(current, datetime.min.time(), tzinfo=timezone.utc),
            open=Decimal(str(round(price, 4))),
            high=Decimal(str(round(price * 1.002, 4))),
            low=Decimal(str(round(price * 0.998, 4))),
            close=Decimal(str(round(price, 4))),
            volume=int(random.uniform(10000, 100000)),
            symbol=symbol,
        ))
        current = date.fromordinal(current.toordinal() + 1)
    return bars
