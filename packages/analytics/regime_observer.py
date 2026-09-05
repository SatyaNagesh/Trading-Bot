"""Market Regime Observation — continuous regime classification and per-regime analysis."""

from datetime import datetime, timezone
from typing import Any

import numpy as np

from packages.domain.models import MarketRegime


class RegimeObserver:
    """Continuous regime classification with **bar-frequency-aware** annualization.

    .. note::
       The annualization factor used to convert a per-bar volatility into an
       "annualized" volatility MUST depend on how many bars make up a day for
       the *input* frequency. The original implementation hard-coded ``sqrt(252)``
       (i.e. it assumed **daily** bars). Feeding it 1-minute returns therefore
       produced a massively understated annualized volatility (per-minute sigma
       scaled by sqrt(252) instead of sqrt(252 * bars_per_day)), which pushed
       almost every intraday bar into the ultra-low-vol ``SIDEWAYS`` bucket and
       caused trend/momentum strategies to be suppressed. This is the
       "regime-frequency / annualization" distortion.

    The correct scaling for a bar frequency with ``P`` bars per trading day is::

        annualized_vol = std_return * sqrt(252 * P)

    =============  ================  =======================================
    Frequency      periods_per_day   multiplier
    =============  ================  =======================================
    1-minute       375                sqrt(252*375)  ~= 305.9
    5-minute        75                sqrt(252*75)   ~= 136.8
    15-minute       25                sqrt(252*25)   ~=  79.0
    hourly          6.5              sqrt(252*6.5)   ~=  40.5
    daily            1                sqrt(252)      ~=  15.87  (legacy)
    =============  ================  =======================================

    ``periods_per_day`` defaults to ``1`` so existing daily callers are
    unaffected; intraday callers should pass the correct value. The vol/mean
    **ratio** thresholds (``abs(mean) > k*std``) are scale-free and unchanged.
    """

    def __init__(self, lookback: int = 21, periods_per_day: int = 1):
        self.lookback = lookback
        if periods_per_day < 1:
            raise ValueError("periods_per_day must be >= 1")
        self.periods_per_day = periods_per_day
        self._history: list[dict[str, Any]] = []
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN
        self._regime_log: list[dict[str, Any]] = []

    def classify(self, prices: list[float]) -> MarketRegime:
        if len(prices) < self.lookback:
            return MarketRegime.UNKNOWN

        recent = prices[-self.lookback :]
        returns = np.diff(recent) / recent[:-1]
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        annualized_vol = std_return * np.sqrt(252 * self.periods_per_day)

        if annualized_vol > 0.08:
            if abs(mean_return) > 2 * std_return:
                self._current_regime = MarketRegime.CRISIS
            elif abs(mean_return) > std_return:
                self._current_regime = MarketRegime.BREAKOUT
            else:
                self._current_regime = MarketRegime.HIGH_VOLATILITY
        elif annualized_vol < 0.02:
            if abs(mean_return) < 0.001:
                self._current_regime = MarketRegime.SIDEWAYS
            else:
                self._current_regime = MarketRegime.LOW_VOLATILITY
        else:
            if abs(mean_return) > std_return:
                self._current_regime = MarketRegime.TRENDING
            else:
                self._current_regime = MarketRegime.MEAN_REVERTING

        return self._current_regime

    def observe(self, prices: list[float], timestamp: datetime | None = None) -> MarketRegime:
        regime = self.classify(prices)
        entry = {
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "regime": regime.value,
            "price": prices[-1] if prices else None,
        }
        self._regime_log.append(entry)
        self._history.append(entry)
        return regime

    @property
    def current_regime(self) -> MarketRegime:
        return self._current_regime

    def regime_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(reversed(self._regime_log))[:limit]

    def regime_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._regime_log:
            regime = r["regime"]
            counts[regime] = counts.get(regime, 0) + 1
        return counts

    def most_common_regime(self) -> str:
        counts = self.regime_counts()
        if not counts:
            return MarketRegime.UNKNOWN.value
        return max(counts, key=counts.get)


def calculate_regime_performance(
    trades: list,
    regime_history: list[dict[str, Any]],
) -> dict[str, Any]:
    from packages.analytics.engine import TradeAnalytics

    regime_trades: dict[str, list] = {}
    for trade in trades:
        if not hasattr(trade, "exit_time") or trade.exit_time is None:
            continue
        closest_regime = _find_closest_regime(trade.exit_time, regime_history)
        if closest_regime not in regime_trades:
            regime_trades[closest_regime] = []
        regime_trades[closest_regime].append(trade)

    results = {}
    for regime, regime_trade_list in regime_trades.items():
        if regime_trade_list:
            a = TradeAnalytics(regime_trade_list)
            results[regime] = a.summary()
    return results


def _find_closest_regime(trade_time: datetime, regime_history: list[dict[str, Any]]) -> str:
    if not regime_history:
        return MarketRegime.UNKNOWN.value
    closest = regime_history[-1]
    for entry in reversed(regime_history):
        entry_time_str = entry.get("timestamp", "")
        try:
            entry_time = datetime.fromisoformat(entry_time_str)
            if entry_time <= trade_time:
                closest = entry
            else:
                break
        except (ValueError, TypeError):
            continue
    return closest.get("regime", MarketRegime.UNKNOWN.value)
