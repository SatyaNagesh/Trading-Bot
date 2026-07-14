"""Technical indicators for QuantLab AI."""

import numpy as np
import pandas as pd


def sma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return data.rolling(window=period).mean()


def ema(data: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return data.ewm(span=period, adjust=False).mean()


def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD indicator."""
    fast_ema = ema(data, fast)
    slow_ema = ema(data, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    })


def bb(data: pd.Series, period: int = 20, std: int = 2) -> pd.DataFrame:
    """Bollinger Bands."""
    middle = sma(data, period)
    rolling_std = data.rolling(window=period).std()
    upper = middle + (rolling_std * std)
    lower = middle - (rolling_std * std)
    bandwidth = (upper - lower) / middle * 100
    return pd.DataFrame({
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
    })


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def wma(data: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average."""
    weights = np.arange(1, period + 1)
    def _wma(arr):
        return np.dot(arr, weights) / weights.sum()
    return data.rolling(window=period).apply(_wma, raw=True)


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3
) -> pd.DataFrame:
    """Stochastic Oscillator."""
    low_min = low.rolling(window=k_period).min()
    high_max = high.rolling(window=k_period).max()
    k = 100 * ((close - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    return pd.DataFrame({"k": k, "d": d})


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    price_change = close.diff()
    direction = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
    return (direction * volume).cumsum()


def compute_all(
    close: pd.Series,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    volume: pd.Series | None = None,
) -> pd.DataFrame:
    """Pre-compute all common indicators into a single DataFrame.

    Call once before a backtest instead of recomputing per bar.
    """
    result = pd.DataFrame(index=close.index)
    result["sma_20"] = sma(close, 20)
    result["sma_50"] = sma(close, 50)
    result["sma_200"] = sma(close, 200)
    result["ema_12"] = ema(close, 12)
    result["ema_26"] = ema(close, 26)
    rsi_vals = rsi(close)
    result["rsi"] = rsi_vals
    macd_vals = macd(close)
    result["macd"] = macd_vals["macd"]
    result["macd_signal"] = macd_vals["signal"]
    result["macd_hist"] = macd_vals["histogram"]
    bb_vals = bb(close)
    result["bb_upper"] = bb_vals["upper"]
    result["bb_lower"] = bb_vals["lower"]
    result["bb_width"] = bb_vals["bandwidth"]
    if high is not None and low is not None:
        result["atr"] = atr(high, low, close)
        stoch = stochastic(high, low, close)
        result["stoch_k"] = stoch["k"]
        result["stoch_d"] = stoch["d"]
    if volume is not None:
        result["obv"] = obv(close, volume)
    return result
