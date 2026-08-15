"""Crypto data pipeline — CCXT integration for cryptocurrency markets."""

from datetime import date, datetime, timezone
from decimal import Decimal

from packages.core.logging import get_logger
from packages.domain.models import Bar

logger = get_logger("crypto_pipeline")

SUPPORTED_EXCHANGES = ["binance", "coinbase", "kraken", "bybit"]
SUPPORTED_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"]


async def fetch_crypto_bars(
    symbol: str,
    start: date,
    end: date,
    exchange: str = "binance",
    interval: str = "1d",
) -> list[Bar]:
    try:
        import ccxt.async_support as ccxt

        ex = getattr(ccxt, exchange)()
        since = int(datetime.combine(start, datetime.min.time()).timestamp() * 1000)
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe=interval, since=since)
        await ex.close()
        bars = []
        for row in ohlcv:
            ts, o, h, low, c, v = row
            bar_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            if bar_date.date() > end:
                break
            bars.append(
                Bar(
                    timestamp=bar_date,
                    open=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(low)),
                    close=Decimal(str(c)),
                    volume=int(v),
                    symbol=symbol,
                )
            )
        logger.info("crypto_fetched", symbol=symbol, bars=len(bars), exchange=exchange)
        return bars
    except ImportError:
        logger.warning("ccxt not installed, returning simulated crypto data")
        return _simulate_crypto(symbol, start, end)
    except Exception as e:
        logger.error("crypto_fetch_failed", error=str(e))
        return []


def _simulate_crypto(symbol: str, start: date, end: date) -> list[Bar]:
    import random

    bars = []
    price = 50000.0
    current = start
    while current <= end:
        change = random.uniform(-0.03, 0.03)
        price *= 1 + change
        bars.append(
            Bar(
                timestamp=datetime.combine(current, datetime.min.time(), tzinfo=timezone.utc),
                open=Decimal(str(round(price, 2))),
                high=Decimal(str(round(price * 1.02, 2))),
                low=Decimal(str(round(price * 0.98, 2))),
                close=Decimal(str(round(price * (1 + random.uniform(-0.01, 0.01)), 2))),
                volume=int(random.uniform(1000, 10000)),
                symbol=symbol,
            )
        )
        current = date.fromordinal(current.toordinal() + 1)
    return bars
