"""Tournament strategy candidates (A-E).

Per Phase 4 each candidate uses a **small, economically/technically justified**
feature set — no 20-indicator stacks, no arbitrary threshold flooding. Each
class documents the exact rule it trades and the features it consumes. All
candidates are causal and are executed through the same :mod:`execution` model.
"""

from __future__ import annotations

import pandas as pd

from packages.research.strategy import BaseStrategy


class TrendFollowingA(BaseStrategy):
    """A — TREND FOLLOWING.

    Rule (long/flat):
      LONG when   EMA(20) > EMA(50)
                  and ADX(14) >= 20        (trend has structure, not chop)
                  and ATR% > 0             (price is actually moving)
                  and vol_ratio >= 1.0     (volume confirms the move)
      FLAT  when  EMA(20) <= EMA(50)  or  ADX(14) < 18  (trend broken / exhausted)
    """

    def __init__(self, ema_fast: int = 20, ema_slow: int = 50,
                 adx_min: float = 20.0, adx_exit: float = 18.0):
        super().__init__(
            name="A_trend_following",
            params=dict(ema_fast=ema_fast, ema_slow=ema_slow,
                        adx_min=adx_min, adx_exit=adx_exit),
        )

    def features_used(self):
        return ["ema_fast", "ema_slow", "adx", "atr_pct", "vol_ratio"]

    def describe(self):
        return ("long EMA20>EMA50 & ADX>=20 & ATR>0 & vol_ratio>=1; "
                "flat when EMA20<=EMA50 or ADX<18")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        ema_fast = f.get("ema_fast")
        ema_slow = f.get("ema_slow")
        adx = f.get("adx")
        atr_pct = f.get("atr_pct")
        vol = f.get("vol_ratio")
        up = (ema_fast > ema_slow).astype(float)
        trend_on = (adx >= self.params["adx_min"]).astype(float)
        trend_off = (adx < self.params["adx_exit"]).astype(float)
        active = (atr_pct > 0).astype(float)
        volconf = vol.fillna(1.0) >= 1.0
        long_sig = up * trend_on * active * volconf.astype(float)
        pos = pd.Series(index=f.index, dtype=float)
        pos[:] = 0.0
        state = 0.0
        for i in f.index:
            if long_sig.loc[i] == 1.0 and state == 0.0:
                state = 1.0
            elif state == 1.0 and (up.loc[i] == 0.0 or trend_off.loc[i] == 1.0):
                state = 0.0
            pos.loc[i] = state
        return pos


class MomentumB(BaseStrategy):
    """B — MOMENTUM.

    Rule (long / short / flat):
      LONG  when RSI(14) between 50 and 70  and MACD-hist > 0  and ROC(5) > 0
      SHORT when RSI(14) between 30 and 50  and MACD-hist < 0  and ROC(5) < 0
      FLAT  when RSI exits (50,70)/(30,50), histogram flips, or ROC flips sign.
    """

    def __init__(self, rsi_period: int = 14, rsi_hi: float = 70.0,
                 rsi_lo: float = 30.0, roc_period: int = 5):
        super().__init__(
            name="B_momentum",
            params=dict(rsi_period=rsi_period, rsi_hi=rsi_hi,
                        rsi_lo=rsi_lo, roc_period=roc_period),
        )

    def features_used(self):
        return ["rsi", "macd_hist", "roc_5"]

    def describe(self):
        return ("long RSI in (50,70)&MACD-h>0&ROC5>0; short RSI in (30,50)"
                "&MACD-h<0&ROC5<0; flat on reversal")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        rsi = f.get("rsi")
        hist = f.get("macd_hist")
        roc = f.get("roc_5")
        hi = self.params["rsi_hi"]
        lo = self.params["rsi_lo"]
        long_zone = (rsi > 50) & (rsi < hi)
        short_zone = (rsi < 50) & (rsi > lo)
        long_sig = (long_zone & (hist > 0) & (roc > 0)).astype(float)
        short_sig = (short_zone & (hist < 0) & (roc < 0)).astype(float)
        # flat triggers
        flat_long = (rsi >= hi) | (hist < 0) | (roc < 0)
        flat_short = (rsi <= lo) | (hist > 0) | (roc > 0)
        pos = pd.Series(0.0, index=f.index)
        state = 0.0
        for i in f.index:
            if state == 0.0:
                if long_sig.loc[i] == 1.0:
                    state = 1.0
                elif short_sig.loc[i] == 1.0:
                    state = -1.0
            elif state == 1.0:
                if flat_long.loc[i]:
                    state = 0.0
                elif short_sig.loc[i] == 1.0:
                    state = -1.0
            elif state == -1.0:
                if flat_short.loc[i]:
                    state = 0.0
                elif long_sig.loc[i] == 1.0:
                    state = 1.0
            pos.loc[i] = state
        return pos


class BreakoutC(BaseStrategy):
    """C — BREAKOUT.

    Rule (long/flat):
      LONG when  close > Donchian(20) upper (prior high)
                 and ATR% above low-vol floor          (real breakout, not chop)
                 and vol_ratio >= 1.1                  (volume confirms)
                 and EMA(50) slope > 0 (higher-timeframe trend confirm)
      FLAT when  close < Donchian mid  or  EMA(50) slope <= 0
    """

    def __init__(self, period: int = 20, vol_floor: float = 0.005,
                 vol_ratio_min: float = 1.1):
        super().__init__(
            name="C_breakout",
            params=dict(period=period, vol_floor=vol_floor,
                        vol_ratio_min=vol_ratio_min),
        )

    def features_used(self):
        return ["dc_upper", "dc_mid", "atr_pct", "vol_ratio", "ema_slow", "close"]

    def describe(self):
        return ("long close>Donchian20 high & ATR%>floor & vol_ratio>=1.1 & "
                "EMA50 slope>0; flat when close<Donchian mid or slope<=0")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        close = f["close"]
        up = f["dc_upper"]
        mid = f["dc_mid"]
        atr_pct = f["atr_pct"]
        vol = f["vol_ratio"].fillna(1.0)
        ema_slow = f["ema_slow"]
        slope = ema_slow.diff(3)
        trend_up = (slope > 0).astype(float)
        breakout = (close > up).astype(float)
        real_vol = (atr_pct > self.params["vol_floor"]).astype(float)
        volconf = (vol >= self.params["vol_ratio_min"]).astype(float)
        long_sig = breakout * real_vol * volconf * trend_up
        exit_sig = ((close < mid) | (slope <= 0)).astype(float)
        pos = pd.Series(0.0, index=f.index)
        state = 0.0
        for i in f.index:
            if state == 0.0 and long_sig.loc[i] == 1.0:
                state = 1.0
            elif state == 1.0 and exit_sig.loc[i] == 1.0:
                state = 0.0
            pos.loc[i] = state
        return pos


class MeanReversionD(BaseStrategy):
    """D — MEAN REVERSION.

    Rule (long/flat, revert-to-fair-value):
      LONG when  price < Bollinger lower (z <= -2)  and RSI(14) < 30
                 and price < VWAP (washout below fair value)
                 and ATR% < high-vol ceiling (don't catch knives in chaos)
      FLAT when  price > Bollinger mid (z >= 0)  or RSI > 50
    """

    def __init__(self, bb_period: int = 20, n_std: float = 2.0,
                 rsi_lo: float = 30.0, vol_ceil: float = 0.02):
        super().__init__(
            name="D_mean_reversion",
            params=dict(bb_period=bb_period, n_std=n_std, rsi_lo=rsi_lo,
                        vol_ceil=vol_ceil),
        )

    def features_used(self):
        return ["bb_z", "bb_lower", "bb_mid", "rsi", "vwap", "atr_pct", "close"]

    def describe(self):
        return ("long z<=-2 & RSI<30 & price<VWAP & ATR%<ceil; "
                "flat when z>=0 or RSI>50")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        close = f["close"]
        z = f["bb_z"]
        mid = f["bb_mid"]
        rsi = f["rsi"]
        vwap = f["vwap"]
        atr_pct = f["atr_pct"]
        oversold = (z <= -self.params["n_std"]).astype(float)
        rsi_lo_sig = (rsi < self.params["rsi_lo"]).astype(float)
        below_vwap = (close < vwap).astype(float)
        ok_vol = (atr_pct < self.params["vol_ceil"]).astype(float)
        long_sig = oversold * rsi_lo_sig * below_vwap * ok_vol
        exit_sig = ((z >= 0) | (rsi > 50)).astype(float)
        pos = pd.Series(0.0, index=f.index)
        state = 0.0
        for i in f.index:
            if state == 0.0 and long_sig.loc[i] == 1.0:
                state = 1.0
            elif state == 1.0 and exit_sig.loc[i] == 1.0:
                state = 0.0
            pos.loc[i] = state
        return pos


class MultiFactorE(BaseStrategy):
    """E — MULTI-FACTOR.

    Independent evidence from trend, momentum, volatility, volume and regime,
    scored and combined. Each factor is +1/-1/0 (long/bullish, short/bearish,
    neutral). The composite is the sum; we act when enough factors agree.

      trend      : +1 EMA20>EMA50 ; -1 EMA20<EMA50
      momentum   : sign(ROC(10))
      volatility : +1 z>0.5 (expansion up) ; -1 z<-0.5 (expansion down)
      volume     : +1 vol_ratio>1 & up-move ; -1 vol_ratio>1 & down-move
      regime     : +1 in TRENDING/LOW_VOL or BREAKOUT-up; -1 in HIGH_VOL/CRISIS

      LONG  when composite >= +2 ; SHORT when composite <= -2 ; FLAT otherwise.
    """

    def __init__(self, act_threshold: float = 2.0):
        super().__init__(name="E_multi_factor",
                         params=dict(act_threshold=act_threshold))

    def features_used(self):
        return ["ema_fast", "ema_slow", "roc_10", "bb_z", "vol_ratio", "close"]

    def describe(self):
        return ("composite of trend+momentum+volatility+volume+regime factors; "
                "long if>threshold, short if<-threshold")

    def decide(self, f: pd.DataFrame) -> pd.Series:
        feat = f
        trend = pd.Series(0.0, index=f.index)
        trend.loc[feat["ema_fast"] > feat["ema_slow"]] = 1.0
        trend.loc[feat["ema_fast"] < feat["ema_slow"]] = -1.0

        mom = (feat["roc_10"] > 0).astype(float) - (feat["roc_10"] < 0).astype(float)

        z = feat["bb_z"].fillna(0.0)
        vol = pd.Series(0.0, index=f.index)
        vol.loc[z > 0.5] = 1.0
        vol.loc[z < -0.5] = -1.0

        vratio = feat["vol_ratio"].fillna(1.0)
        up_move = (feat["close"].diff() > 0)
        volconf = pd.Series(0.0, index=f.index)
        volconf.loc[(vratio > 1.0) & up_move] = 1.0
        volconf.loc[(vratio > 1.0) & ~up_move] = -1.0

        # regime factor is supplied externally through the 'regime_signal' column
        # if present (set by the tournament harness via the fixed RegimeObserver).
        regime = feat["regime_signal"].fillna(0.0) if "regime_signal" in feat else pd.Series(0.0, index=f.index)

        composite = trend + mom + vol + volconf + regime
        th = self.params["act_threshold"]
        pos = pd.Series(0.0, index=f.index)
        pos.loc[composite >= th] = 1.0
        pos.loc[composite <= -th] = -1.0
        return pos


ALL_CANDIDATES = {
    "A_trend_following": TrendFollowingA,
    "B_momentum": MomentumB,
    "C_breakout": BreakoutC,
    "D_mean_reversion": MeanReversionD,
    "E_multi_factor": MultiFactorE,
}
