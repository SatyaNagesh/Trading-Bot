"""Evaluation harness for the tournament: walk-forward, regime, MC, stress, params.

Everything here is split on **chronological** time (never random shuffle of a
financial series). Each candidate runs through the identical execution + cost
model, so comparisons are fair.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from packages.analytics.regime_observer import RegimeObserver
from packages.analytics.frequency import periods_per_day
from packages.research.execution import execute
from packages.research.metrics import compute_metrics
from packages.research.strategy import BaseStrategy


def annotate_regime(feat: pd.DataFrame, periods_per_day_value: int,
                    lookback: int = 21) -> pd.DataFrame:
    """Add a causal 'regime_signal' column (+1/-1/0) from the frequency-aware RegimeObserver.

    The signed factor maps favourable regimes for a long bias to +1 and adverse
    (high-vol / crisis) regimes to -1, so it can be consumed by ``MultiFactorE``.
    """
    obs = RegimeObserver(lookback=lookback, periods_per_day=periods_per_day_value)
    closes = feat["close"].to_numpy()
    signals = np.zeros(len(feat))
    seen = []
    for i in range(len(feat)):
        seen.append(float(closes[i]))
        r = obs.observe(seen, feat.index[i]).value
        if r in ("trending", "breakout", "low_volatility"):
            signals[i] = 1.0
        elif r in ("high_volatility", "volatile", "crisis"):
            signals[i] = -1.0
        else:
            signals[i] = 0.0
    feat["regime_signal"] = pd.Series(signals, index=feat.index)
    # also expose the raw regime label string for breakdown analysis
    obs2 = RegimeObserver(lookback=lookback, periods_per_day=periods_per_day_value)
    labels = []
    seen2 = []
    for i in range(len(feat)):
        seen2.append(float(closes[i]))
        labels.append(obs2.observe(seen2, feat.index[i]).value)
    feat["regime_label"] = pd.Series(labels, index=feat.index)
    # trend-following regime compatibility (used by the autonomous_momentum baseline)
    from packages.research.baseline import TREND_COMPATIBLE

    feat["regime_compat"] = feat["regime_label"].map(
        lambda r: 1.0 if (r in TREND_COMPATIBLE or r == "unknown") else 0.0
    ).astype(float)
    return feat


def evaluate_strategy(
    strategy: BaseStrategy,
    feat: pd.DataFrame,
    slippage: float = 0.001,
    commission: float = 0.0005,
    periods_per_day_value: int = 1,
):
    """Run one strategy over the full feature frame and return (execution, metrics)."""
    if "regime_signal" not in feat and (
        "regime_signal" in strategy.features_used() or "regime_label" in strategy.features_used()
    ):
        feat = annotate_regime(feat, periods_per_day_value)
    if "regime_label" in strategy.features_used() and "regime_compat" not in feat:
        from packages.research.baseline import add_regime_compat

        feat = add_regime_compat(feat)
    target = strategy.decide(feat).fillna(0.0)
    res = execute(feat["close"], feat.index, target, slippage=slippage, commission=commission)
    metrics = compute_metrics(res, periods_per_day=periods_per_day_value)
    metrics["strategy"] = strategy.name
    return res, metrics


def chronological_walkforward(
    strategy: BaseStrategy,
    feat_all: pd.DataFrame,
    train_frac: float = 0.6,
    n_windows: int = 3,
    slippage: float = 0.001,
    commission: float = 0.0005,
    periods_per_day_value: int = 1,
):
    """Chronological walk-forward on a time series (never shuffled).

    The series is split into ``n_windows + 1`` equal chronological segments.
    The **first** segment is the model-free train anchor; each following
    segment is a successive out-of-sample test slice scored independently.
    This is the standard expanding-window walk-forward applied to a single
    contiguous series. Returns (aggregate dict, per-window DataFrame).
    """
    n = len(feat_all)
    rows = []
    n_seg = n_windows + 1
    seg = max(int(n / n_seg), 1)
    start_test = seg  # first segment is the train anchor
    for w in range(1, n_windows + 1):
        end_test = min(n, start_test + seg)
        if end_test - start_test < 2:
            break
        oos = feat_all.iloc[start_test:end_test].copy()
        if "regime_signal" in strategy.features_used():
            oos = annotate_regime(oos, periods_per_day_value)
        target = strategy.decide(oos).fillna(0.0)
        res = execute(oos["close"], oos.index, target, slippage=slippage, commission=commission)
        m = compute_metrics(res, periods_per_day=periods_per_day_value)
        m["window"] = w
        m["train_anchor_bars"] = start_test
        m["oos_bars"] = len(oos)
        rows.append(m)
        start_test = end_test
    if not rows:
        return {}, []
    df = pd.DataFrame(rows)
    agg = {
        "windows": len(rows),
        "avg_oos_net_return_pct": round(float(df["net_return_pct"].mean()), 4),
        "total_oos_net_return_pct": round(float(df["net_return_pct"].sum()), 4),
        "avg_oos_expectancy_pct": round(float(df["expectancy_pct"].mean()), 4),
        "avg_oos_win_rate_pct": round(float(df["win_rate_pct"].mean()), 4),
        "avg_oos_trades": round(float(df["trades"].mean()), 2),
        "total_oos_trades": int(df["trades"].sum()),
        "both_oos_windows_positive": bool(
            (df["net_return_pct"] > 0).all() if len(df) > 0 else False
        ),
        "negative_windows": int((df["net_return_pct"] <= 0).sum()),
    }
    return agg, df


def regime_breakdown(
    strategy: BaseStrategy, feat: pd.DataFrame, slippage=0.001, commission=0.0005,
    periods_per_day_value: int = 1,
) -> pd.DataFrame:
    """Per-regime performance by rolling-regime annotation of each bar."""
    if "regime_label" not in feat:
        feat = annotate_regime(feat, periods_per_day_value)
    target = strategy.decide(feat).fillna(0.0)
    res = execute(feat["close"], feat.index, target, slippage=slippage, commission=commission)
    labels = feat["regime_label"].to_numpy()
    rows = []
    for label in sorted(set(labels)):
        mask = labels == label
        if mask.sum() < 2:
            continue
        sub_close = feat["close"][mask]
        sub_target = target[mask]
        sub_res = execute(sub_close, feat.index[mask], sub_target, slippage=slippage, commission=commission)
        m = compute_metrics(sub_res, periods_per_day=periods_per_day_value)
        rows.append({"regime": label, "bars": int(mask.sum()),
                     "trades": m["trades"], "net_return_pct": m["net_return_pct"],
                     "win_rate_pct": m["win_rate_pct"], "expectancy_pct": m["expectancy_pct"]})
    return pd.DataFrame(rows)


def monte_carlo_trades(
    trades, n_sims: int = 5000, seed: int = 7, periods_per_day: int = 1
):
    """Monte Carlo over the *actual* trade-return distribution (resampling with replacement)."""
    pnls = np.array([t["pnl_pct"] for t in trades])
    if len(pnls) < 8:
        return {"status": "INSUFFICIENT SAMPLE", "n_trades": len(pnls)}
    rng = np.random.default_rng(seed)
    finals = np.empty(n_sims)
    for i in range(n_sims):
        sample = rng.choice(pnls, size=len(pnls), replace=True)
        finals[i] = float(np.prod(1 + sample / 100.0))
    mean_final = finals.mean()
    prob_loss = float((finals < 1.0).mean())
    var_95 = float(np.percentile(finals, 5))
    cvar_95 = float(finals[finals <= var_95].mean()) if (finals <= var_95).any() else var_95
    # losing streak distribution
    max_streak = []
    for i in range(min(n_sims, 2000)):
        sample = rng.choice(pnls, size=len(pnls), replace=True)
        worst = cur = 0
        for v in sample:
            if v < 0:
                cur += 1
                worst = max(worst, cur)
            else:
                cur = 0
        max_streak.append(worst)
    return {
        "status": "OK",
        "n_trades": len(pnls),
        "n_sims": n_sims,
        "mean_final_mult": round(float(mean_final), 4),
        "prob_loss": round(float(prob_loss), 4),
        "var_95": round(float(var_95), 4),
        "cvar_95": round(float(cvar_95), 4),
        "mean_max_losing_streak": round(float(np.mean(max_streak)), 2),
        "p95_max_losing_streak": round(float(np.percentile(max_streak, 95)), 1),
    }


def cost_stress(
    strategy: BaseStrategy, feat: pd.DataFrame, periods_per_day_value: int = 1,
):
    """Phase 9: same strategy under BASE/HIGHER cost and BASE/HIGHER slippage."""
    base = {"slippage": 0.001, "commission": 0.0005}
    scenarios = {
        "BASE": dict(base),
        "HIGHER_COST": {"slippage": 0.001, "commission": 0.0020},
        "HIGHER_SLIPPAGE": {"slippage": 0.003, "commission": 0.0005},
        "HIGHER_BOTH": {"slippage": 0.003, "commission": 0.0020},
    }
    out = {}
    for label, c in scenarios.items():
        _, m = evaluate_strategy(strategy, feat.copy(), slippage=c["slippage"],
                                 commission=c["commission"],
                                 periods_per_day_value=periods_per_day_value)
        out[label] = {"net_return_pct": m["net_return_pct"],
                      "expectancy_pct": m["expectancy_pct"],
                      "trades": m["trades"],
                      "fragile": m["net_return_pct"] < 0}
    return out


def parameter_neighborhood(
    strategy_cls, feat: pd.DataFrame, param_sets: list[dict],
    periods_per_day_value: int = 1,
):
    """Phase 11: evaluate a *neighborhood* of reasonable parameterisations.

    `param_sets` is a list of dicts, each a complete param dict for strategy_cls.
    Reports the spread of OOS/full net returns to test broad stability, not a
    single tuned peak.
    """
    rows = []
    for ps in param_sets:
        try:
            s = strategy_cls(**ps)
        except TypeError:
            continue
        _, m = evaluate_strategy(s, feat.copy(), periods_per_day_value=periods_per_day_value)
        rows.append({"params": ps, "net_return_pct": m["net_return_pct"],
                     "expectancy_pct": m["expectancy_pct"], "trades": m["trades"],
                     "pf": m["profit_factor"]})
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    return {
        "n_variants": len(df),
        "net_mean": round(float(df["net_return_pct"].mean()), 4),
        "net_std": round(float(df["net_return_pct"].std()), 4),
        "net_min": round(float(df["net_return_pct"].min()), 4),
        "net_max": round(float(df["net_return_pct"].max()), 4),
        "fraction_positive": round(float((df["net_return_pct"] > 0).mean()), 4),
        "expectancy_spread": round(float(df["expectancy_pct"].std()), 4),
        "rows": df.to_dict("records"),
    }
