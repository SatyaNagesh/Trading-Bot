import pandas as pd
import numpy as np


def detect_regime(df: pd.DataFrame, params: dict) -> str:
    if df is None or len(df) < params['trend_lookback']:
        return 'unknown'

    close = df['Close']
    vol_lookback = params['volatility_lookback']
    trend_lookback = params['trend_lookback']
    sideways_thresh = params['sideways_threshold']

    returns = close.pct_change().dropna()
    recent_vol = returns.tail(vol_lookback).std()

    sma_short = close.rolling(window=20).mean()
    sma_long = close.rolling(window=trend_lookback).mean()

    price_vs_sma = ((close.iloc[-1] - sma_long.iloc[-1]) / sma_long.iloc[-1])
    slope = (sma_short.iloc[-1] - sma_short.iloc[-20]) / sma_short.iloc[-20]

    atr = (df['High'] - df['Low']).rolling(window=14).mean()
    atr_pct = (atr.iloc[-1] / close.iloc[-1])

    annual_vol = recent_vol * np.sqrt(252)

    if abs(price_vs_sma) < sideways_thresh and abs(slope) < 0.02:
        return 'sideways'
    elif slope > 0.02 and annual_vol < 0.35:
        return 'bullish_trend'
    elif slope < -0.02 and annual_vol < 0.35:
        return 'bearish_trend'
    elif annual_vol >= 0.35:
        return 'high_volatility'
    else:
        return 'mixed'


def regime_confidence(df: pd.DataFrame, regime: str) -> float:
    close = df['Close']
    sma_long = close.rolling(window=50).mean()

    if regime == 'bullish_trend':
        above_sma = (close > sma_long).sum()
        return min(above_sma / 50, 1.0)
    elif regime == 'bearish_trend':
        below_sma = (close < sma_long).sum()
        return min(below_sma / 50, 1.0)
    elif regime == 'sideways':
        within_range = ((close - sma_long).abs() / sma_long < 0.05).sum()
        return min(within_range / 50, 1.0)
    return 0.5
