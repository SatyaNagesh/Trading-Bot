#!/usr/bin/env python3
"""Run the strategy research tournament on real historical data.

Evaluates all 5 candidate strategies through the identical, causal,
no-look-ahead execution + cost model, producing:
  * full IS metrics per candidate (intraday Sep-4 + daily)
  * chronological walk-forward OOS
  * regime breakdown
  * Monte Carlo on actual trades
  * cost/slippage stress (Phase 9)
  * parameter-neighborhood robustness (Phase 11)
then writes a single JSON the report generator consumes.

Usage:
  python -m packages.research.driver [--out /tmp/research_out.json]
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

import pandas as pd

from packages.analytics.frequency import infer_frequency, periods_per_day
from packages.research.baseline import (
    AutonomousMomentumBaseline,
    add_regime_compat,
)
from packages.research.candidates import ALL_CANDIDATES
from packages.research.features import build_features
from packages.research.evaluation import (
    annotate_regime,
    evaluate_strategy,
    chronological_walkforward,
    regime_breakdown,
    monte_carlo_trades,
    cost_stress,
    parameter_neighborhood,
)
from packages.research.strategy import BaseStrategy

CACHE = "data/cache/parquet"
SYMBOLS = ["RELIANCE_NS", "TCS_NS"]
BASE_COST = {"slippage": 0.001, "commission": 0.0005}

# candidates + the unchanged autonomous_momentum baseline (compared fairly)
REGISTRY: dict[str, type] = dict(ALL_CANDIDATES)
REGISTRY["autonomous_momentum_baseline"] = AutonomousMomentumBaseline


def load_symbol(sym: str) -> pd.DataFrame:
    df = pd.read_parquet(f"{CACHE}/{sym}.parquet")
    df = df.rename(columns=str.lower)
    return df[["open", "high", "low", "close", "volume"]].copy()


def split_daily_intraday(df: pd.DataFrame):
    intra = df[(df.index.hour >= 9)].copy()          # Sep-4 1-min session
    daily = df[(df.index.hour == 0) & (df.index.minute == 0)].copy()  # daily bars
    return daily, intra


def run_full(strategy: BaseStrategy, feat: pd.DataFrame, ppd: int, symbol: str,
             label: str):
    if "regime_signal" in strategy.features_used():
        feat = feat.copy()
        feat = annotate_regime(feat, ppd)
    _, m = evaluate_strategy(strategy, feat, **BASE_COST, periods_per_day_value=ppd)
    m["symbol"] = symbol
    m["set"] = label
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/research_out.json")
    args = ap.parse_args()

    out = {
        "symbols": SYMBOLS,
        "base_cost": BASE_COST,
        "candidates": {},
        "intraday_metrics": [],
        "daily_metrics": [],
        "walkforward": {},
        "regime_breakdown": {},
        "monte_carlo": {},
        "cost_stress": {},
        "param_robustness": {},
    }

    # per-symbol intraday feature frames (the largest usable sample)
    intra_feat = {}
    daily_feat = {}
    for sym in SYMBOLS:
        df = load_symbol(sym)
        d, intra = split_daily_intraday(df)
        ppd = periods_per_day(infer_frequency(intra.index))
        intra_feat[sym] = (build_features(intra), ppd)
        d_ppd = 1
        daily_feat[sym] = (build_features(d), d_ppd)

    # full IS metrics + MC on each candidate (and the baseline)
    for name, cls in REGISTRY.items():
        strat = cls()
        out["candidates"][name] = {"name": name, "class": cls.__name__,
                                   "default_params": strat.params,
                                   "description": strat.describe(),
                                   "features_used": strat.features_used()}
        intra_rows = []
        daily_rows = []
        mc = {}
        for sym in SYMBOLS:
            feat, ppd = intra_feat[sym]
            # annotate regime once per symbol/frame for any candidate needing it
            if feat.get("regime_signal") is None:
                feat = annotate_regime(feat, ppd)
            intra_feat[sym] = (feat, ppd)
            m = run_full(strat, feat, ppd, sym, "intraday")
            intra_rows.append(m)
            out["intraday_metrics"].append(m)
            # MC on intraday trades
            res, _m2 = evaluate_strategy(strat, feat, **BASE_COST, periods_per_day_value=ppd)
            mc[sym] = monte_carlo_trades(res.trades, periods_per_day=ppd)
            # daily
            df, dppd = daily_feat[sym]
            if "regime_signal" in strat.features_used() or "regime_label" in strat.features_used():
                df = annotate_regime(df, dppd)
            dm = run_full(strat, df, dppd, sym, "daily")
            daily_rows.append(dm)
            out["daily_metrics"].append(dm)
        out["monte_carlo"][name] = mc

        # walk-forward on intraday (single-session OOS — caveat documented)
        wf = {}
        for sym in SYMBOLS:
            feat, ppd = intra_feat[sym]
            agg, per = chronological_walkforward(strat, feat, train_frac=0.6,
                                                 n_windows=3, periods_per_day_value=ppd)
            wf[sym] = {"agg": agg, "windows": per.to_dict("records")}
        out["walkforward"][name] = wf

        # regime breakdown on intraday
        rb = {}
        for sym in SYMBOLS:
            feat, ppd = intra_feat[sym]
            rb[sym] = regime_breakdown(strat, feat, periods_per_day_value=ppd).to_dict("records")
        out["regime_breakdown"][name] = rb

        # cost stress on intraday (first symbol covers the mechanism)
        cs = {}
        for sym in SYMBOLS:
            feat, ppd = intra_feat[sym]
            cs[sym] = cost_stress(strat, feat.copy(), periods_per_day_value=ppd)
        out["cost_stress"][name] = cs

        # parameter-neighborhood robustness on intraday
        pr = {}
        for sym in SYMBOLS:
            feat, ppd = intra_feat[sym]
            pr[sym] = parameter_neighborhood(cls, feat.copy(),
                                             _neighborhood(name),
                                             periods_per_day_value=ppd)
        out["param_robustness"][name] = pr

    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"wrote {args.out}")
    print("registry:", list(REGISTRY.keys()))


def _neighborhood(name: str) -> list[dict]:
    """Small, reasonable parameter neighborhoods (not grid explosions)."""
    if name == "A_trend_following":
        return [dict(ema_fast=20, ema_slow=50, adx_min=20, adx_exit=18),
                dict(ema_fast=21, ema_slow=55, adx_min=18, adx_exit=16),
                dict(ema_fast=10, ema_slow=30, adx_min=22, adx_exit=20)]
    if name == "B_momentum":
        return [dict(rsi_period=14, rsi_hi=70, rsi_lo=30, roc_period=5),
                dict(rsi_period=14, rsi_hi=75, rsi_lo=25, roc_period=5),
                dict(rsi_period=10, rsi_hi=70, rsi_lo=30, roc_period=10)]
    if name == "C_breakout":
        return [dict(period=20, vol_floor=0.005, vol_ratio_min=1.1),
                dict(period=20, vol_floor=0.004, vol_ratio_min=1.0),
                dict(period=10, vol_floor=0.006, vol_ratio_min=1.2)]
    if name == "D_mean_reversion":
        return [dict(bb_period=20, n_std=2.0, rsi_lo=30, vol_ceil=0.02),
                dict(bb_period=20, n_std=2.5, rsi_lo=25, vol_ceil=0.03),
                dict(bb_period=15, n_std=2.0, rsi_lo=30, vol_ceil=0.02)]
    if name == "E_multi_factor":
        return [dict(act_threshold=2.0), dict(act_threshold=3.0),
                dict(act_threshold=1.5)]
    if name == "autonomous_momentum_baseline":
        return [dict(momentum_window=5), dict(momentum_window=3),
                dict(momentum_window=10)]
    return [{}]


if __name__ == "__main__":
    main()
