"""Deep validation of the volatility signal `vol_rel20@1`.

Discipline: this is CONFIRMATION evidence for one feature (vol_rel20@1) that
survived the 105-hypothesis screen. The original FINAL-OOS window was already
scored during discovery and is NOT a fresh holdout; its numbers are disclosed
as such. Phases 2-9, 10 are computed on TRAIN/VALIDATION and on the (scored)
FINAL-OOS separately, all with a FIXED rule (daily long-top / short-bottom decile,
base cost 0.15% per side) — no parameter is selected from outcomes.

Outputs a machine-readable results dict (JSON) + console summary.
Checkpointed: saves after every phase, resumable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from packages.research.alpha_analysis import (
    SPLIT_ORDER,
    bh_fdr,
    block_bootstrap_ic,
    ic_stats,
    ls_daily_rows,
)
from packages.research.alpha_dataset import store_root

HORIZONS = [1, 2, 3, 5, 10, 20]
FOCUS = "vol_rel20"
PANEL_CACHE = store_root() / "alpha_panel.parquet"
SEED = 11
BASE_CPS = 0.0015  # 0.05% commission + 0.10% slippage per side


def load_panel() -> pd.DataFrame:
    p = pd.read_parquet(PANEL_CACHE)
    p.index = pd.MultiIndex.from_arrays(
        [p.index.get_level_values(0), p.index.get_level_values(1).tz_convert("Asia/Kolkata")])
    if "fwd_ret_2" not in p.columns:
        c = p.groupby(level="symbol")["close"].shift(-2)
        p["fwd_ret_2"] = c.div(p["close"]) - 1.0
    print(f"[panel] {len(p)} rows cached")
    return p


def dates_of(panel: pd.DataFrame) -> pd.Series:
    return pd.Series(panel.index.get_level_values("date"))


def daily_ls_mean(sub: pd.DataFrame, feature: str = FOCUS, horizon: int = 1,
                  coverage: float = 0.10) -> dict:
    """Daily-rebalanced long-top/short-bottom, equal-weight, gross (no costs)."""
    sub = sub.dropna(subset=[feature, f"fwd_ret_{horizon}"])
    if len(sub) < 200:
        return {"status": "INSUFFICIENT", "n": int(len(sub))}
    rows, _, _ = ls_daily_rows(sub, feature, horizon, coverage=coverage, cost_per_side=0.0)
    if len(rows) < 10:
        return {"status": "INSUFFICIENT", "dates": len(rows)}
    g = np.array([r["gross"] for r in rows])
    g = g[np.isfinite(g)]
    return {"status": "OK", "dates": int(len(g)),
            "daily_ls_mean_pct": round(float(g.mean()) * 100, 4),
            "tstat": round(float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))), 3)
            if len(g) > 1 and g.std(ddof=1) > 0 else 0.0,
            "pos_frac": round(float((g > 0).mean()), 4),
            "cum_gross_pct": round((np.prod(1 + g) - 1) * 100, 4)}


def date_slice(panel: pd.DataFrame, start, end) -> pd.DataFrame:
    d = panel.index.get_level_values("date")
    return panel[(d >= start) & (d < end)]


def run_phase(out_path: Path, results: dict, name: str, fn) -> None:
    done = results.setdefault("done", [])
    if name in done:
        print(f"[skip] {name}")
        return
    print(f"\n=== {name} ===", flush=True)
    fn()
    done.append(name)
    with out_path.open("w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"[saved] {out_path} ({name})", flush=True)


class WindowEval:
    """Reusable per-window metrics for one (feature, horizon) on a date slice."""

    def __init__(self, panel: pd.DataFrame, start, end, feature: str = FOCUS,
                 horizon: int = 1, cps: float = BASE_CPS, n_boot: int = 150):
        sub = date_slice(panel, start, end).dropna(subset=[feature, f"fwd_ret_{horizon}"])
        self.sub = sub
        self.feature, self.horizon = feature, horizon
        x = sub[feature].to_numpy(float)
        y = sub[f"fwd_ret_{horizon}"].to_numpy(float)
        sym = sub.index.get_level_values("symbol").to_numpy()
        dt = sub.index.get_level_values("date").to_numpy()
        self.ic = ic_stats(x, y, sym)
        self.boot = block_bootstrap_ic(x, y, dt, sym, n_sims=n_boot, seed=SEED)
        self.ls = daily_ls_mean(sub, feature, horizon)

    def summary(self) -> dict:
        return {
            "n": int(len(self.sub)),
            "symbols": int(self.sub.index.get_level_values("symbol").nunique()),
            "windows_dates": self.window_dates(),
            "spearman_ic": self.ic.get("spearman_ic"),
            "ic_pvalue": self.ic.get("pvalue"),
            "median_fwd_ret_pct": round(float(self.sub[f"fwd_ret_{self.horizon}"].median()) * 100, 4),
            "boot_ci95": [self.boot.get("ci95_lo"), self.boot.get("ci95_hi")],
            "daily_ls_mean_pct": self.ls.get("daily_ls_mean_pct"),
            "ls_tstat": self.ls.get("tstat"),
        }

    def window_dates(self):
        try:
            return [str(x) for x in (self.sub.index.get_level_values("date").min(),
                                     self.sub.index.get_level_values("date").max())]
        except Exception:
            return []


def daily_quantile_shape(sub: pd.DataFrame, feature: str = FOCUS, horizon: int = 1,
                         q: int = 5) -> dict:
    """Daily-aggregated quantile profile: bucket means, deciles, shape classification."""
    data = sub.dropna(subset=[feature, f"fwd_ret_{horizon}"])
    if len(data) < 200:
        return {"status": "INSUFFICIENT"}
    w = data.copy()
    w["dt"] = w.index.get_level_values("date")
    w["pct"] = w.groupby("dt")[feature].rank(method="average", pct=True)
    w["bucket"] = (w["pct"] * q).clip(upper=q - 1).astype(int) + 1
    w["decile"] = (w["pct"] * 10).clip(upper=9).astype(int) + 1
    daily_b = w.groupby(["dt", "bucket"])[f"fwd_ret_{horizon}"].mean().unstack(level="bucket")
    daily_d = w.groupby(["dt", "decile"])[f"fwd_ret_{horizon}"].mean().unstack(level="decile")
    b = daily_b.mean().sort_index() * 100
    d = daily_d.mean().sort_index() * 100
    b_vals = [round(float(b.get(i, np.nan)), 4) for i in range(1, q + 1)]
    d_vals = [round(float(d.get(i, np.nan)), 4) for i in range(1, 11)]
    rho_m = None
    if q >= 3:
        idx = np.arange(1, q + 1)
        valid = ~np.isnan(b_vals)
        if valid.sum() >= 3:
            rho_m = float(np.corrcoef(idx[valid], np.asarray(b_vals)[valid])[0, 1])
    shape = classify_shape(b, d)
    return {"status": "OK", "n": int(len(w)),
            "bucket_means_pct": b_vals, "decile_means_pct": d_vals,
            "q1_pct": b_vals[0], "qq_pct": b_vals[-1],
            "spread_pct": round(float(b_vals[-1] - b_vals[0]), 4),
            "long_top_pct": b_vals[-1], "short_bottom_pct": b_vals[0],
            "monotonic_rho": (round(rho_m, 4) if rho_m is not None else None),
            "shape": shape}


def classify_shape(b: pd.Series, d: pd.Series) -> str:
    """One of monotonic / u_shaped / inverted_u / threshold_* / outlier_driven / unstable."""
    bv = np.asarray([float(x) for x in b], dtype=float)
    dc = np.asarray([float(x) for x in d], dtype=float)
    if np.isnan(bv).any() or np.isnan(dc).any():
        return "insufficient"
    mid = bv[1:-1] if len(bv) >= 3 else bv
    lo, hi = bv[0], bv[-1]
    spread = hi - lo
    scale = max(abs(bv).max(), 1e-9)
    if abs(spread) < 0.05 * scale:
        return "unstable"
    # outlier-driven: extreme decile dominates the spread
    if dc.size >= 10 and abs((dc[-1] - dc[-2])) > abs(dc[0] - dc[1]) * 1.5 and \
            abs(dc[-1] - dc[-2]) > 0.4 * abs(spread):
        return "outlier_driven_top"
    if dc.size >= 10 and abs((dc[0] - dc[1])) > abs(dc[-1] - dc[-2]) * 1.5 and \
            abs(dc[0] - dc[1]) > 0.4 * abs(spread):
        return "outlier_driven_bottom"
    if spread > 0:
        # increasing pattern?
        if np.allclose(np.diff(bv) > 0, True) or (bv[-1] > bv[0] and np.mean(np.diff(bv)) > 0
                                                  and abs(np.diff(bv)).max() < 2 * abs(np.mean(np.diff(bv)))):
            return "monotonic_increasing"
        if bv[0] > np.median(bv) and bv[-1] > np.median(bv) and bv[(len(bv) - 1) // 2] < min(bv[0], bv[-1]):
            return "u_shaped"
        if bv[1:-1].max() > max(bv[0], bv[-1]) and abs(bv.max() - bv.min()) > 0.3 * abs(spread):
            return "inverted_u"
        # threshold: flat except the highest bucket
        inner = bv[:-1][1:] if len(bv) > 3 else bv[:-1][:1]
        if abs(inner - bv[0]).max() < 0.2 * spread:
            return "threshold_top"
        return "non_monotonic_positive"
    else:
        if abs(np.diff(bv)).max() < 0.2 * abs(spread):
            return "non_monotonic_negative"
        inner = bv[:-1][1:] if len(bv) > 3 else bv[:-1][:1]
        if abs(inner - bv[0]).max() < 0.2 * abs(spread):
            return "threshold_bottom_beneficial"
        return "non_monotonic_negative"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/volatility_alpha_validation.json")
    ap.add_argument("--from-scratch", action="store_true")
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not args.from_scratch:
        results = json.loads(out_path.read_text())
        print(f"[resume] {len(results.get('done', []))} phases done")
    else:
        results = {"generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                   "feature": FOCUS, "horizon": 1,
                   "rule": "daily-rebalanced long-top / short-bottom decile (10/10), equal weight",
                   "cost_model": {"commission_per_side": 0.0005, "slippage_per_side": 0.0010,
                                  "base_cost_per_side": BASE_CPS},
                   "holdout_status": "FINAL-OOS was scored during discovery; NOT an independent follow-up holdout",
                   "done": []}
        with out_path.open("w") as fh:
            json.dump(results, fh, indent=2, default=str)

    panel = load_panel()
    all_dates = pd.Index(np.sort(pd.unique(dates_of(panel))))
    d0, d1 = all_dates[0], all_dates[-1]

    # ---------- PHASE 2: temporal (walk-forward) replication ----------
    def phase2():
        wins = []
        span = 126
        start_idx = 120 + span
        n_w = 24
        for i in range(n_w):
            b = start_idx + i * span
            m = b + span
            e = m + span
            if e + 1 >= len(all_dates):
                break
            t_start, t_val, t_oos = all_dates[0], all_dates[b], all_dates[e]
            train_p = date_slice(panel, d0, all_dates[b])
            val_p = date_slice(panel, all_dates[b], all_dates[m])
            oos_p = date_slice(panel, all_dates[m], all_dates[e])
            if len(oos_p) < 200:
                continue
            ev = WindowEval(panel, all_dates[m], all_dates[e])
            ic_val = ic_stats(val_p[FOCUS].to_numpy(float), val_p["fwd_ret_1"].to_numpy(float),
                              val_p.index.get_level_values("symbol").to_numpy()).get("spearman_ic")
            rows, _, _ = ls_daily_rows(oos_p, FOCUS, 1, coverage=0.10, cost_per_side=BASE_CPS)
            if len(rows) >= 10:
                net_cum = (np.prod([1 + r["net"] for r in rows]) - 1) * 100
                gt = [r["gross"] for r in rows]
                gross_cum = (np.prod([1 + r for r in gt]) - 1) * 100
                drag = gross_cum - net_cum
                to = np.array([r["turnover"] for r in rows])
                cost = {"gross_cum_pct": round(gross_cum, 3), "net_cum_pct": round(net_cum, 3),
                        "drag_pct": round(drag, 3),
                        "avg_turnover": round(float(to.mean()), 4),
                        "turnover_p90": round(float(np.quantile(to, 0.9)), 4)}
            else:
                cost = None
            wins.append({**ev.summary(),
                         "train": str(t_start.date()), "validation_start": str(t_val.date()),
                         "oos_start": str(all_dates[m].date()), "oos_end": str(all_dates[e].date()),
                         "validation_ic": ic_val,
                         "net_after_base_costs": cost["net_cum_pct"] if cost else None,
                         "cost": cost})
        results["temporal_replication"] = {
            "window_days_in_oos": span,
            "windows": wins,
            "n_windows": len(wins),
            "positive_net_windows": int(sum(1 for w in wins if (w.get("net_after_base_costs") or 0) > 0)),
            "net_avg_pct": round(float(np.mean([w.get("net_after_base_costs") or 0 for w in wins])), 3),
            "net_stdev_pct": round(float(np.std([w.get("net_after_base_costs") or 0 for w in wins])), 3),
            "median_daily_ls_pct": round(float(np.median([w.get("daily_ls_mean_pct") or 0 for w in wins])), 4),
        }
        tr = results["temporal_replication"]
        print(f"{tr['n_windows']} windows; positive-net {tr['positive_net_windows']}; "
              f"avg net {tr['net_avg_pct']}% stdev {tr['net_stdev_pct']}%; "
              f"median daily LS {tr['median_daily_ls_pct']}%")

    run_phase(out_path, results, "phase2_temporal_replication", phase2)

    # ---------- PHASE 3: cross-sectional quantile shape ----------
    def phase3():
        shape = {}
        for sp in SPLIT_ORDER:
            shape[sp] = daily_quantile_shape(panel[panel["split"] == sp])
        results["quantile_shape"] = shape
        for sp in SPLIT_ORDER:
            s = shape.get(sp, {})
            print(f"  {sp:12s} {s.get('shape')} spread {s.get('spread_pct')}% "
                  f"buckets {s.get('bucket_means_pct')}")

    run_phase(out_path, results, "phase3_quantile_shape", phase3)

    # ---------- PHASE 4: symbol robustness ----------
    def phase4():
        oos = panel[panel["split"] == "final_oos"].dropna(subset=[FOCUS, "fwd_ret_1"])
        oos = oos.copy()
        oos["dt"] = oos.index.get_level_values("date")
        rows = []
        n_days = oos["dt"].nunique()
        bounds = pd.Index(np.sort(pd.unique(oos["dt"])))[::max(1, n_days // 8)]
        bounds = bounds.tolist() + [np.sort(pd.unique(oos["dt"]))[-1]]
        contribs = {}
        for date, g in oos.groupby("dt"):
            g = g.sort_values(FOCUS)
            n = len(g); k = max(1, int(round(n * 0.10)))
            top = g.index[-k:]; bottom = g.index[:k]
            for idx in top:
                contribs[idx] = g.loc[idx, "fwd_ret_1"] / k
            for idx in bottom:
                contribs[idx] = -g.loc[idx, "fwd_ret_1"] / k
        for sym, g in oos.groupby(level="symbol"):
            x = g[FOCUS].to_numpy(float); y = g["fwd_ret_1"].to_numpy(float)
            st = ic_stats(x, y, np.full(len(y), sym))
            c = np.array([contribs.get(idx, 0.0) for idx in g.index])
            pos_w = 0
            for i in range(len(bounds) - 1):
                lo, hi = bounds[i], bounds[i + 1]
                chunk = g[(g["dt"] >= lo) & (g["dt"] < hi)]
                if len(chunk) and np.sum([contribs.get(idx, 0.0) for idx in chunk.index]) > 0:
                    pos_w += 1
            rows.append({"symbol": sym, "n": int(len(g)),
                         "mean_fwd_pct": round(float(g["fwd_ret_1"].mean()) * 100, 4),
                         "median_fwd_pct": round(float(g["fwd_ret_1"].median()) * 100, 4),
                         "ic": st.get("spearman_ic"),
                         "hit_rate": round(float((g["fwd_ret_1"] > 0).mean()), 4),
                         "ls_contrib_daily_pct": round(float(c.mean()) * 100, 5),
                         "ls_contrib_sum_pct": round(float(c.sum()) * 100, 4),
                         "positive_windows": pos_w, "total_windows": len(bounds) - 1})
        df = pd.DataFrame(rows)
        pos = df[df["ls_contrib_sum_pct"] > 0]
        abs_c = df["ls_contrib_sum_pct"].abs()
        hhi = float(((abs_c / abs_c.sum()) ** 2).sum())
        top5 = df.sort_values("ls_contrib_sum_pct", key=abs, ascending=False).head(5)
        results["symbol_robustness"] = {
            "symbols": rows,
            "n_symbols": int(len(df)),
            "n_positive": int(len(pos)),
            "frac_positive": round(float(len(pos) / len(df)), 3),
            "total_net_sum_pct": round(float(df["ls_contrib_sum_pct"].sum()), 3),
            "top_symbol_share_of_total": round(float(df["ls_contrib_sum_pct"].max()) /
                                               max(df["ls_contrib_sum_pct"].sum(), 1e-12), 3),
            "top5_share_of_total": round(float(top5["ls_contrib_sum_pct"].sum()) /
                                         max(df["ls_contrib_sum_pct"].sum(), 1e-12), 3),
            "hhi_of_abs_contrib": round(float(hhi), 4),
            "n_obs_min": int(df["n"].min()),
            "median_ic": round(float(df["ic"].median()), 4),
            "frac_positive_ic": round(float((df["ic"] > 0).mean()), 3),
        }
        s = results["symbol_robustness"]
        print(f"{s['n_positive']}/{s['n_symbols']} symbols positive; top-1 share "
              f"{s['top_symbol_share_of_total']}; top-5 share {s['top5_share_of_total']}; "
              f"HHI {s['hhi_of_abs_contrib']}")

    run_phase(out_path, results, "phase4_symbol_robustness", phase4)

    # ---------- PHASE 5: regime robustness ----------
    def phase5():
        regime = {}
        for period, mask in [("train_validation", panel["split"].isin(["train", "validation"])),
                             ("final_oos", panel["split"] == "final_oos")]:
            sub = panel[mask].dropna(subset=["regime_bucket", FOCUS, "fwd_ret_1"])
            buckets = {}
            for bucket, g in sub.groupby("regime_bucket"):
                if len(g) < 200:
                    continue
                st = ic_stats(g[FOCUS].to_numpy(float), g["fwd_ret_1"].to_numpy(float),
                              g.index.get_level_values("symbol").to_numpy())
                ls = daily_ls_mean(g)
                buckets[bucket] = {"n": int(len(g)),
                                   "ic": st.get("spearman_ic"),
                                   "daily_ls_mean_pct": ls.get("daily_ls_mean_pct"),
                                   "ls_tstat": ls.get("tstat")}
            regime[period] = buckets
        # coarse market regimes: direction (mkt_ret_20d sign) x vol tercile (mkt_vol_pctile_252)
        coarse = {}
        for period, mask in [("train_validation", panel["split"].isin(["train", "validation"])),
                             ("final_oos", panel["split"] == "final_oos")]:
            sub = panel[mask].dropna(subset=["mkt_ret_20d", "mkt_vol_pctile_252", FOCUS, "fwd_ret_1"])
            sub = sub.copy()
            sub["dirg"] = np.where(sub["mkt_ret_20d"] > 0, "up", "down")
            sub["volg"] = pd.cut(sub["mkt_vol_pctile_252"], [0, 0.33, 0.66, 1.0],
                                 labels=["low_vol", "med_vol", "high_vol"])
            sub["creg"] = sub["dirg"] + "|" + sub["volg"].astype(str)
            out = {}
            for creg, g in sub.groupby("creg"):
                if len(g) < 200:
                    continue
                st = ic_stats(g[FOCUS].to_numpy(float), g["fwd_ret_1"].to_numpy(float),
                              g.index.get_level_values("symbol").to_numpy())
                out[creg] = {"n": int(len(g)), "ic": st.get("spearman_ic")}
            coarse[period] = out
        results["regime_robustness"] = {"regime_bucket": regime, "market_regime": coarse}
        rb = results["regime_robustness"]["regime_bucket"]
        for b in sorted(set(rb.get("train_validation", {})) & set(rb.get("final_oos", {}))):
            a, c = rb["train_validation"][b], rb["final_oos"][b]
            same = (a["ic"] > 0) == (c["ic"] > 0)
            print(f"  {b:18s} t/v IC {a['ic']:+.4f} | oos IC {c['ic']:+.4f} same-sign={same}")

    run_phase(out_path, results, "phase5_regime_robustness", phase5)

    # ---------- PHASE 6: outlier / concentration ----------
    def phase6():
        oos = panel[panel["split"] == "final_oos"].dropna(subset=[FOCUS, "fwd_ret_1"]).copy()
        y = oos["fwd_ret_1"]
        variants = {}
        variants["full"] = oos
        absy = y.abs()
        oos_d = oos.copy(); oos_d["key"] = np.arange(len(oos_d))
        def _drop(n_keep_mask):
            return oos_d[n_keep_mask].drop(columns="key")
        variants["drop_top1_by_abs"] = _drop(~(absy == absy.max()))
        variants["drop_top5_by_abs"] = _drop(~absy.isin(absy.nlargest(5)))
        k1pct = max(1, int(round(len(oos) * 0.01)))
        variants["drop_top1pct_by_abs"] = _drop(~absy.isin(absy.nlargest(k1pct)))
        # winsorize labels at 1/99 pct
        w = oos.copy()
        lo99, hi99 = y.quantile(0.01), y.quantile(0.99)
        w["fwd_ret_1"] = y.clip(lo99, hi99)
        variants["winsorize_1_99"] = w
        out = {}
        for name, sub in variants.items():
            if name == "full":
                n = len(sub)
            else:
                n = int(sub["fwd_ret_1"].notna().sum())
            ls = daily_ls_mean(sub)
            qs = daily_quantile_shape(sub)
            rows, _, _ = ls_daily_rows(sub.drop(columns="key") if "key" in sub.columns else sub,
                                       FOCUS, 1, coverage=0.10, cost_per_side=BASE_CPS)
            net = (np.prod([1 + r["net"] for r in rows]) - 1) * 100 if len(rows) >= 10 else None
            out[name] = {"n": int(n), "daily_ls_mean_pct": ls.get("daily_ls_mean_pct"),
                         "quintile_spread_pct": qs.get("spread_pct"),
                         "shape": qs.get("shape"),
                         "net_after_costs_pct": (round(net, 3) if net is not None else None)}
            print(f"  {name:22s} LS {out[name]['daily_ls_mean_pct']}% "
                  f"spread {out[name]['quintile_spread_pct']}% net {out[name]['net_after_costs_pct']}%")
        base = out["full"]
        keep_frac = out["drop_top1pct_by_abs"].get("net_after_costs_pct") or 0
        basef = base.get("net_after_costs_pct") or 0
        results["outlier_concentration"] = {
            "variants": out,
            "net_retained_after_drop1pct_frac": round(keep_frac / basef, 3) if basef else None,
            "assessment": ("OUTLIER-DEPENDENT" if (basef and abs(keep_frac / basef) < 0.5)
                           else "NOT OUTLIER-DEPENDENT")}

    run_phase(out_path, results, "phase6_outlier_concentration", phase6)

    # ---------- PHASE 7: horizon curve ----------
    def phase7():
        curve = {}
        for sp in SPLIT_ORDER:
            per = {}
            for h in HORIZONS:
                sub = panel[panel["split"] == sp].dropna(subset=[FOCUS, f"fwd_ret_{h}"])
                if len(sub) < 200:
                    per[str(h)] = {"status": "INSUFFICIENT"}
                    continue
                st = ic_stats(sub[FOCUS].to_numpy(float), sub[f"fwd_ret_{h}"].to_numpy(float),
                              sub.index.get_level_values("symbol").to_numpy())
                ls = daily_ls_mean(sub, horizon=h)
                per[str(h)] = {"ic": st.get("spearman_ic"), "daily_ls_mean_pct": ls.get("daily_ls_mean_pct"),
                               "ls_tstat": ls.get("tstat"), "n": int(len(sub))}
            curve[sp] = per
        results["horizon_curve"] = curve
        for h in HORIZONS:
            f = curve["final_oos"].get(str(h), {})
            print(f"  h={h:2d} oos IC {f.get('ic'):+.4f} LS {f.get('daily_ls_mean_pct')}% t={f.get('ls_tstat')}")

    run_phase(out_path, results, "phase7_horizon_curve", phase7)

    # ---------- PHASE 8: alternative volatility definitions ----------
    def phase8():
        family = ["vol_rel20", "vol_pctile_252", "vol_atr_pct", "vol_trend_10v50", "vol_realized20"]
        hyps = [(f, h) for f in family for h in [1, 3, 5]]
        rows = []
        for f, h in hyps:
            for sp in SPLIT_ORDER:
                sub = panel[panel["split"] == sp].dropna(subset=[f, f"fwd_ret_{h}"])
                if len(sub) < 200:
                    continue
                st = ic_stats(sub[f].to_numpy(float), sub[f"fwd_ret_{h}"].to_numpy(float),
                              sub.index.get_level_values("symbol").to_numpy())
                rows.append({"feature": f, "horizon": h, "split": sp,
                             "ic": st.get("spearman_ic"), "pvalue": st.get("pvalue"),
                             "n": int(len(sub))})
        val_p = [r["pvalue"] for r in rows if r["split"] == "validation"]
        q_vals = bh_fdr(val_p)
        qi = 0
        for r in rows:
            if r["split"] == "validation":
                r["fdr_q"] = round(float(q_vals[qi]), 4) if qi < len(q_vals) else None
                qi += 1
        results["alt_volatility"] = {"family": family, "horizons": [1, 3, 5],
                                     "hypotheses_tested": len(hyps), "rows": rows}
        surv = [r for r in rows if r["split"] == "validation" and (r.get("fdr_q") is not None)
                and r["fdr_q"] <= 0.10 and (r["pvalue"] or 1) < 0.05]
        results["alt_volatility"]["val_survivors_fdr"] = [{"feature": s["feature"], "horizon": s["horizon"],
                                                           "q": s["fdr_q"]} for s in surv]
        print(f"alt-vol family: {len(hyps)} hyps; val FDR<=0.10 survivors: {len(surv)}")

    run_phase(out_path, results, "phase8_alt_volatility", phase8)

    # ---------- PHASE 9: cost / turnover ladder ----------
    def phase9():
        ladder = {}
        for sp in ["validation", "final_oos"]:
            sub = panel[panel["split"] == sp].dropna(subset=[FOCUS, "fwd_ret_1"])
            per = {}
            for cps in [0.0015, 0.0020, 0.0025, 0.0030]:
                rows, _, _ = ls_daily_rows(sub, FOCUS, 1, coverage=0.10, cost_per_side=cps)
                if len(rows) < 10:
                    continue
                g = np.array([r["gross"] for r in rows])
                n = np.array([r["net"] for r in rows])
                to = np.array([r["turnover"] for r in rows])
                gross = (np.prod(1 + g) - 1) * 100
                net = (np.prod(1 + n) - 1) * 100
                per[str(cps)] = {"gross_cum_pct": round(gross, 3), "net_cum_pct": round(net, 3),
                                 "drag_pct": round(gross - net, 3),
                                 "gross_minus_net_ratio": round((gross - net) / max(gross, 1e-12), 3),
                                 "avg_turnover": round(float(to.mean()), 4),
                                 "turnover_p50": round(float(np.quantile(to, 0.50)), 4),
                                 "turnover_p90": round(float(np.quantile(to, 0.90)), 4),
                                 "turnover_max": round(float(to.max()), 4)}
            ladder[sp] = per
        results["cost_turnover"] = ladder
        for sp in ["validation", "final_oos"]:
            for cps, r in ladder[sp].items():
                print(f"  [{sp}] cps={cps} gross {r['gross_cum_pct']} drag {r['drag_pct']} "
                      f"net {r['net_cum_pct']}% (to p50 {r['turnover_p50']})")

    run_phase(out_path, results, "phase9_cost_turnover", phase9)

    # ---------- PHASE 10: randomization controls ----------
    def phase10():
        oos = panel[panel["split"] == "final_oos"].dropna(subset=[FOCUS, "fwd_ret_1"])
        oos = oos.copy(); oos["dt"] = oos.index.get_level_values("date")
        sims = 300
        rng = np.random.default_rng(SEED)
        # full D x N matrices (NaN where a symbol is absent that date)
        feat = oos[FOCUS].unstack(level="symbol")
        fwdm = oos["fwd_ret_1"].unstack(level="symbol")
        Fm = fwdm.to_numpy(dtype=float)
        Vm = feat.to_numpy(dtype=float)
        D, Ns = Vm.shape
        valid = ~np.isnan(Vm)
        # per-date top/bottom index sets from a rank matrix R (NaN -> -inf)
        def _rankpick(Rm):
            R = np.where(valid, Rm, -np.inf)
            order = np.argsort(R, axis=1)  # last k = top (LONG), first k = bottom (SHORT)
            k_by = np.zeros(D, dtype=int)
            for di in range(D):
                k_by[di] = max(1, int(round(valid[di].sum() * 0.10)))
            picks = np.full((D, 2, valid.shape[1]), -1, dtype=int)
            for di in range(D):
                kd = k_by[di]
                picks[di, 1, :kd] = order[di, -kd:]          # top (last k)
                picks[di, 0, :kd] = order[di, :kd]           # bottom (first k)
            return picks
        def _ls_array(picks, Fm_):
            top_ok = picks[:, 1, 0] >= 0
            vals = np.zeros(D)
            for di in range(D):
                if not top_ok[di]:
                    vals[di] = np.nan
                    continue
                kd = int((picks[di, 1] >= 0).sum())
                vals[di] = np.nanmean(Fm_[di, picks[di, 1, :kd]]) - np.nanmean(Fm_[di, picks[di, 0, :kd]])
            return vals[np.isfinite(vals)]
        obs = _ls_array(_rankpick(Vm), Fm).mean()
        def _null(kind):
            out = np.empty(sims)
            for s in range(sims):
                if kind == "shuffle_feature":
                    Vs = Vm.copy()
                    for j in range(Ns):
                        rows = np.where(valid[:, j])[0]
                        if rows.size:
                            Vs[rows, j] = Vs[rows[rng.permutation(rows.size)], j]
                    picks = _rankpick(Vs)
                    out[s] = _ls_array(picks, Fm).mean()
                elif kind == "random_rank":
                    Rs = rng.random((D, Ns))
                    out[s] = _ls_array(_rankpick(Rs), Fm).mean()
                else:  # shuffle_label: permute returns within symbol, keep observed ranking
                    Fs = Fm.copy()
                    for j in range(Ns):
                        rows = np.where(valid[:, j])[0]
                        if rows.size:
                            Fs[rows, j] = Fs[rows[rng.permutation(rows.size)], j]
                    picks = _rankpick(Vm)
                    out[s] = _ls_array(picks, Fs).mean()
            return out
        nul = {k: _null(k) for k in ["shuffle_feature", "random_rank", "shuffle_label"]}
        results["randomization"] = {
            "obs_daily_ls_mean_pct": round(float(obs) * 100, 4),
            "n_dates": D, "sims": sims,
            "null": {k: {"mean_pct": round(float(v.mean()) * 100, 4),
                         "sd_pct": round(float(v.std()) * 100, 4),
                         "p_two_sided": round(float((np.abs(v) >= abs(obs)).mean()), 4),
                         "p_gt_obs": round(float((v >= obs).mean()), 4)} for k, v in nul.items()}}
        for k, v in results["randomization"]["null"].items():
            print(f"  {k:16s} null mean {v['mean_pct']}% sd {v['sd_pct']}% p2 {v['p_two_sided']}")

    run_phase(out_path, results, "phase10_randomization", phase10)

    # ---------- PHASE 11: selection-bias audit ----------
    def phase11():
        results["selection_bias_audit"] = {
            "discovery_context": "vol_rel20@1 was screened from 105 (feature x horizon) hypotheses; "
                                 "54 sign+magnitude preselected; BH-FDR q<=0.10 on VALIDATION; 31 survived "
                                 "including vol_rel20@1 and vol_rel20@3.",
            "evidence_types": {
                "DISCOVERY": ["105-hypothesis screen", "FINAL-OOS scored once (selection-free but NOT a fresh holdout)"],
                "CONFIRMATION": ["This deep-validation run: fixed rule (no params to select), TRAIN/VALIDATION windows, "
                                 "randomization, cost ladder, symbol/regime robustness"]},
            "caveats": ["Follow-up statistics are NOT an independent experiment: the same period that surfaced the "
                        "candidate is re-scored here.",
                        "Any p-value in this report is PRE-EXPERIMENTAL conditioning on survival of the screen; "
                        "they overstate confidence."],
            "validation_used_for_selection": True,
        }
        print("selection-bias audit recorded (DISCOVERY vs CONFIRMATION, 105-hypothesis context)")

    run_phase(out_path, results, "phase11_selection_bias_audit", phase11)

    # ---------- PHASE 12: final holdout ----------
    def phase12():
        frozen = {}
        if len(all_dates) < 260:
            frozen["status"] = "insufficient data"
        else:
            last_year_start = all_dates[-252]
            sub = date_slice(panel, last_year_start, all_dates[-1])
            ls = daily_ls_mean(sub)
            rows, _, _ = ls_daily_rows(sub, FOCUS, 1, coverage=0.10, cost_per_side=BASE_CPS)
            if len(rows) >= 10:
                net = (np.prod([1 + r["net"] for r in rows]) - 1) * 100
                g = np.array([r["gross"] for r in rows])
                gross = (np.prod(1 + g) - 1) * 100
            else:
                net = gross = None
            frozen = {"window": [str(last_year_start.date()), str(all_dates[-1].date())],
                      "n": int(len(sub)), "daily_ls_mean_pct": ls.get("daily_ls_mean_pct"),
                      "gross_cum_pct": (round(gross, 3) if gross is not None else None),
                      "net_cum_pct": (round(net, 3) if net is not None else None)}
        results["final_holdout"] = {
            "available": False,
            "reason": ("The dataset ends 2026-09-04. The entire FINAL-OOS period (2025-07-01..2026-09-04) was "
                       "scored during the discovery phase to produce the +29.9% figure. No chronological slice of "
                       "this corpus has NEVER been used, so no independent final holdout exists."),
            "frozen_eval_rerun_once_best_available_not_independent": frozen,
        }
        print(f"NO INDEPENDENT FINAL HOLDOUT AVAILABLE; frozen last-252d rerun: {frozen.get('net_cum_pct')}")

    run_phase(out_path, results, "phase12_final_holdout", phase12)

    # ---------- FINAL DECISION ----------
    def decide():
        tr_ = results.get("temporal_replication", {})
        sym_ = results.get("symbol_robustness", {})
        outl_ = results.get("outlier_concentration", {})
        hz_ = results.get("horizon_curve", {}).get("final_oos", {})
        alt_ = results.get("alt_volatility", {})
        cst_ = results.get("cost_turnover", {}).get("final_oos", {}).get("0.0025", {})
        rnd_ = results.get("randomization", {})
        reg_ = results.get("regime_robustness", {}).get("regime_bucket", {})
        schema = {
            "temporal": {"positive_net_windows_frac": round(
                (tr_.get("positive_net_windows", 0) / max(tr_.get("n_windows", 1), 1)), 2),
                "net_avg_pct": tr_.get("net_avg_pct")},
            "symbols": {"frac_positive": sym_.get("frac_positive"),
                        "top5_share": sym_.get("top5_share_of_total")},
            "outliers": {"assessment": outl_.get("assessment"),
                         "net_retained_after_drop1pct": outl_.get("net_retained_after_drop1pct_frac")},
            "horizon": {h: hz_.get(str(h), {}).get("ic") for h in HORIZONS},
            "alt_vol_family_survivors": alt_.get("val_survivors_fdr"),
            "cost_at_2p5bp_net_pct": cst_.get("net_cum_pct"),
            "randomization_p2": {k: v.get("p_two_sided") for k, v in rnd_.get("null", {}).items()},
            "regime_sign_stability": None,
        }
        if reg_:
            common = set(reg_.get("train_validation", {})) & set(reg_.get("final_oos", {}))
            if common:
                same = sum(1 for b in common
                           if (reg_["train_validation"][b]["ic"] > 0) == (reg_["final_oos"][b]["ic"] > 0))
                schema["regime_sign_stability"] = round(same / len(common), 2)
        results["decision_schema"] = schema
        # scoring
        score = 0
        reasons = []
        pos_frac = schema["temporal"]["positive_net_windows_frac"] or 0
        if pos_frac >= 0.5:
            score += 1; reasons.append(f"temporal positive-net windows {int(pos_frac * 100)}%")
        else:
            reasons.append(f"temporal positive-net windows only {int(pos_frac * 100)}%")
        frac_pos_sym = sym_.get("frac_positive") or 0
        if frac_pos_sym >= 0.6:
            score += 1; reasons.append(f"{int(frac_pos_sym * 100)}% of symbols positive")
        else:
            reasons.append(f"only {int(frac_pos_sym * 100)}% of symbols positive")
        if (outl_.get("assessment") or "") == "NOT OUTLIER-DEPENDENT":
            score += 1; reasons.append("not outlier-dependent")
        else:
            reasons.append("outlier-dependent")
        rx = rnd_.get("null", {}).get("shuffle_feature", {}).get("p_two_sided")
        if rx is not None and rx < 0.05:
            score += 1; reasons.append(f"randomization p={rx}")
        else:
            reasons.append(f"randomization p={rx}")
        hzs = [schema["horizon"][h] for h in HORIZONS]
        pos_neg = [1 if h and h > 0 else -1 if h and h < 0 else 0 for h in hzs]
        if all(x == 1 for x in pos_neg if x):
            score += 1; reasons.append("positive IC across full horizon curve")
        elif 0 < sum(1 for x in pos_neg if x == 1) <= 2:
            reasons.append("horizon curve mostly negative/zero")
        net25 = schema["cost_at_2p5bp_net_pct"]
        if net25 is not None and net25 > 0:
            score += 1; reasons.append(f"net positive at 2x costs ({net25}%)")
        else:
            reasons.append(f"net {net25}% at 2x costs (FRAGILE)")
        fs = results.get("final_holdout", {}).get("available")
        if fs:
            score += 1; reasons.append("independent holdout")
        else:
            reasons.append("no independent holdout available")
        reg_st = schema["regime_sign_stability"]
        if reg_st is not None and reg_st >= 0.7:
            score += 1; reasons.append(f"regime sign stable ({reg_st})")
        else:
            reasons.append(f"regime sign stability {reg_st}")

        if score >= 10:
            decision = "A. ROBUST ALPHA CANDIDATE"
        elif score >= 7:
            decision = "B. PROMISING BUT INSUFFICIENT DATA"
        elif "outlier-dependent" in " ".join(reasons).split("outlier-dependent"):
            decision = "C. OUTLIER-DRIVEN"
        elif net25 is not None and net25 <= 0:
            decision = "E. COST-FRAGILE"
        else:
            decision = "F. UNSTABLE"
        if results["final_holdout"].get("available") is False and decision == "A. ROBUST ALPHA CANDIDATE":
            decision = "B. PROMISING BUT INSUFFICIENT DATA"
        results["final_decision"] = {
            "decision": decision,
            "score": score, "max": 10,
            "reasons": reasons,
            "recommendation": {"action": "DO NOT trade this signal",
                               "next": "Extend the corpus (universe and/or history) so a GENUINELY untouched "
                                       "chronological holdout exists; re-run this exact frozen pipeline once on it. "
                                       "Only if the frozen test reproduces a positive net result should a "
                                       "pre-registered strategy spec be written.",
                               "strategy": "No strategy construction, no parameter tuning, no paper trading "
                                           "promotion (project HARD RULE)."}
        }
        print(f"\nFINAL DECISION: {decision}  (score {score}/{10})")
        for r in reasons:
            print("   -", r)

    run_phase(out_path, results, "final_decision", decide)

    with out_path.open("w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\ndone: {out_path}")


if __name__ == "__main__":
    main()