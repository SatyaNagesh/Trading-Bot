"""FROZEN HOLDOUT strategy replication — Phase 5-7.

Re-runs the frozen `expanded_driver` machinery (same registry, same candidates,
same execution + costs, same metrics, same tournament decision rule) over the
60-symbol independent holdout corpus in `data/holdout/`. Every algorithm is
imported unchanged from the frozen modules; only the data store root and the
loop substrate differ. No new strategy, parameter or threshold is introduced.

Output: reports/holdout_strategy_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from packages.research.alpha_dataset import load_splits as _load_splits
from packages.research.baseline import add_regime_compat
from packages.research.driver import REGISTRY, _neighborhood
from packages.research.evaluation import (
    annotate_regime,
    chronological_walkforward,
    cost_stress,
    evaluate_strategy,
    parameter_neighborhood,
    regime_breakdown,
)
from packages.research.expanded_driver import (
    BASE_COST,
    MIN_OOS_TRADES,
    ROUND_TRIP_COST_PCT,
    decision,
    per_symbol_run,
    pooled_stats,
    trade_net_pct,
)
from packages.research.features import build_features

HOLD = Path("data/holdout")
PPD = 1
OUT = Path("reports/holdout_strategy_results.json")


def _annotate_all(symbols: list[str]):
    feat_annotated, features = {}, {}
    for sym in symbols:
        df = pd.read_parquet(HOLD / "d1d" / f"{sym}.parquet")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        feat = build_features(df)
        feat["close"] = df["close"]
        feat_annotated[sym] = annotate_regime(feat.copy(), PPD)
        features[sym] = feat
    return feat_annotated, features


def mask_slice(feat: pd.DataFrame, bounds: dict) -> pd.Series:
    return (feat.index >= bounds["start"]) & (feat.index < bounds["end"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    splits_raw = json.loads((HOLD / "splits.json").read_text())
    splits_ts = {}
    for name, b in splits_raw.items():
        splits_ts[name] = {
            "start": pd.Timestamp(b["start"], tz="Asia/Kolkata"),
            "end": pd.Timestamp(b["end"], tz="Asia/Kolkata"),
        }
    symbols = sorted(p.stem for p in (HOLD / "d1d").glob("*.parquet"))

    output = {
        "frozen_ref": {"commit": "9e70300",
                       "registry_decision_fn": "expanded_driver.decision"},
        "holdout_store": "data/holdout",
        "symbols": symbols,
        "n_symbols": len(symbols),
        "splits": splits_raw,
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

    feat_annotated, features = _annotate_all(symbols)

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
            res = per_symbol_run(strat, feat, splits_ts)
            per_sym[sym] = res
            val_trades.append(np.array(res["validation"]["trade_net_pct"], dtype=float))
            final_trades.append(np.array(res["final_oos"]["trade_net_pct"], dtype=float))
            combo = feat[mask_slice(feat, splits_ts["validation"]) |
                         mask_slice(feat, splits_ts["final_oos"])]
            wf[sym] = chronological_walkforward(
                strat, feat.loc[feat.index <= splits_ts["validation"]["end"]],
                train_frac=0.6, n_windows=3, periods_per_day_value=PPD)[0]
            rb[sym] = regime_breakdown(strat, combo, periods_per_day_value=PPD).to_dict("records")
            cs[sym] = cost_stress(strat, combo.copy(), periods_per_day_value=PPD)
            pr[sym] = parameter_neighborhood(cls, combo.copy(),
                                             _neighborhood(name),
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
        cs_frag = np.mean([1 if any(v.get("fragile") for v in cs[s].values())
                           else 0 for s in cs] or [0])
        rb_regimes = [r for s in rb for r in rb[s]]
        pos_regimes = {r["regime"] for r in rb_regimes if r.get("net_return_pct", 0) > 0}
        all_regimes = {r["regime"] for r in rb_regimes}
        rb_stats = {
            "positive_regime_fraction": round(
                len(pos_regimes) / len(all_regimes) if all_regimes else 0, 3),
            "regimes_positive": sorted(pos_regimes),
            "regimes_observed": sorted(all_regimes),
        }
        output["decisions"][name] = decision(name, pooled, pr_stats,
                                             {"fragile_fraction": cs_frag}, rb_stats)
        # point-in-time summary for quick reading
        st = pooled["combined"]
        print(f"  {name:30s} OOS trades={st.get('n_trades'):>5} "
              f"exp={st.get('expectancy_pct')}%  PF={st.get('profit_factor')}  "
              f"decision={output['decisions'][name]['decision']}", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2, default=str))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()