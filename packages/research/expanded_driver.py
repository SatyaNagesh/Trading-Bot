"""Expanded-data strategy tournament runner.

Re-runs the *identical* evaluation framework (same candidates, same execution,
same costs, same metric suite as ``packages.research.driver``) over the
multi-year NIFTY-50 daily dataset acquired by the historical-data pipeline.

Primary evidence is OUT-OF-SAMPLE by design:

  * TRAIN      2014-01-01 -> 2023-01-01        (development, never scored)
  * VALIDATION 2023-01-01 -> 2025-07-01        (candidate comparison)
  * FINAL-OOS  2025-07-01 -> 2026-09-04        (untouched test period)

For every strategy it reports per-split OOS metrics, pooled OOS trade-level
statistics (wins/losses, expectancy, PF, drawdown, Sharpe, Sortino, bootstrap
confidence intervals), a chronological walk-forward, regime breakdown, cost
stress and parameter robustness — then applies the tournament selection rule.

Usage:
  python -m packages.research.expanded_driver [--out /tmp/research_out_expanded.json]
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from packages.market.data_split import split_frame
from packages.market.data_ingestion import store_root
from packages.research.baseline import add_regime_compat, AutonomousMomentumBaseline
from packages.research.candidates import ALL_CANDIDATES
from packages.research.features import build_features
from packages.research.evaluation import (
    annotate_regime,
    chronological_walkforward,
    cost_stress,
    evaluate_strategy,
    parameter_neighborhood,
    regime_breakdown,
)
from packages.research.driver import REGISTRY, _neighborhood

BASE_COST = {"slippage": 0.001, "commission": 0.0005}
ROUND_TRIP_COST_PCT = 2 * (BASE_COST["slippage"] + BASE_COST["commission"]) * 100
MIN_OOS_TRADES = 30
PPD = 1


def trade_net_pct(res) -> np.ndarray:
    return np.array([t["pnl_pct"] - ROUND_TRIP_COST_PCT for t in res.trades])


def _metrics_slice(strategy, feat, start, end):
    mask = (feat.index >= start) & (feat.index < end)
    res, m = evaluate_strategy(strategy, feat[mask], **BASE_COST, periods_per_day_value=PPD)
    return res, m


def ci_bootstrap(values: np.ndarray, n_sims: int = 2000, seed: int = 7) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(n_sims, len(values)), replace=True).mean(axis=1)
    return tuple(np.percentile(samples, [2.5, 97.5]))


def pooled_stats(trades_pct: list[np.ndarray]) -> dict:
    values = np.concatenate(trades_pct) if trades_pct else np.array([])
    n = int(len(values))
    if n == 0:
        return {"n_trades": 0, "status": "INSUFFICIENT DATA"}
    wins = values[values > 0]
    losses = values[values <= 0]
    gross = float(values.sum())
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf")
    lo, hi = ci_bootstrap(values)
    prob_win = len(wins) / n
    desc = np.sort(values)[::-1]
    n_top10 = max(1, n // 10)
    share10 = float(desc[:n_top10].sum() / gross) if gross > 0 else 0.0
    return {
        "n_trades": n,
        "status": "OK",
        "wins": int(len(wins)),
        "losses": int(n - len(wins)),
        "win_rate_pct": round(prob_win * 100, 2),
        "avg_net_pct": round(float(values.mean()), 4),
        "median_net_pct": round(float(np.median(values)), 4),
        "expectancy_pct": round(float(values.mean()), 4),
        "sum_net_pct": round(gross, 4),
        "profit_factor": round(pf, 3),
        "ci95_lo": round(float(lo), 4),
        "ci95_hi": round(float(hi), 4),
        "top10pct_net_share": round(share10, 3),
    }


def per_symbol_run(strategy, feat, splits) -> dict:
    out = {}
    for name in ("train", "validation", "final_oos"):
        mask = (feat.index >= splits[name]["start"]) & (feat.index < splits[name]["end"])
        res, m = evaluate_strategy(strategy, feat[mask], **BASE_COST, periods_per_day_value=PPD)
        out[name] = {
            "metrics": {k: (str(v) if isinstance(v, (pd.Timestamp,)) else v)
                        for k, v in m.items()},
            "n_trades": len(res.trades),
            "trade_net_pct": trade_net_pct(res).tolist(),
        }
    return out


def decision(strategy: str, oos: dict, param: dict, cost: dict, regime: dict) -> dict:
    st = oos["combined"]
    recent = oos.get("final_oos", {})
    n = st.get("n_trades", 0)
    if n < MIN_OOS_TRADES:
        return {"decision": "INSUFFICIENT DATA",
                "rationale": f"pooled OOS trades={n} < {MIN_OOS_TRADES}"}
    exp = st.get("expectancy_pct", -1)
    ci_lo = st.get("ci95_lo", -1)
    if exp <= 0 or ci_lo <= 0:
        return {"decision": "NO EDGE",
                "rationale": f"OOS expectancy {exp}% (CI lohi {ci_lo}..{st.get('ci95_hi')}) not positive"}
    pf = st.get("profit_factor", 0)
    win = st.get("win_rate_pct", 0)
    param_frac = param.get("fraction_positive", 0)
    fragile = cost.get("fragile_fraction", 1.0) > 0.5
    regime_bad = regime.get("positive_regime_fraction", 0) < 0.5
    share10 = st.get("top10pct_net_share", 0)
    reasons = []
    if pf < 1.2:
        reasons.append(f"PF={pf}<1.2")
    if win < 40:
        reasons.append(f"win={win}%<40")
    if param_frac < 0.5:
        reasons.append(f"param positive frac {param_frac}")
    if fragile:
        reasons.append("cost-fragile")
    if regime_bad:
        reasons.append("regime-weak")
    if share10 > 0.90:
        reasons.append(f"outlier-driven top10%={share10*100:.0f}% of net")
    if recent.get("n_trades", 0) >= MIN_OOS_TRADES and recent.get("expectancy_pct", 1) <= 0:
        reasons.append(f"most-recent OOS window negative "
                       f"(exp {recent.get('expectancy_pct')}%, PF {recent.get('profit_factor')})")
    if reasons:
        return {"decision": "OVERFIT/FRAGILE", "rationale": "; ".join(reasons)}
    return {"decision": "PROMISING - MORE DATA",
            "rationale": "positive OOS edge; intraday depth insufficient to ADVANCE"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/research_out_expanded.json")
    args = ap.parse_args()

    splits = json.loads((store_root() / "splits.json").read_text())
    symbols = sorted(p.stem for p in (store_root() / "d1d").glob("*.parquet"))

    output = {
        "timeframe": "d1d",
        "symbols": symbols,
        "splits": splits,
        "base_cost": BASE_COST,
        "registry": list(REGISTRY.keys()),
        "per_split_metrics": {},
        "walkforward": {},
        "regime_breakdown": {},
        "cost_stress": {},
        "param_robustness": {},
        "pooled_oos": {},
        "decisions": {},
    }

    feat_annotated = {}
    features = {}
    for sym in symbols:
        df = pd.read_parquet(store_root() / "d1d" / f"{sym}.parquet")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        feat = build_features(df)
        feat["close"] = df["close"]
        feat_annotated[sym] = annotate_regime(feat.copy(), PPD)
        features[sym] = feat

    for name, cls in REGISTRY.items():
        strat = cls()
        per_sym = {}
        val_trades: list[np.ndarray] = []
        final_trades: list[np.ndarray] = []
        wf = {}
        rb = {}
        cs = {}
        pr = {}
        for sym in symbols:
            feat = feat_annotated[sym]
            if "regime_label" in strat.features_used():
                feat = add_regime_compat(feat.copy())
            res = per_symbol_run(strat, feat, splits)
            per_sym[sym] = res
            val_trades.append(np.array(res["validation"]["trade_net_pct"], dtype=float))
            final_trades.append(np.array(res["final_oos"]["trade_net_pct"], dtype=float))
            combo = feat[mask_slice(feat, splits["validation"]) | mask_slice(feat, splits["final_oos"])]
            wf[sym] = chronological_walkforward(
                strat, feat.loc[feat.index <= splits["validation"]["end"]],
                train_frac=0.6, n_windows=3, periods_per_day_value=PPD)[0]
            rb[sym] = regime_breakdown(strat, combo, periods_per_day_value=PPD).to_dict("records")
            cs[sym] = cost_stress(strat, combo.copy(), periods_per_day_value=PPD)
            pr[sym] = parameter_neighborhood(cls, combo.copy(), _neighborhood(name),
                                             periods_per_day_value=PPD)
        output["per_split_metrics"][name] = per_sym
        output["walkforward"][name] = wf
        output["regime_breakdown"][name] = rb
        output["cost_stress"][name] = cs
        output["param_robustness"][name] = pr
        pooled = {
            "validation": pooled_stats(val_trades),
            "final_oos": pooled_stats(final_trades),
            "combined": pooled_stats(val_trades + final_trades),
        }
        output["pooled_oos"][name] = pooled

        pr_stats = {"fraction_positive": round(np.mean(
            [pr[s].get("fraction_positive", 0) for s in pr] or [0]), 3)}
        cs_frag = np.mean([1 if any(
            v.get("fragile") for v in cs[s].values()) else 0 for s in cs] or [0])
        rb_regimes = [r for s in rb for r in rb[s]]
        pos_regimes = {r["regime"] for r in rb_regimes if r.get("net_return_pct", 0) > 0}
        all_regimes = {r["regime"] for r in rb_regimes}
        rb_stats = {
            "positive_regime_fraction": round(
                len(pos_regimes) / len(all_regimes) if all_regimes else 0, 3),
            "regimes_positive": sorted(pos_regimes),
            "regimes_observed": sorted(all_regimes),
        }
        output["decisions"][name] = decision(
            name, pooled, pr_stats, {"fragile_fraction": cs_frag}, rb_stats)

    with open(args.out, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"wrote {args.out}")
    print("decisions:")
    for s, d in output["decisions"].items():
        print(f"  {s:28s} {d['decision']:20s} {d['rationale']}")


def mask_slice(feat: pd.DataFrame, bounds: dict) -> pd.Series:
    return (feat.index >= bounds["start"]) & (feat.index < bounds["end"])


if __name__ == "__main__":
    main()