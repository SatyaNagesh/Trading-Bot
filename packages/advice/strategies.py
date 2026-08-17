"""Indicator-based advisory strategies.

Each adopted strategy reads a symbol's full bar history and decides whether a
fresh bullish setup exists RIGHT NOW. If it does, it emits an analysis dict with
an indicator-derived expected (target) price and stop, plus expected/risk returns.

All ideas are LONG-only (the paper engine cannot short).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from packages.advice.company_map import company_for
from packages.domain.models import Bar
from packages.indicators.api import atr, ema, macd, rsi, sma


@dataclass
class Analysis:
    symbol: str
    company_name: str
    sector: str
    strategy: str
    reason: str
    indicators: list[str]
    current_price: float
    expected_price: float
    stop_price: float
    expected_return_pct: float
    downside_pct: float
    confidence: float
    risk_reward: float
    # internal signal strength, used for ranking only
    signals: dict = field(default_factory=dict)


def _series(bars: list[Bar]) -> tuple[pd.Series, pd.Series, pd.Series]:
    close = pd.Series([float(b.close) for b in bars], dtype=float)
    high = pd.Series([float(b.high) for b in bars], dtype=float)
    low = pd.Series([float(b.low) for b in bars], dtype=float)
    return close, high, low


def _f(x: float) -> float | None:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    return float(x)


def _base(symbol: str, last: float) -> tuple[str, str]:
    comp = company_for(symbol)
    return comp["name"], comp["sector"]


def _finalize(symbol: str, strategy: str, last: float, atr_v: float,
              reason: str, indicators: list[str], k_t: float, k_s: float,
              confidence_bump: float = 0.0) -> Analysis:
    name, sector = _base(symbol, last)
    target = last + atr_v * k_t
    stop = max(0.05, last - atr_v * k_s)
    expected_return_pct = (target - last) / last * 100
    downside_pct = (last - stop) / last * 100
    confidence = max(0.5, min(0.95, 0.6 + confidence_bump))
    risk_reward = (expected_return_pct / downside_pct) if downside_pct > 0 else 0.0
    return Analysis(
        symbol=symbol, company_name=name, sector=sector, strategy=strategy,
        reason=reason, indicators=indicators, current_price=last,
        expected_price=round(target, 2), stop_price=round(stop, 2),
        expected_return_pct=round(expected_return_pct, 2),
        downside_pct=round(downside_pct, 2), confidence=round(confidence, 2),
        risk_reward=round(risk_reward, 2),
        signals={"atr": atr_v, "target": target, "stop": stop},
    )


def sma_golden_cross(bars: list[Bar], fast: int = 20, slow: int = 50) -> Analysis | None:
    if len(bars) < slow + 2:
        return None
    close, _, _ = _series(bars)
    f, s = sma(close, fast), sma(close, slow)
    if pd.isna(f.iloc[-1]) or pd.isna(s.iloc[-1]):
        return None
    if not (f.iloc[-1] > s.iloc[-1]):  # persistent bullish alignment (trending)
        return None
    last = float(close.iloc[-1])
    atr_v = _atr(bars)
    return _finalize(symbol=bars[-1].symbol, strategy="SMA Golden Cross",
                     last=last, atr_v=atr_v, k_t=1.5, k_s=1.0,
                     reason=f"Fast SMA({fast}) above Slow SMA({slow}) — up trend",
                     indicators=["sma", "trend"])


def _atr(bars: list[Bar]) -> float:
    close, high, low = _series(bars)
    return float(atr(high, low, close, period=14).iloc[-1])


def rsi_oversold_rebound(bars: list[Bar], period: int = 14, threshold: float = 32.0) -> Analysis | None:
    if len(bars) < period + 2:
        return None
    close, _, _ = _series(bars)
    r = rsi(close, period)
    if pd.isna(r.iloc[-1]):
        return None
    val = float(r.iloc[-1])
    if val >= threshold:
        return None
    last = float(close.iloc[-1])
    depth = (threshold - val) / threshold
    return _finalize(symbol=bars[-1].symbol, strategy="RSI Oversold Rebound",
                     last=last, atr_v=_atr(bars), k_t=2.0, k_s=1.2,
                     reason=f"RSI({period}) = {val:.0f}, oversold & mean-reverting",
                     indicators=["rsi", "mean_reversion"], confidence_bump=min(0.2, depth * 0.3))


def macd_bullish_cross(bars: list[Bar]) -> Analysis | None:
    if len(bars) < 35:
        return None
    close, _, _ = _series(bars)
    df = macd(close)
    line, sig = df["macd"], df["signal"]
    if len(line) < 3 or pd.isna(line.iloc[-1]) or pd.isna(sig.iloc[-1]):
        return None
    if not (line.iloc[-1] > sig.iloc[-1]):  # persistent bullish alignment
        return None
    last = float(close.iloc[-1])
    return _finalize(symbol=bars[-1].symbol, strategy="MACD Bullish Cross",
                     last=last, atr_v=_atr(bars), k_t=1.5, k_s=1.0,
                     reason="MACD line above its signal line — bullish momentum",
                     indicators=["macd", "trend"], confidence_bump=0.05)


def momentum_surge(bars: list[Bar], roc_lookback: int = 5, roc_min: float = 1.5) -> Analysis | None:
    if len(bars) < roc_lookback + 21:
        return None
    close, _, _ = _series(bars)
    e = ema(close, 20)
    if pd.isna(e.iloc[-1]):
        return None
    prev = float(close.iloc[-(roc_lookback + 1)])
    roc = (float(close.iloc[-1]) - prev) / prev * 100
    if roc < roc_min or float(close.iloc[-1]) <= float(e.iloc[-1]):
        return None
    last = float(close.iloc[-1])
    return _finalize(symbol=bars[-1].symbol, strategy="Momentum Surge",
                     last=last, atr_v=_atr(bars), k_t=1.2, k_s=1.0,
                     reason=f"ROC({roc_lookback}) = {roc:.1f}% above EMA(20)",
                     indicators=["roc", "ema", "momentum"],
                     confidence_bump=min(0.15, roc / 15.0))


ADOPTED_STRATEGIES = {
    "sma_golden_cross": sma_golden_cross,
    "rsi_oversold_rebound": rsi_oversold_rebound,
    "macd_bullish_cross": macd_bullish_cross,
    "momentum_surge": momentum_surge,
}


def scan_symbol(bars: list[Bar]) -> list[Analysis]:
    """Run every adopted strategy over one symbol; return qualified bullish setups."""
    if not bars:
        return []
    out = []
    for fn in ADOPTED_STRATEGIES.values():
        try:
            a = fn(bars)
        except Exception:
            a = None
        if a is not None:
            out.append(a)
    return out