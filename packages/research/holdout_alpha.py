"""FROZEN HOLDOUT alpha replication — Phase 8.

Rebuilds the holdout panel with the frozen `alpha_dataset.build_panel`
(store-root injected to data/holdout, splits identical to DEVELOPMENT) and
re-runs the frozen alpha-analysis machinery for the two pre-registered
features — vol_rel20@{1,3,5} and vol_trend_10v50@{1,3} — on the independent
dataset: per-split IC, cross-sectional long/short deciles, cost-aware LS,
per-symbol breadth, regime conditioning, and randomization nulls.

Every statistic uses the unchanged frozen functions from `alpha_analysis.py`.
DEV baseline numbers are read live from the frozen reports for comparison.

Output: reports/holdout_alpha_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from packages.research import alpha_analysis as aa
from packages.research import alpha_dataset as ad

HOLD = Path("data/holdout")
OUT = Path("reports/holdout_alpha_results.json")
SPLITS = ["train", "validation", "final_oos"]
MIN_SYM_IC_N = 200


def build_holdout_panel(verbose: bool = True) -> pd.DataFrame:
    ad.store_root = lambda: HOLD
    return ad.build_panel(verbose=verbose)


def per_symbol_ic(sub: pd.DataFrame, feature: str, horizon: int) -> list[dict]:
    rows = []
    for sym, g in sub.groupby(level="symbol"):
        f = g[feature].to_numpy()
        lab = g[f"fwd_ret_{horizon}"].to_numpy()
        mask = np.isfinite(f) & np.isfinite(lab)
        if mask.sum() < MIN_SYM_IC_N:
            continue
        rho = float(pd.Series(f[mask]).corr(pd.Series(lab[mask]), method="spearman"))
        rows.append({"symbol": sym, "ic": round(rho, 5), "n": int(mask.sum())})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--n-shuffle", type=int, default=200)
    ap.add_argument("--n-bootstrap", type=int, default=250)
    args = ap.parse_args()

    panel = build_holdout_panel()
    syms_all = set(panel.index.get_level_values("symbol"))
    print(f"holdout panel: {len(panel)} rows, {len(syms_all)} symbols", flush=True)
    panel["symbol_id"] = panel.index.get_level_values("symbol")

    # dev baselines read from frozen reports (no manual copying)
    dev = json.loads((Path("reports/alpha_discovery_results.json")).read_text())["ic_table"]
    dev_baseline = {}
    for fk in ("vol_rel20", "vol_trend_10v50"):
        for hk in ("1", "3", "5"):
            row = dev.get(fk, {}).get(hk, {})
            dev_baseline[f"{fk}@{hk}"] = {
                sp: {
                    "spearman_ic": r.get("spearman_ic"),
                    "pvalue": r.get("pvalue"),
                    "ci95_lo": r.get("ci95_lo"),
                    "ci95_hi": r.get("ci95_hi"),
                }
                for sp, r in row.items() if isinstance(r, dict)
            }

    out = {
        "holdout_store": "data/holdout",
        "panel_rows": int(len(panel)),
        "symbols": len(syms_all),
        "min_symbol_ic_n": MIN_SYM_IC_N,
        "splits": json.loads((HOLD / "splits.json").read_text()),
        "features_tested": ["vol_rel20@1", "vol_rel20@3", "vol_rel20@5",
                            "vol_trend_10v50@1", "vol_trend_10v50@3"],
        "dev_baseline": dev_baseline,
        "per_split_ic": {},
        "ls_decile": {},
        "ls_quintile": {},
        "cost_aware": {},
        "symbol_breadth": {},
        "regime_ic": {},
        "randomization": {},
        "bootstrap_ic": {},
    }

    tested = [("vol_rel20", 1), ("vol_rel20", 3), ("vol_rel20", 5),
              ("vol_trend_10v50", 1), ("vol_trend_10v50", 3)]

    for feature, horizon in tested:
        key = f"{feature}@{horizon}"
        ic_by_split = {}
        lsd = {}
        lsq = {}
        ca = {}
        breadth = {}
        reg = {}
        for split in SPLITS:
            sub = panel[panel["split"] == split]
            st = aa.ic_stats(sub[feature].to_numpy(),
                             sub[f"fwd_ret_{horizon}"].to_numpy(),
                             sub.index.get_level_values("symbol").to_numpy())
            ic_by_split[split] = st
            ls20 = aa.long_short_by_date(sub, feature, horizon, split, 0.10)
            lsq[split] = aa.long_short_by_date(sub, feature, horizon, split, 0.20)
            lsd[split] = ls20
            ca[split] = aa.cost_aware_ls(sub, feature, horizon, split,
                                         coverage=0.10, cost_per_side=0.0015)
            rows = per_symbol_ic(sub, feature, horizon)
            positive = sum(1 for r in rows if r["ic"] >= 0)
            negative = sum(1 for r in rows if r["ic"] < 0)
            breadth[split] = {"symbols_with_ic": len(rows),
                              "ic_positive": positive, "ic_negative": negative,
                              "frac_positive": round(positive / len(rows), 4) if rows else None,
                              "median_ic": round(float(np.median([r["ic"] for r in rows])), 5) if rows else None}
            reg[split] = aa.regime_ic(sub, feature, horizon, split)
        out["per_split_ic"][key] = ic_by_split
        out["ls_decile"][key] = lsd
        out["ls_quintile"][key] = lsq
        out["cost_aware"][key] = ca
        out["symbol_breadth"][key] = breadth
        out["regime_ic"][key] = reg

        # randomization nulls on validation + final_oos (frozen engine)
        rand = {}
        for split in ("validation", "final_oos"):
            sub = panel[panel["split"] == split]
            rn = aa.randomized_null(sub[feature].to_numpy(),
                                    sub[f"fwd_ret_{horizon}"].to_numpy(),
                                    sub.index.get_level_values("symbol").to_numpy(),
                                    n_shuffles=args.n_shuffle, seed=7)
            rand[split] = rn
        out["randomization"][key] = rand

        # time-block bootstrap IC on final_oos (autocorrelation-robust CI)
        sub = panel[panel["split"] == "final_oos"]
        bboot = aa.block_bootstrap_ic(
            sub[feature].to_numpy(), sub[f"fwd_ret_{horizon}"].to_numpy(),
            sub.index.get_level_values("date").to_numpy(),
            sub.index.get_level_values("symbol").to_numpy(),
            n_sims=args.n_bootstrap, block=63, seed=7)
        out["bootstrap_ic"][key] = bboot

    st_print = {}
    for key in out["per_split_ic"]:
        v = out["per_split_ic"][key]
        def _g(sp): return (v.get(sp) or {}).get("spearman_ic")
        ls = out["ls_decile"][key].get("final_oos") or {}
        st_print[key] = {
            "dev_IC_v/f/o": [dev_baseline[key].get("validation", {}).get("spearman_ic"),
                             dev_baseline[key].get("final_oos", {}).get("spearman_ic")],
            "val_IC": _g("validation"), "val_p": (v.get("validation") or {}).get("pvalue"),
            "oos_IC": _g("final_oos"), "oos_p": (v.get("final_oos") or {}).get("pvalue"),
            "oos_LS20/80_%": ls.get("ls_mean_pct"), "oos_LS_t": ls.get("ls_tstat"),
            "bfr_pos_frac_val": out["symbol_breadth"][key]["validation"].get("frac_positive"),
            "bfr_pos_frac_oos": out["symbol_breadth"][key]["final_oos"].get("frac_positive"),
            "rand_p_val": (out["randomization"][key]["final_oos"] or {}).get("p_two_sided"),
            "boot_IC_ci": [out["bootstrap_ic"][key].get("ci95_lo"),
                           out["bootstrap_ic"][key].get("ci95_hi")],
        }
    print(json.dumps(st_print, indent=1), flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()