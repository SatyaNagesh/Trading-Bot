"""Bar-frequency metadata and annualization helpers.

Central source of truth for how many bars make up a NSE trading day at each
timeframe and the correct volatility-annualization multiplier. Both
:class:`RegimeObserver` (frequency-aware regime) and the research framework use
this so that every consumer scales intraday statistics identically.

NSE equity cash session is 09:15-15:15 IST (360 minutes) on a normal day.
"""

from __future__ import annotations

from typing import Literal, Union

# NSE cash: 09:15-15:15 IST = 360 minutes = 75 five-min bars = 25 fifteen-min bars
TRADING_MINUTES_PER_DAY = 360

Frequency = Literal["1m", "5m", "15m", "1h", "1d"]

# bars that make up one trading day per frequency
_PERIODS_PER_DAY: dict[Frequency, int] = {
    "1m": 360,
    "5m": 72,   # 360/5
    "15m": 24,  # 360/15
    "1h": 6,
    "1d": 1,
}


def periods_per_day(freq: Frequency | str) -> int:
    """Return the number of ``freq`` bars per trading day.

    Falls back to 1 (daily) for any unrecognised frequency so that legacy daily
    behaviour is preserved instead of erroring.
    """
    return _PERIODS_PER_DAY.get(freq, 1)


def annualized_multiplier(freq: Frequency | str) -> float:
    """Return ``sqrt(252 * bars_per_day)`` used to annualise per-bar volatility.

    For daily this is the legacy ``sqrt(252)``.
    """
    import math

    return math.sqrt(252 * periods_per_day(freq))


def infer_frequency(timestamps) -> Frequency:
    """Best-effort infer frequency from a sorted series of timestamps.

    Returns "1d" when all bars sit at midnight / have a single bar per day.
    """
    import numpy as np

    ts = list(timestamps)
    if len(ts) < 2:
        return "1d"
    # median gap in minutes
    gaps = []
    for a, b in zip(ts[:-1], ts[1:]):
        gap_min = (b - a).total_seconds() / 60.0
        if gap_min > 0:
            gaps.append(gap_min)
    if not gaps:
        return "1d"
    med = float(np.median(gaps))
    if med >= 12 * 60:  # whole days
        return "1d"
    if med <= 1.5:
        return "1m"
    if med <= 3:
        return "5m"
    if med <= 7.5:
        return "15m"
    if med <= 90:
        return "1h"
    return "1d"
