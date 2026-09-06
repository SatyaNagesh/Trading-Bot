"""Alpha V2 - post-freeze measurement engine (Phase 4-13).

Pipeline:
  SCAN       -> pooled rank IC per (feature, horizon) per split, both panels
  FDR-SEL    -> BH-FDR q<=0.10 on development VALIDATION -> candidates
  GATE       -> candidates with same-sign dev FINAL-OOS + |final|>=0.4|val| -> survivors
  DEEP       -> per-survivor: quantiles / ls / block-bootstrap / randomization /
                temporal / symbol / sector / liquidity / regime / incremental /
                costs / nonlinear
  G-TRACK    -> market-timing diagnostics for the breadth family (date-level)
  REPLICATE  -> survivors scored on the frozen holdout (report-only, no selection)

Classification policy (frozen spec): no A/C claim without a genuinely untouched
corpus (holdout_2 is locked for V1; the frozen 60-symbol holdout is consumed as
replication evidence, not confirmation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
from packages.research import alpha_analysis as aa
from packages.research.alpha_v2_features import CARRY, KEYS, PANELS, FAMILIES, F as FEATURES
from packages.research.vt_signal import SECTOR, sector_of

OUT_DIR = Path("data/alpha_v2")

G_KEYS = [k for k in KEYS if k.startswith("G")]
POOL_KEYS = [k for k in KEYS if not k.startswith("G")]
HORIZONS = sorted({1, 3, 5, 10, 20})
_FH = {f["key"]: f["horizons"] for f in FEATURES}
HYP_GRID = [(k, h) for k in POOL_KEYS for h in _FH[k]]
HYP_GRID_G = [(k, h) for k in G_KEYS for h in (1, 3, 5)]

WINDOW = 63
BOOT_SIMS = 250
NULL_SIMS = 200
COSTS = (0.0015, 0.0025, 0.0050)

SPLITS = ["train", "validation", "final_oos"]


def _sub(panel, split, feat, horizon):
    return panel[panel["split"] == split].dropna(subset=[feat, f"fwd_ret_{horizon}"])


def _syms(panel):
    return panel.index.get_level_values("symbol").to_numpy()


def scan(panel):
    rows = []
    for split in SPLITS:
        for feat, h in HYP_GRID:
            sub = _sub(panel, split, feat, h)
            if len(sub) >= aa.MIN_OBS_PER_IC:
                st = aa.ic_stats(sub[feat].to_numpy(), sub[f"fwd_ret_{h}"].to_numpy(),
                                 sub.index.get_level_values("symbol").to_numpy())
                rows.append({"split": split, "feature": feat, "horizon": h, "status": "OK",
                             "n": st["n"], "n_eff": st["n_eff"], "ic": st["spearman_ic"],
                             "ci95_lo": st["ci95_lo"], "ci95_hi": st["ci95_hi"],
                             "pvalue": st["pvalue"], "hit_rate": st["hit_rate"], "sign": st["sign"]})
            else:
                rows.append({"split": split, "feature": feat, "horizon": h,
                             "status": "INSUFFICIENT", "n": int(len(sub))})
    return rows


def temporal_banded_ic(panel, feat, horizon, window=WINDOW):
    keep = panel[panel["split"].isin(SPLITS)].dropna(subset=[feat, f"fwd_ret_{horizon}"]).copy()
    keep["dt"] = keep.index.get_level_values("date")
    dates = pd.Index(np.unique(keep["dt"])).sort_values()
    keep["band"] = dates.searchsorted(keep["dt"]) // window
    bands = []
    for b, g in keep.groupby("band"):
        if len(g) < aa.MIN_OBS_PER_IC:
            continue
        st = aa.ic_stats(g[feat].to_numpy(), g[f"fwd_ret_{horizon}"].to_numpy(),
                         g.index.get_level_values("symbol").to_numpy())
        bands.append({"band": int(b), "start": str(g["dt"].min())[:10], "end": str(g["dt"].max())[:10],
                      "n": st["n"], "ic": st["spearman_ic"], "pvalue": st["pvalue"]})
    ics = [r["ic"] for r in bands]
    out = {"n_bands": len(bands), "bands": bands,
           "frac_bands_ic_gt0": round(float(np.mean([i > 0 for i in ics])), 4),
           "best_band_ic": round(float(max(ics, default=np.nan)), 5),
           "worst_band_ic": round(float(min(ics, default=np.nan)), 5)}
    _t0 = pd.Timestamp("2023-01-01", tz="Asia/Kolkata")
    for name, cond in [("early_2014_2022", keep["dt"] < _t0),
                       ("late_2023_plus", keep["dt"] >= _t0)]:
        g = keep[cond]
        if len(g) < aa.MIN_OBS_PER_IC:
            out[name] = {"n": int(len(g)), "ic": None}
            continue
        st = aa.ic_stats(g[feat].to_numpy(), g[f"fwd_ret_{horizon}"].to_numpy(),
                         g.index.get_level_values("symbol").to_numpy())
        out[name] = {"n": st["n"], "ic": st["spearman_ic"], "pvalue": st["pvalue"]}
    return out


def _liquidity_means(d1d_dir):
    means = {}
    for p in sorted(Path(d1d_dir).glob("*.parquet")):
        df = pd.read_parquet(p, columns=["close", "volume"])
        v = (df["close"] * df["volume"]).replace(0, np.nan)
        means[p.stem] = float(np.log1p(v.mean()))
    return means


def symbol_breakdown(panel, feat, horizon, liq_means):
    keep = panel[panel["split"].isin(SPLITS)].dropna(subset=[feat, f"fwd_ret_{horizon}"])
    per_sym = []
    for sym, g in keep.groupby(level="symbol"):
        if len(g) < 200 or g[feat].nunique() < 3:
            continue
        rho = stats.spearmanr(g[feat], g[f"fwd_ret_{horizon}"])[0]
        per_sym.append({"symbol": sym, "n": int(len(g)), "ic": round(float(rho), 4)})
    per_sym = sorted(per_sym, key=lambda r: -abs(r["ic"]))
    icv = np.array([r["ic"] for r in per_sym], dtype=float)
    sectors = {}
    for r in per_sym:
        sectors.setdefault(sector_of(r["symbol"]), []).append(r["ic"])
    sec_rows = sorted([{"sector": s, "n_symbols": len(v), "median_ic": round(float(np.median(v)), 4),
                        "frac_pos": round(float(np.mean([i > 0 for i in v])), 4)}
                       for s, v in sectors.items()], key=lambda r: -abs(r["median_ic"]))
    liq_rows = {}
    if liq_means:
        arr = [(r["symbol"], r["ic"], liq_means.get(r["symbol"])) for r in per_sym]
        arr = [x for x in arr if x[2] is not None]
        if len(arr) >= 9:
            rows = pd.DataFrame(arr, columns=["symbol", "ic", "log_rupee_vol"])
            rows["tercile"] = pd.qcut(rows["log_rupee_vol"], 3, labels=["low", "mid", "high"])
            for t, g in rows.groupby("tercile"):
                if len(g) >= 3:
                    liq_rows[t] = {"n_symbols": int(len(g)), "median_ic": round(float(g["ic"].median()), 4),
                                   "frac_pos": round(float((g["ic"] > 0).mean()), 4)}
    return {"n_symbols": len(icv),
            "frac_sym_ic_gt0": round(float((icv > 0).mean()), 4) if len(icv) else None,
            "median_sym_ic": round(float(np.median(icv)), 4) if len(icv) else None,
            "best_syms": per_sym[:5], "worst_syms": per_sym[-5:],
            "sector_table": sec_rows, "liquidity_terciles": liq_rows}


def incremental_info(panel, feat, horizon):
    sub = panel[panel["split"] == "validation"].dropna(subset=[feat, f"fwd_ret_{horizon}"])
    exps = [c for c in CARRY if c in panel.columns and c not in ("split", "regime_bucket")
            and not c.startswith("fwd_ret")]
    if len(sub) < aa.MIN_OBS_PER_IC:
        return {"status": "INSUFFICIENT", "n": int(len(sub))}
    syms = _syms(sub)
    base = aa.ic_stats(sub[feat].to_numpy(), sub[f"fwd_ret_{horizon}"].to_numpy(), syms)
    per = {}
    for ex in exps:
        if sub[ex].nunique() < 5:
            continue
        ic_ = aa.partial_ic(sub[ex].to_numpy(), sub[feat].to_numpy(),
                            sub[f"fwd_ret_{horizon}"].to_numpy())
        per[ex] = round(float(ic_), 5) if ic_ is not None else None
    return {"status": "OK", "base_ic": base["spearman_ic"], "after_single": per}


def nonlinear_diag(panel, feat, horizon):
    sub = panel[panel["split"].isin(["train", "validation"])].dropna(subset=[feat, f"fwd_ret_{horizon}"])
    tr = sub[sub["split"] == "train"]
    va = sub[sub["split"] == "validation"]
    if len(tr) < 500 or len(va) < 200:
        return {"status": "INSUFFICIENT"}
    for g in (tr, va):
        g["rfeat"] = stats.rankdata(g[feat].to_numpy())
        g["ry"] = stats.rankdata(g[f"fwd_ret_{horizon}"].to_numpy())
    tr["rfeat2"] = tr["rfeat"] ** 2
    va["rfeat2"] = va["rfeat"] ** 2
    X1 = np.column_stack([np.ones(len(tr)), tr["rfeat"]])
    X2 = np.column_stack([np.ones(len(tr)), tr["rfeat"], tr["rfeat2"] - tr["rfeat2"].mean()])
    c1 = np.linalg.lstsq(X1, tr["ry"], rcond=None)[0]
    c2 = np.linalg.lstsq(X2, tr["ry"], rcond=None)[0]
    r1_tr = float(np.corrcoef(X1 @ c1, tr["ry"])[0, 1]) ** 2
    r2_tr = float(np.corrcoef(X2 @ c2, tr["ry"])[0, 1]) ** 2
    X1v = np.column_stack([np.ones(len(va)), va["rfeat"]])
    X2v = np.column_stack([np.ones(len(va)), va["rfeat"], va["rfeat2"] - tr["rfeat2"].mean()])
    ic_lin = float(stats.spearmanr(X1v @ c1, va[f"fwd_ret_{horizon}"])[0])
    ic_quad = float(stats.spearmanr(X2v @ c2, va[f"fwd_ret_{horizon}"])[0])
    return {"status": "OK", "n_train": len(tr), "n_val": len(va),
            "train_rsq": {"linear": round(r1_tr, 4), "quad": round(r2_tr, 4)},
            "val_rank_ic": {"linear": round(ic_lin, 5), "quad": round(ic_quad, 5)},
            "quad_beats_linear": bool(ic_quad > ic_lin)}


def g_market_timing(panel):
    out = {}
    keep = panel[panel["split"].isin(SPLITS)]
    for split in SPLITS:
        sub = keep[keep["split"] == split]
        for feat in G_KEYS:
            g = sub.dropna(subset=[feat]).groupby("date")[feat].mean()
            for h in (1, 3, 5):
                r = sub.groupby("date")[f"fwd_ret_{h}"].mean()
                df = pd.DataFrame({"g": g, "r": r}).dropna()
                key = f"{feat}|{h}|{split}"
                if len(df) < 30:
                    out[key] = None
                    continue
                rho, p = stats.spearmanr(df["g"], df["r"])
                hi = df.loc[df["g"] >= df["g"].quantile(0.8), "r"]
                lo = df.loc[df["g"] <= df["g"].quantile(0.2), "r"]
                out[key] = {"n_dates": int(len(df)), "ic": round(float(rho), 5), "p": round(float(p), 5),
                            "top_mean_pct": round(float(hi.mean()) * 100, 4),
                            "bottom_mean_pct": round(float(lo.mean()) * 100, 4),
                            "top_minus_bottom_pct": round(float((hi.mean() - lo.mean())) * 100, 4)}
    return out


def run(stage):
    OUT_DIR.mkdir(exist_ok=True)
    dev = None
    if stage in ("scan", "deep", "g"):
        dev = pd.read_parquet(OUT_DIR / "development_v2_panel.parquet")
        dev = dev[dev["split"] != ""]

    si = Path(OUT_DIR / "scan_results.json")
    if stage in ("scan", "deep", "g") and not si.exists():
        print("scanning development...", flush=True)
        dev_scan = scan(dev)
        df = pd.DataFrame(dev_scan)
        val = df[(df["split"] == "validation") & (df["status"] == "OK")].copy()
        val["q"] = aa.bh_fdr(val["pvalue"].tolist())
        cand = val[val["q"] <= 0.10]
        print(f"dev validation: {len(val)} hyps, {len(cand)} candidates q<=0.10", flush=True)

        finals_map = {(r["feature"], r["horizon"]): r for _, r in df[df["split"] == "final_oos"].iterrows()}
        surv = []
        for _, r in cand.iterrows():
            fr = finals_map.get((r["feature"], r["horizon"]))
            if fr is None or fr["status"] != "OK":
                continue
            sign_ok = fr["sign"] == r["sign"]
            mag_ok = fr["sign"] * fr["ic"] >= 0.4 * abs(r["ic"])
            surv.append({**r.to_dict(), "final_ic": fr["ic"], "final_p": fr["pvalue"],
                         "final_sign_ok": bool(sign_ok), "final_mag_ok": bool(mag_ok)})
        survivors = [s for s in surv if s["final_sign_ok"] and s["final_mag_ok"]]
        print(f"survivors (gate): {len(survivors)} of {len(surv)} sign-only", flush=True)

        OUT_DIR.mkdir(exist_ok=True)
        si.write_text(json.dumps(
            {"scan": dev_scan, "selection": "fdr_q<=0.10 on development/validation",
             "candidates": cand.to_dict("records"), "survivor_gate": survivors}, indent=1))
        with open(OUT_DIR / "survivor_list.json", "w") as f:
            json.dump([{"feature": s["feature"], "horizon": s["horizon"], "q": s["q"],
                        "val_ic": s["ic"], "final_ic": s["final_ic"]} for s in survivors], f, indent=1)

    if stage in ("deep", "g"):
        survivors = json.loads((OUT_DIR / "scan_results.json").read_text())["survivor_gate"]
        survivors = [s for s in survivors if s["final_sign_ok"] and s["final_mag_ok"]][:40]
    if stage == "deep":
        liq = {name: _liquidity_means(Path(PANELS[name][1])) for name in PANELS}
        doss = Path(OUT_DIR / "survivor_dossiers.json")
        dossiers = json.loads(doss.read_text()) if doss.exists() else {}
        for s in survivors:
            key = f"{s['feature']}|{s['horizon']}"
            if key in dossiers:
                continue
            feat, h = s["feature"], s["horizon"]
            print(f"deep {feat} h={h}...", flush=True)
            val = _sub(dev, "validation", feat, h)
            syms_val = val.index.get_level_values("symbol").to_numpy()
            dossiers[key] = {
                "family": feat[0], "feature": feat, "horizon": h,
                "quantile_profile": aa.quantile_profile(val[feat].to_numpy(), val[f"fwd_ret_{h}"].to_numpy()),
                "block_bootstrap": aa.block_bootstrap_ic(val[feat].to_numpy(), val[f"fwd_ret_{h}"].to_numpy(),
                                                         val.index.get_level_values("date").to_numpy(),
                                                         syms_val, n_sims=BOOT_SIMS),
                "randomized_null": aa.randomized_null(val[feat].to_numpy(), val[f"fwd_ret_{h}"].to_numpy(),
                                                      syms_val, n_shuffles=NULL_SIMS),
                "long_short_val": aa.long_short_by_date(dev, feat, h, "validation", 0.10),
                "long_short_oos": aa.long_short_by_date(dev, feat, h, "final_oos", 0.10),
                "incremental": incremental_info(dev, feat, h),
                "nonlinear": nonlinear_diag(dev, feat, h),
                "temporal": temporal_banded_ic(dev, feat, h),
                "costs": {str(bp): aa.cost_aware_ls(dev, feat, h, "validation", 0.10, bp) for bp in COSTS}
                         | {"oos_25bp": aa.cost_aware_ls(dev, feat, h, "final_oos", 0.10, 0.0025)},
                "regimes": {splt: aa.regime_ic(dev, feat, h, splt) for splt in SPLITS},
                "symbol": symbol_breakdown(dev, feat, h, liq["development"]),
            }
            doss.write_text(json.dumps(dossiers, indent=1))
        print(f"dossiers: {len(dossiers)} saved", flush=True)

    if stage == "g":
        print("g-family market timing...", flush=True)
        (OUT_DIR / "g_market_timing_dev.json").write_text(json.dumps(g_market_timing(dev), indent=1))
    if stage in ("deep", "g"):
        del dev

    if stage == "replicate":
        hold = pd.read_parquet(OUT_DIR / "holdout_v2_panel.parquet")
        hold = hold[hold["split"] != ""]
        (OUT_DIR / "g_market_timing_hold.json").write_text(json.dumps(g_market_timing(hold), indent=1))
        sv = json.loads((OUT_DIR / "survivor_list.json").read_text())
        rep = {}
        for s_ in sv:
            feat, h = s_["feature"], s_["horizon"]
            rep[f"{feat}|{h}"] = {}
            for splt in ["validation", "final_oos"]:
                sub = _sub(hold, splt, feat, h)
                if len(sub) >= aa.MIN_OBS_PER_IC:
                    st = aa.ic_stats(sub[feat].to_numpy(), sub[f"fwd_ret_{h}"].to_numpy(),
                                     sub.index.get_level_values("symbol").to_numpy())
                    rep[f"{feat}|{h}"][splt] = {"n": st["n"], "ic": st["spearman_ic"],
                                                "ci95": [st["ci95_lo"], st["ci95_hi"]],
                                                "pvalue": st["pvalue"], "sign": st["sign"]}
                else:
                    rep[f"{feat}|{h}"][splt] = {"n": int(len(sub)), "ic": None, "sign": None}
            sub = _sub(hold, "validation", feat, h)
            if len(sub) >= 200:
                rep[f"{feat}|{h}"]["cost_25bp"] = aa.cost_aware_ls(hold, feat, h, "validation", 0.10, 0.0025)
        (OUT_DIR / "holdout_replication.json").write_text(json.dumps(rep, indent=1))
        del hold
    print("done", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["scan", "deep", "g", "replicate", "all"])
    args = ap.parse_args()
    run(args.stage)