"""autonomous_momentum baseline (unchanged) — reconstructed decision path.

There is **no Python implementation** of ``autonomous_momentum`` in this
repository (verified by git/grep); it is registry-only
(``data/strategies.json``: active, trend, params ``{}``) plus an audit
document. To compare candidates fairly, the baseline is reconstructed here
exactly as documented in ``reports/AUTONOMOUS_MOMENTUM_PERFORMANCE_AUDIT_2026-09-04.md``
and run through the **same** tournament execution + cost model:

  1. regime from the (now frequency-aware) RegimeObserver — causal
  2. momentum  = (close_T - close_{T-5}) / close_{T-5}
  3. confidence = clamp(0.60 + min(momentum, 0.30), 0, 1)
  4. round-trip HARDFULLY: LONG only when flat & momentum>0 ;
     exit (SHORT) when held & momentum<0
  5. gate via the live SignalOptimizer: regime-compatibility
     (trend_following compatible regimes) + min_confidence

The baseline's **trading logic is NOT modified** by this task; only the shared
regime-frequency fix (Phase 1) applies to its regime detection.
"""

from __future__ import annotations

import pandas as pd

from packages.research.strategy import BaseStrategy

TREND_COMPATIBLE = {"trending", "breakout", "low_volatility"}
MIN_CONFIDENCE = 0.55
CONFIDENCE_FLOOR = 0.60
MOMENTUM_CAP = 0.30


class AutonomousMomentumBaseline(BaseStrategy):
    """The unchanged ``autonomous_momentum`` decision path, tournament-ready."""

    def __init__(self, momentum_window: int = 5):
        super().__init__(name="autonomous_momentum",
                         params=dict(momentum_window=momentum_window))

    def features_used(self):
        return ["close", "regime_label"]

    def describe(self):
        return ("long only when flat & momentum(5)>0; exit when held & momentum<0; "
                "confidence=0.60+min(mom,0.30); regime-gated (trend_following)")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        close = f["close"]
        win = self.params["momentum_window"]
        momentum = close.pct_change(win)
        regime = f.get("regime_label")
        # regime gate: LONG accepted only in trend_following-compatible regimes
        if regime is not None:
            compatibility = f["regime_compat"].fillna(0.0)
        else:
            compatibility = pd.Series(1.0, index=f.index)
        long_sig = ((momentum > 0) & (compatibility >= 1.0)).astype(float)
        exit_sig = ((momentum < 0)).astype(float)
        pos = pd.Series(0.0, index=f.index)
        state = 0.0
        for i in f.index:
            if state == 0.0 and long_sig.loc[i] == 1.0:
                state = 1.0
            elif state == 1.0 and exit_sig.loc[i] == 1.0:
                state = 0.0
            pos.loc[i] = state
        return pos


def add_regime_compat(feat: pd.DataFrame) -> pd.DataFrame:
    """Attach a regime-compatibility mask column for the baseline.

    +1 when the regime label is in the trend_following compatible set
    (trending / breakout / low_volatility) or unknown (passes the gate as in
    the live SignalOptimizer), else 0.
    """
    if "regime_label" not in feat:
        return feat
    compat = feat["regime_label"].map(
        lambda r: 1.0 if (r in TREND_COMPATIBLE or r == "unknown") else 0.0
    ).astype(float)
    feat["regime_compat"] = compat
    return feat