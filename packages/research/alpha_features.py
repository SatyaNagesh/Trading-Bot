"""Alpha discovery - causal feature library.

Every feature here is **strictly causal**: its value at timestamp ``t`` is a
function only of data at-or-before ``t`` (rolling / ewm / percentile windows).
No forward-looking bar is referenced by any feature. Labels (forward returns)
are computed separately by ``alpha_dataset``.

Feature count is deliberately small (~22) and each one has an explicit
definition, lookback and economic rationale. We are testing hypotheses about
predictive power, not fitting indicators.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from packages.research.features import (
    atr,
    bollinger,
    ema,
    macd,
    roc,
    rsi,
    sma,
    vwap,
)

FEATURES: list[dict] = [
    # --- Trend ---
    {"key": "trend_sma20_gap", "category": "trend",
     "definition": "close / SMA(close,20) - 1",
     "lookback": 20,
     "rationale": "Distance of price from the 20-day trend centre; classical trend-following anchor."},
    {"key": "trend_ema10_gap", "category": "trend",
     "definition": "close / EMA(close,10) - 1",
     "lookback": 10,
     "rationale": "Faster trend-state gauge; responds earlier than SMA20 to direction change."},
    {"key": "trend_sma20_slope5", "category": "trend",
     "definition": "SMA20_t / SMA20_{t-5} - 1",
     "lookback": 25,
     "rationale": "5-day slope of the 20-day average — trend momentum without price noise."},
    {"key": "trend_strength_20v50", "category": "trend",
     "definition": "SMA(close,20) / SMA(close,50) - 1",
     "lookback": 50,
     "rationale": "Fast-vs-slow average alignment; trend strength/regime proxy."},
    # --- Momentum ---
    {"key": "mom_roc20", "category": "momentum",
     "definition": "close_t / close_{t-20} - 1",
     "lookback": 20,
     "rationale": "20-day rate of change; the canonical medium-horizon momentum signal."},
    {"key": "mom_rsi14", "category": "momentum",
     "definition": "RSI(14) using Wilder-style smoothed gain/loss",
     "lookback": 14,
     "rationale": "Overbought/oversold momentum gauge; tests mean-reversion vs continuation stories."},
    {"key": "mom_macd_hist_norm", "category": "momentum",
     "definition": "(MACD(12,26) - signal(9)) / close",
     "lookback": 35,
     "rationale": "Normalized MACD histogram — momentum with trend crossovers, scale-free."},
    # --- Volatility ---
    {"key": "vol_atr_pct", "category": "volatility",
     "definition": "ATR(14) / close",
     "lookback": 14,
     "rationale": "Per-unit-price daily range; volatility adjusted for price level."},
    {"key": "vol_realized20", "category": "volatility",
     "definition": "std(daily log return, 20)",
     "lookback": 20,
     "rationale": "Realized volatility; tests whether low/high vol precedes returns."},
    {"key": "vol_pctile_252", "category": "volatility",
     "definition": "ranking percentile of realized20 within trailing 252 bars",
     "lookback": 252,
     "rationale": "Cyclical volatility position — distinguishes quiet-from-normal vs extreme-vol episodes."},
    # --- Volume ---
    {"key": "vol_rel20", "category": "volume",
     "definition": "volume_t / SMA(volume,20)",
     "lookback": 20,
     "rationale": "Relative volume; spike/quiet detection often precedes moves."},
    {"key": "vol_trend_10v50", "category": "volume",
     "definition": "SMA(volume,10) / SMA(volume,50) - 1",
     "lookback": 50,
     "rationale": "Volume trend — accumulation/distribution regime."},
    {"key": "vol_price_corr20", "category": "volume",
     "definition": "rolling Pearson corr(return, log volume, 20)",
     "lookback": 20,
     "rationale": "Price-volume relationship; trend-confirmed vs diverging moves."},
    # --- Price structure ---
    {"key": "struct_breakout20", "category": "price_structure",
     "definition": "close / max(high, 20) - 1",
     "lookback": 20,
     "rationale": "Distance below recent 20-day high (<=0); breakout proximity."},
    {"key": "struct_lowdist20", "category": "price_structure",
     "definition": "close / min(low, 20) - 1",
     "lookback": 20,
     "rationale": "Distance above recent 20-day low (>=0); support proximity."},
    {"key": "struct_bb_z20", "category": "price_structure",
     "definition": "(close - SMA20) / std(close,20)",
     "lookback": 20,
     "rationale": "Normalized distance from the 20-day mean (Bollinger z) — mean-reversion distance gauge."},
    {"key": "struct_vwap_gap20", "category": "price_structure",
     "definition": "close / rolling20 VWAP(typical-price^vol) - 1",
     "lookback": 20,
     "rationale": "Distance from 20-bar VWAP anchor (daily proxy; session VWAP unavailable on daily bars)."},
    # --- Cross-sectional ---
    {"key": "xs_rel_str20", "category": "cross_sectional",
     "definition": "cross-sectional z-score of (close/SMA20-1) across universe at date t",
     "lookback": 20,
     "rationale": "Relative strength within the NIFTY-50 universe; tests cross-sectional ranking alpha."},
    {"key": "xs_mom_rank20", "category": "cross_sectional",
     "definition": "cross-sectional percentile rank of ROC20 across universe at date t",
     "lookback": 20,
     "rationale": "Cross-sectional momentum rank — classic long/short ranking variable."},
    # --- Market context ---
    {"key": "mkt_ret_5d", "category": "market_context",
     "definition": "equal-weight universe index 5-day return up to t",
     "lookback": 5,
     "rationale": "Broad-market short-term return; controls for beta/trend-driven future returns."},
    {"key": "mkt_vol_20", "category": "market_context",
     "definition": "std of equal-weight index daily returns, 20d",
     "lookback": 20,
     "rationale": "Market-wide volatility; regime gauge for the whole cross-section."},
]

FEATURE_KEYS: list[str] = [f["key"] for f in FEATURES]

# categorical conditioning variables (not scored for IC, but used to slice)
REGIME_LIST = [
    "trending", "breakout", "sideways", "low_volatility",
    "mean_reverting", "high_volatility", "volatile", "crisis", "unknown",
]


def _trailing_pctile(series: pd.Series, window: int = 252) -> pd.Series:
    """Percentile rank of the current value within the trailing ``window`` (causal)."""
    return series.rolling(window).apply(
        lambda x: float(np.mean(x <= x[-1])), raw=True
    )


def compute_symbol_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all causal per-symbol features for one symbol's daily frame.

    ``df`` must be indexed by timestamp with ``open/high/low/close/volume``.
    Returns only the feature columns (values are NaN during each indicator's
    warm-up period).
    """
    h: pd.Series = df["high"]
    l: pd.Series = df["low"]
    c: pd.Series = df["close"]
    v: pd.Series = df["volume"].astype(float)

    ret = c.pct_change()
    s20 = sma(c, 20)
    e10 = ema(c, 10)
    s50 = sma(c, 50)
    rv20 = ret.rolling(20).std()
    macd_df = macd(c, 12, 26, 9)
    bb = bollinger(c, 20, 2.0)
    vwap20 = vwap(h, l, c, v, rolling=20)
    vol_s10 = v.rolling(10).mean()
    vol_s50 = v.rolling(50).mean()
    lvol = np.log(v.replace(0, np.nan))

    feat = pd.DataFrame(index=df.index)
    feat["trend_sma20_gap"] = c / s20 - 1
    feat["trend_ema10_gap"] = c / e10 - 1
    feat["trend_sma20_slope5"] = s20 / s20.shift(5) - 1
    feat["trend_strength_20v50"] = s20 / s50 - 1
    feat["mom_roc20"] = roc(c, 20)
    feat["mom_rsi14"] = rsi(c, 14)
    feat["mom_macd_hist_norm"] = macd_df["hist"] / c
    feat["vol_atr_pct"] = atr(h, l, c, 14) / c
    feat["vol_realized20"] = rv20
    feat["vol_pctile_252"] = _trailing_pctile(rv20, 252)
    feat["vol_rel20"] = v / sma(v, 20)
    feat["vol_trend_10v50"] = vol_s10 / vol_s50 - 1
    feat["vol_price_corr20"] = ret.rolling(20).corr(lvol)
    feat["struct_breakout20"] = c / h.rolling(20).max() - 1
    feat["struct_lowdist20"] = c / l.rolling(20).min() - 1
    feat["struct_bb_z20"] = bb["z"]
    feat["struct_vwap_gap20"] = c / vwap20 - 1
    # cross-sectional and market-context features are added in the panel builder
    return feat