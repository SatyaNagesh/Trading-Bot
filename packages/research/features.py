"""Causal feature computation for the strategy research tournament.

All indicators here are **causal**: the value at index ``t`` depends only on
data at-or-before ``t`` (rolling / ewm / expanding windows). No future bar is
ever referenced, so features can feed a no-look-ahead backtest.

The convention is to work on a pandas DataFrame indexed by timestamp with
columns ``open, high, low, close, volume``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line}
    )


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Average Directional Index (Wilder). Causal."""
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0), index=high.index
    )
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr_w = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx_val


def roc(close: pd.Series, period: int) -> pd.Series:
    """Rate of change (momentum) over ``period`` bars: (close_t/close_{t-p}) - 1."""
    return close.pct_change(period)


def bollinger(close: pd.Series, period: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower,
                         "z": (close - mid) / std.replace(0, np.nan)})


def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> pd.DataFrame:
    """Donchian channel: rolling period high/low (look-back)."""
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    mid = (upper + lower) / 2
    return pd.DataFrame({"upper": upper, "lower": lower, "mid": mid})


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
         rolling: int | None = None) -> pd.Series:
    """Typical-price volume weighted average price.

    Uses a cumulative/rolling VWAP. If ``rolling`` is None it is a running VWAP
    from the start of the series (session VWAP, causal). Otherwise it is a
    rolling window VWAP (also causal).
    """
    typical = (high + low + close) / 3.0
    pv = typical * volume
    if rolling is None:
        cumpv = pv.cumsum()
        cumvol = volume.cumsum()
    else:
        cumpv = pv.rolling(rolling).sum()
        cumvol = volume.rolling(rolling).sum()
    return cumpv / cumvol.replace(0, np.nan)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the full causal feature set used by all tournament candidates.

    Returns a DataFrame aligned to ``df.index`` with only causally-known values
    (columns are ``nan`` for the warm-up period of each indicator).
    """
    o = df["open"]
    h = df["high"]
    l = df["low"]
    c = df["close"]
    v = df["volume"].astype(float)

    feat = pd.DataFrame(index=df.index)
    feat["ema_fast"] = ema(c, 20)
    feat["ema_slow"] = ema(c, 50)
    feat["sma_20"] = sma(c, 20)
    feat["rsi"] = rsi(c, 14)
    macd_df = macd(c, 12, 26, 9)
    feat["macd"] = macd_df["macd"]
    feat["macd_signal"] = macd_df["signal"]
    feat["macd_hist"] = macd_df["hist"]
    feat["roc_5"] = roc(c, 5)
    feat["roc_10"] = roc(c, 10)
    feat["atr"] = atr(h, l, c, 14)
    feat["atr_pct"] = feat["atr"] / c.replace(0, np.nan)
    feat["adx"] = adx(h, l, c, 14)
    bb_df = bollinger(c, 20, 2.0)
    feat["bb_z"] = bb_df["z"]
    feat["bb_mid"] = bb_df["mid"]
    feat["bb_upper"] = bb_df["upper"]
    feat["bb_lower"] = bb_df["lower"]
    dc = donchian(h, l, 20)
    feat["dc_upper"] = dc["upper"]
    feat["dc_lower"] = dc["lower"]
    feat["dc_mid"] = dc["mid"]
    feat["vwap"] = vwap(h, l, c, v)
    # volume confirmation: current/avg volume ratio (causal)
    feat["vol_ma20"] = v.rolling(20).mean()
    feat["vol_ratio"] = v / feat["vol_ma20"].replace(0, np.nan)
    feat["close"] = c
    feat["high"] = h
    feat["low"] = l
    feat["open"] = o
    return feat
