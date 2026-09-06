"""Pre-registered monetization transforms for vol_trend_10v50 (Phases 8 & 10).

Builds cross-sectional long-short portfolios for exactly the transforms frozen
in data/holdout_2/transform_spec.json and reports gross- and cost-aware metrics.

Pre-registration discipline:
  - The transform definitions, costs, gates and decision rule are read from
    data/holdout_2/transform_spec.json (frozen BEFORE any holdout_2 data was
    fetched and before any evaluation).
  - Selection gate = DEVELOPMENT VALIDATION; confirmation = exactly one run on
    holdout_2 FINAL-OOS. Nothing is tuned after the fact.
  - Transforms are daily-rebalanced, equal-weight, long-short cross-sectional
    portfolios of the vol_trend_10v50 feature (or a pre-specified transform of
    it). They are NOT production strategies.

Usage:
    python -m packages.research.vt_transforms --out reports/vt_transforms_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from scipy import stats

from packages.research.vt_signal import (
    attach_exposures, _index_ret, load_panels, sector_of, _load_d1d_volume)

SPEC_PATH = Path("data/holdout_2/transform_spec.json")
FEATURE = "vol_trend_10v50"


def load_holdout2_panel() -> pd.DataFrame:
    """holdout_2 alpha panel (features + raw volume), mirrors frozen building."""
    from packages.research import alpha_dataset as ad
    from packages.research.vt_signal import _load_d1d_volume

    ad.store_root = lambda: Path("data/holdout_2")
    ho2 = ad.build_panel()
    ho2 = ho2.join(_load_d1d_volume("data/holdout_2/d1d"), how="left")
    return ho2


def _per_symbol_rolling_std(panel: pd.DataFrame, window: int = 252) -> pd.Series:
    return panel[FEATURE].groupby(level="symbol").rolling(window).std() \
        .reset_index(level=0, drop=True)


def _t3_feature(panel: pd.DataFrame) -> pd.Series:
    s = panel[FEATURE] / _per_symbol_rolling_std(panel).replace(0, np.nan)
    return s


def _t4_feature(panel: pd.DataFrame) -> pd.Series:
    """within-date, within-sector integer rank (1..n) of the raw feature."""
    dd = pd.DataFrame({"sym": panel.index.get_level_values("symbol"),
                       "dt": panel.index.get_level_values("date"),
                       "f": panel[FEATURE]})
    dd["sector"] = dd["sym"].map(sector_of)
    r = dd.groupby(["dt", "sector"])["f"].rank(method="first")
    return r.reindex(panel.index)


def _t5_feature(panel: pd.DataFrame) -> pd.Series:
    """per-date cross-sectional rank-OLS residual on exposures."""
    exps = ["beta", "vol", "mom", "trend", "size", "liq"]
    fr = panel[FEATURE].rank()
    idx, resid = [], []
    for dt, gg in panel.groupby(level="date"):
        X = gg[[c for c in exps if c in gg.columns]].astype(float).rank()
        X = (X - X.mean()) / X.std().replace(0, np.nan)
        X["const"] = 1.0
        y = fr.reindex(gg.index).to_numpy().astype(float)
        m = np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(y)
        if m.sum() < 15:
            continue
        coef, *_ = np.linalg.lstsq(X.to_numpy()[m], y[m], rcond=None)
        pred = X.to_numpy()[m] @ coef
        idx.extend(gg.index[m])
        resid.extend(y[m] - pred)
    return pd.Series(resid, index=pd.Index(idx))


def _transform_feature(panel: pd.DataFrame, kind: str) -> pd.Series:
    if kind == "raw":
        return panel[FEATURE]
    if kind == "vol_std_scaled":
        return _t3_feature(panel)
    if kind == "sector_relative":
        return _t4_feature(panel)
    if kind == "neutralized":
        return _t5_feature(panel)
    raise ValueError(f"unknown transform kind {kind}")


def _leg_series(panel: pd.DataFrame, feature: pd.Series,
                coverage: float, pre_ranked: str | None = None) -> dict:
    sub = panel.loc[feature.dropna().index].copy()
    sub["f"] = feature.reindex(sub.index)
    sub["dt"] = sub.index.get_level_values("date")
    if pre_ranked == "cell":
        # feature = integer within-(date,sector) rank (1..n); size-aware cutoffs
        sub["sector"] = sub.index.get_level_values("symbol").map(sector_of)
        grp = sub.groupby(["dt", "sector"])
        sub["cell_rank"] = sub["f"]
        sub["cell_n"] = grp["f"].transform("max")
        k = np.ceil(sub["cell_n"] * coverage).clip(lower=1)
        sub["rank_pct"] = sub["cell_rank"] / sub["cell_n"]
        sub["long"] = sub["cell_rank"] >= (sub["cell_n"] - k + 1)
        sub["short"] = sub["cell_rank"] <= k
    elif pre_ranked:
        raise ValueError(f"unknown pre_ranked mode {pre_ranked}")
    else:
        sub["rank_pct"] = sub.groupby("dt")["f"].rank(pct=True)
        sub["long"] = sub["rank_pct"] >= 1.0 - coverage
        sub["short"] = sub["rank_pct"] <= coverage

    long_ret = sub.loc[sub["long"]].groupby("dt")["fwd_ret_1"].mean()
    short_ret = sub.loc[sub["short"]].groupby("dt")["fwd_ret_1"].mean()
    long_n = sub.loc[sub["long"]].groupby("dt").size()
    short_n = sub.loc[sub["short"]].groupby("dt").size()
    turnover = {}
    for leg in ("long", "short"):
        members = {}
        for dt, m in sub.groupby("dt"):
            members[dt] = set(m.index.get_level_values("symbol")[m[leg].to_numpy()])
        prev = None
        t = {}
        for dt, mset in members.items():
            if prev is not None and mset:
                t[dt] = len(mset - prev) / len(mset)
            prev = mset
        turnover[leg] = pd.Series(t)
    return {"long_ret": long_ret, "short_ret": short_ret,
            "long_n": long_n, "short_n": short_n,
            "turnover": turnover}


def eval_transform(panel: pd.DataFrame, split: str, spec: dict) -> dict:
    if spec["kind"] == "neutralized":
        sub = attach_exposures(panel)
        sub = sub[sub["split"] == split].copy()
    else:
        sub = panel[panel["split"] == split]
    feat = _transform_feature(sub, spec["kind"])
    cov = spec["coverage"]
    pre_ranked = "cell" if spec["kind"] == "sector_relative" else None
    res = _leg_series(sub, feat, cov, pre_ranked=pre_ranked)
    # daily LS series
    df = pd.DataFrame({"long": res["long_ret"], "short": res["short_ret"],
                       "ln": res["long_n"], "sn": res["short_n"],
                       "to_l": res["turnover"]["long"],
                       "to_s": res["turnover"]["short"]}).dropna(subset=["long", "short"])
    out = {"transform": spec["id"], "split": split, "n_dates": int(len(df))}
    if len(df) < 30:
        out["status"] = "INSUFFICIENT"
        return out
    out["status"] = "OK"
    gross_ls = df["long"] - df["short"]
    out["gross_ls_mean_pct"] = round(float(gross_ls.mean()) * 100, 4)
    out["gross_long_mean_pct"] = round(float(df["long"].mean()) * 100, 4)
    out["gross_short_mean_pct"] = round(float(df["short"].mean()) * 100, 4)
    out["avg_n_long"] = round(float(df["ln"].mean()), 1)
    out["avg_n_short"] = round(float(df["sn"].mean()), 1)
    out["turnover_long"] = round(float(df["to_l"].mean(skipna=True)), 4)
    out["turnover_short"] = round(float(df["to_s"].mean(skipna=True)), 4)

    def _bootstrap(ls_ser: pd.Series, seed: int = 7, block: int = 63,
                   n_sims: int = 1000) -> dict:
        x = ls_ser.to_numpy()
        dates = ls_ser.index.to_numpy()
        n_d = len(dates)
        n_blk = int(np.ceil(n_d / block))
        rng = np.random.default_rng(seed)
        sims = np.empty(n_sims)
        for s in range(n_sims):
            starts = rng.integers(0, n_d, size=n_blk)
            keep = []
            for st_ in starts:
                keep.extend(range(st_, min(st_ + block, n_d)))
            sims[s] = x[keep].mean()
        return {"ci95_lo": round(float(np.quantile(sims, 0.025)), 5),
                "ci95_hi": round(float(np.quantile(sims, 0.975)), 5),
                "p_le_0": round(float((sims <= 0).mean()), 4)}

    for label, cost in (("net_25bps", 0.0025), ("net_15bps", 0.0015)):
        c = cost
        net = (df["long"] - c * df["to_l"].fillna(0)) \
            - (df["short"] + c * df["to_s"].fillna(0))
        boot = _bootstrap(net)
        out[f"{label}_mean_pct"] = round(float(net.mean()) * 100, 4)
        out[f"{label}_tstat"] = round(float(net.mean() /
            (net.std(ddof=1) / np.sqrt(len(net))) if net.std(ddof=1) > 0 else 0.0), 3)
        out[f"{label}_ci95_pct"] = [round(float(boot["ci95_lo"]) * 100, 4),
                                    round(float(boot["ci95_hi"]) * 100, 4)]
        out[f"{label}_p_le0"] = boot["p_le_0"]
        out[f"{label}_ann_sharpe"] = round(float(net.mean() / net.std(ddof=1)) * np.sqrt(252)
                                           if net.std(ddof=1) > 0 else 0.0, 3)
        dd_ = (net[net < 0] ** 2).mean() ** 0.5
        out[f"{label}_ann_sortino"] = round(float(net.mean() / dd_) * np.sqrt(252)
                                            if dd_ > 0 else 0.0, 3)
        cum = (1 + net).cumprod()
        out[f"{label}_max_drawdown_pct"] = round(float(
            (cum / cum.cummax() - 1).min()) * 100, 3)
        out[f"{label}_expectancy_per_rebalance_pct"] = round(float(net.mean()) * 100, 4)
    out["gross_ls_positive_dates_frac"] = round(float((gross_ls > 0).mean()), 4)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/vt_transforms_results.json")
    ap.add_argument("--max-transforms", type=int, default=None)
    args = ap.parse_args()

    spec = json.loads(SPEC_PATH.read_text())
    transforms = spec["transforms"]
    if args.max_transforms:
        transforms = transforms[:args.max_transforms]

    panels = load_panels()
    panels["holdout_2"] = load_holdout2_panel()

    results = {}
    for pname, panel in panels.items():
        po = {}
        for tspec in transforms:
            for split in spec["evaluation_splits"].get(pname, []):
                po[tspec["id"]] = eval_transform(panel, split, tspec)
        results[pname] = po
        print(f"[{pname}] {len(po)} transform-splits", flush=True)

    # selection gate: DEVELOPMENT validation (net 25 bps mean > 0, bootstrap
    # CI lower > 0, then BH-FDR q=0.10 across the five pre-registered transforms)
    from packages.research import alpha_analysis as aa

    dev = results["development"]
    pvals, names = [], []
    for t in transforms:
        r = dev.get(t["id"])
        if r and r.get("status") == "OK" and r["net_25bps_ci95_pct"][0] > 0:
            pvals.append(r["net_25bps_p_le0"] + 1e-9)
            names.append(t["id"])
    gate = {"decision": {}, "selected": []}
    if pvals:
        qvals = aa.bh_fdr(pvals)
        for tid, (pv, qv) in zip(names, zip(pvals, qvals)):
            gate["decision"][tid] = {"p_value": round(pv, 4),
                                     "fdr_q": round(qv, 4),
                                     "reject_fdr010": bool(qv <= 0.10)}
        gate["selected"] = [t for t in names if gate["decision"][t]["reject_fdr010"]]

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "spec_source": str(SPEC_PATH),
        "selected_on_validation_gate": gate["selected"],
        "gate": gate,
        "results": results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {args.out} | validation-gate selected: {gate['selected']}")


if __name__ == "__main__":
    main()