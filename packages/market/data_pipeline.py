"""NSE market data pipeline with yfinance and cache layer."""

import asyncio
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from packages.domain.models import Bar
from packages.core.exceptions import DataError, DataQualityError
from packages.core.logging import get_logger

logger = get_logger("data_pipeline")

CACHE_DIR = Path("data/cache/parquet")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NSE_SUFFIX = ".NS"
DEFAULT_TIMEOUT = 30


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.replace('.', '_')}.parquet"


async def fetch_bars(
    symbol: str,
    start: date,
    end: date,
    use_cache: bool = True,
) -> list[Bar]:
    full_symbol = symbol if symbol.endswith(NSE_SUFFIX) else symbol + NSE_SUFFIX

    if use_cache:
        cached = _load_from_cache(symbol, start, end)
        if cached:
            return cached

    df = await asyncio.to_thread(_download_from_yahoo, full_symbol, start, end)
    bars = _dataframe_to_bars(df, symbol)

    if use_cache:
        _save_to_cache(symbol, df)

    return bars


def _download_from_yahoo(symbol: str, start: date, end: date) -> pd.DataFrame:
    logger.info("fetching_data", symbol=symbol, start=str(start), end=str(end))
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=True)
    except Exception as e:
        raise DataError(f"Failed to fetch {symbol}: {e}") from e

    if df.empty:
        raise DataError(f"No data returned for {symbol}")

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df.columns = [c.lower() for c in df.columns]
    return df


def _dataframe_to_bars(df: pd.DataFrame, symbol: str) -> list[Bar]:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise DataQualityError(f"Missing columns: {missing}")

    timestamps = df.index.to_pydatetime()
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    volumes = df["volume"].values

    bars = [
        Bar(
            timestamp=timestamps[i],
            open=Decimal(str(opens[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(closes[i])),
            volume=int(volumes[i]),
            symbol=symbol,
        )
        for i in range(len(df))
    ]

    if not bars:
        raise DataQualityError(f"No valid bars after conversion for {symbol}")

    return bars


def _load_from_cache(symbol: str, start: date, end: date) -> list[Bar] | None:
    path = _cache_path(symbol)
    if not path.exists():
        return None

    try:
        df = _load_parquet_range(path, start, end)
        if df.empty:
            return None
        logger.info("cache_hit", symbol=symbol, rows=len(df))
        return _dataframe_to_bars(df, symbol)
    except Exception as e:
        logger.warning("cache_read_failed", symbol=symbol, error=str(e))
        return None


def _load_parquet_range(path: Path, start: date, end: date) -> pd.DataFrame:
    try:
        return pd.read_parquet(path, filters=[
            ("index", ">=", str(start)),
            ("index", "<=", str(end)),
        ])
    except (TypeError, ValueError):
        df = pd.read_parquet(path)
        return df[(df.index >= str(start)) & (df.index <= str(end))]


def _save_to_cache(symbol: str, df: pd.DataFrame) -> None:
    path = _cache_path(symbol)
    try:
        df.to_parquet(path)
        logger.info("cache_saved", symbol=symbol, path=str(path))
    except Exception as e:
        logger.warning("cache_write_failed", symbol=symbol, error=str(e))


def get_available_symbols() -> list[str]:
    nifty50 = [  # TODO: load from config/API in V1
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
        "BAJFINANCE", "LT", "WIPRO", "AXISBANK", "TITAN",
        "ASIANPAINT", "MARUTI", "SUNPHARMA", "TATAMOTORS", "NTPC",
        "ONGC", "POWERGRID", "BAJAJFINSV", "JSWSTEEL", "HCLTECH",
        "ULTRACEMCO", "INDUSINDBK", "NESTLEIND", "M&M", "TATASTEEL",
        "TECHM", "HDFCLIFE", "SBILIFE", "DRREDDY", "CIPLA",
        "BAJAJ_AUTO", "DIVISLAB", "GRASIM", "EICHERMOT", "BRITANNIA",
        "TRENT", "APOLLOHOSP", "BPCL", "ADANIPORTS", "COALINDIA",
        "HINDALCO", "ADANIENT", "HEROMOTOCO", "BEL", "SHRIRAMFIN",
    ]
    return sorted(nifty50)
