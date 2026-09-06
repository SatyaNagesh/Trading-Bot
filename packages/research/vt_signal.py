"""vol_trend_10v50 signal investigation — diagnostics (Phases 1-7, 11-13).

Pure diagnostic; produces NO trading rule and performs NO monetization
selection. Uses the DEVELOPMENT panel and the FROZEN HOLD OUT panel built by
the frozen `alpha_dataset.build_panel`. All statistics reuse the frozen
`alpha_analysis` engine where possible.

Output: reports/vt_signal_diagnostics.json
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

from packages.research import alpha_analysis as aa

FEATURE = "vol_trend_10v50"
HORIZONS = ["1", "3"]

# static sector labels (public NSE classification, snapshot 2026-09-06).
# No future information; used only for concentration reporting.
SECTOR = {
    "HDFCBANK.NS": "Banks", "ICICIBANK.NS": "Banks", "AXISBANK.NS": "Banks",
    "KOTAKBANK.NS": "Banks", "SBIN.NS": "Banks", "INDUSINDBK.NS": "Banks",
    "BANKBARODA.NS": "Banks", "PNB.NS": "Banks", "CANBK.NS": "Banks",
    "UNIONBANK.NS": "Banks", "INDIANB.NS": "Banks", "IDFCFIRSTB.NS": "Banks",
    "YESBANK.NS": "Banks",
    "BAJFINANCE.NS": "Financial Services", "BAJAJFINSV.NS": "Financial Services",
    "SBILIFE.NS": "Financial Services", "HDFCLIFE.NS": "Financial Services",
    "RECLTD.NS": "Financial Services", "PFC.NS": "Financial Services",
    "IRFC.NS": "Financial Services", "CDSL.NS": "Financial Services",
    "TCS.NS": "Information Technology", "INFY.NS": "Information Technology",
    "HCLTECH.NS": "Information Technology", "WIPRO.NS": "Information Technology",
    "TECHM.NS": "Information Technology", "LTIM.NS": "Information Technology",
    "MPHASIS.NS": "Information Technology", "PERSISTENT.NS": "Information Technology",
    "COFORGE.NS": "Information Technology",
    "MARUTI.NS": "Automobile", "M&M.NS": "Automobile", "BAJAJ_AUTO.NS": "Automobile",
    "EICHERMOT.NS": "Automobile", "HEROMOTOCO.NS": "Automobile",
    "TVSMOTOR.NS": "Automobile", "ASHOKLEY.NS": "Automobile",
    "BALKRISIND.NS": "Automobile", "MRF.NS": "Automobile",
    "APOLLOTYRE.NS": "Automobile", "MOTHERSON.NS": "Automobile",
    "CEATLTD.NS": "Automobile", "BHARATFORG.NS": "Automobile",
    "SUNPHARMA.NS": "Pharmaceuticals", "DIVISLAB.NS": "Pharmaceuticals",
    "DRREDDY.NS": "Pharmaceuticals", "CIPLA.NS": "Pharmaceuticals",
    "LUPIN.NS": "Pharmaceuticals", "AUROPHARMA.NS": "Pharmaceuticals",
    "ZYDUSLIFE.NS": "Pharmaceuticals", "TORNTPHARM.NS": "Pharmaceuticals",
    "ALKEM.NS": "Pharmaceuticals",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "BRITANNIA.NS": "FMCG",
    "NESTLEIND.NS": "FMCG", "GODREJCP.NS": "FMCG", "DABUR.NS": "FMCG",
    "MARICO.NS": "FMCG", "VBL.NS": "FMCG", "JUBLFOOD.NS": "FMCG",
    "TATASTEEL.NS": "Metals & Mining", "JSWSTEEL.NS": "Metals & Mining",
    "HINDALCO.NS": "Metals & Mining", "VEDL.NS": "Metals & Mining",
    "JINDALSTEL.NS": "Metals & Mining", "SAIL.NS": "Metals & Mining",
    "HINDZINC.NS": "Metals & Mining",
    "RELIANCE.NS": "Oil & Gas", "ONGC.NS": "Oil & Gas", "BPCL.NS": "Oil & Gas",
    "GAIL.NS": "Oil & Gas",
    "NTPC.NS": "Power & Utilities", "POWERGRID.NS": "Power & Utilities",
    "TATAPOWER.NS": "Power & Utilities", "ADANIPOWER.NS": "Power & Utilities",
    "NHPC.NS": "Power & Utilities",
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement", "AMBUJACEM.NS": "Cement",
    "LT.NS": "Construction & Infra", "ADANIPORTS.NS": "Construction & Infra",
    "ADANIENT.NS": "Construction & Infra", "DLF.NS": "Construction & Infra",
    "GODREJPROP.NS": "Construction & Infra", "OBEROIRLTY.NS": "Construction & Infra",
    "PRESTIGE.NS": "Construction & Infra",
    "TITAN.NS": "Consumer Durables & Retail", "TRENT.NS": "Consumer Durables & Retail",
    "DMART.NS": "Consumer Durables & Retail", "BLUESTARCO.NS": "Consumer Durables & Retail",
    "VOLTAS.NS": "Consumer Durables & Retail", "HAVELLS.NS": "Consumer Durables & Retail",
    "POLYCAB.NS": "Consumer Durables & Retail", "KEI.NS": "Consumer Durables & Retail",
    "SIEMENS.NS": "Consumer Durables & Retail", "DIXON.NS": "Consumer Durables & Retail",
    "THERMAX.NS": "Industrials", "CUMMINSIND.NS": "Industrials",
    "BHARTIARTL.NS": "Telecom", "TATACOMM.NS": "Telecom",
    "APOLLOHOSP.NS": "Healthcare", "BEL.NS": "Defence",
    "CONCOR.NS": "Logistics & Services", "IRCTC.NS": "Logistics & Services",
}

SPLITS = ["train", "validation", "final_oos"]


def sector_of(sym: str) -> str:
    return SECTOR.get(sym.replace("_", "."), "Other")


def _load_d1d_volume(d1d_dir: str) -> pd.DataFrame:
    """Raw daily volume (index ts) -> (symbol, date) MultiIndex frame.

    Symbol labels follow the alpha panel convention ('ADANIENT_NS'). Only the
    volume column is returned; raw frames stay untouched.
    """
    frames = []
    for p in sorted(Path(d1d_dir).glob("*.parquet")):
        df = pd.read_parquet(p, columns=["volume"]).rename_axis("date")
        df["symbol"] = p.stem
        frames.append(df.set_index(["symbol"], append=True).swaplevel("symbol", "date"))
    return pd.concat(frames)


def load_panels() -> dict[str, pd.DataFrame]:
    dev = pd.read_parquet("data/historical/alpha_panel_dev.parquet")
    ho = pd.read_parquet("data/holdout/alpha_panel_holdout.parquet")
    dev = dev.join(_load_d1d_volume("data/historical/d1d"), how="left")
    ho = ho.join(_load_d1d_volume("data/holdout/d1d"), how="left")
    return {"development": dev, "holdout": ho}


def per_date_means(sub: pd.DataFrame, col: str) -> pd.Series:
    return sub.groupby(level="date")[col].mean()


# ---------------- Phase 2: definition + correlations ----------------
def feature_correlations(panel: pd.DataFrame, split: str) -> dict:
    sub = panel[panel["split"] == split]
    feats = [c for c in panel.columns if c != "split" and c.endswith(("20", "50", "20")) is False
             and c in aa.QUALITY]  # placeholder; real list below
    feats = ["trend_sma20_gap", "trend_ema10_gap", "mom_roc20", "mom_rsi14",
             "vol_rel20", "vol_trend_10v50", "vol_price_corr20", "vol_atr_pct",
             "vol_realized20", "vol_pctile_252", "struct_breakout20",
             "struct_lowdist20", "struct_bb_z20", "struct_vwap_gap20",
             "xs_rel_str20", "xs_mom_rank20", "mkt_ret_5d", "mkt_vol_20"]
    df = sub[feats].dropna()
    c = df.corr(method="spearman").loc[FEATURE].to_dict()
    return {k: round(v, 4) for k, v in c.items()}


# ---------------- Phase 3: cross-sectional distribution ----------------
def xs_distribution(panel: pd.DataFrame, split: str) -> dict:
    sub = panel[panel["split"] == split].dropna(subset=[FEATURE])
    daily = sub.groupby(level="date")[FEATURE]
    stats_ = daily.agg(["median", "std", "min", "max", "nunique", "count"])
    out = {
        "split": split,
        "pooled": {k: round(float(v), 6) for k, v in sub[FEATURE]
                   .describe()[["mean", "std", "min", "max"]].to_dict().items()},
        "pooled_p50": round(float(sub[FEATURE].median()), 6),
        "pooled_p1": round(float(sub[FEATURE].quantile(0.01)), 6),
        "pooled_p5": round(float(sub[FEATURE].quantile(0.05)), 6),
        "pooled_p95": round(float(sub[FEATURE].quantile(0.95)), 6),
        "pooled_p99": round(float(sub[FEATURE].quantile(0.99)), 6),
        "avg_daily_median": round(float(stats_["median"].mean()), 6),
        "avg_daily_std": round(float(stats_["std"].mean()), 6),
        "avg_daily_min": round(float(stats_["min"].mean()), 6),
        "avg_daily_max": round(float(stats_["max"].mean()), 6),
        "avg_daily_unique": round(float(stats_["nunique"].mean()), 2),
        "avg_daily_count": round(float(stats_["count"].mean()), 2),
        "days_with_<20_unique": int((stats_["nunique"] < 20).sum()),
        "avg_dispersion_cv": round(float(
            (stats_["std"] / stats_["median"].replace(0, np.nan)).mean()), 6),
        "share_of_days_median_zero": round(
            float((stats_["median"].abs() < 1e-9).mean()), 4),
    }
    return out


# ---------------- Phase 4: quantile target relationship ----------------
def bucket_stats(sub: pd.DataFrame, feature: str, horizon: str) -> dict:
    lab = sub[f"fwd_ret_{horizon}"]
    mask = np.isfinite(sub[feature].to_numpy()) & np.isfinite(lab.to_numpy())
    feat = sub[feature].to_numpy()[mask]
    y = lab.to_numpy()[mask]
    if len(feat) < 200:
        return {"status": "INSUFFICIENT"}
    b = pd.qcut(pd.Series(feat), 5, labels=False, duplicates="drop")
    rows = {}
    for i in range(5):
        ys = y[b == i]
        m, md = float(ys.mean()), float(np.median(ys))
        se = float(ys.std(ddof=1) / np.sqrt(len(ys))) if len(ys) > 1 else np.nan
        rows[i] = {"n": int(len(ys)),
                   "mean_pct": round(m * 100, 4),
                   "median_pct": round(md * 100, 4),
                   "ci95_pct": [round((m - 1.96 * se) * 100, 4),
                                round((m + 1.96 * se) * 100, 4)]}
    row0, row4 = rows[0], rows[4]
    q5q1_diff = row4["mean_pct"] - row0["mean_pct"]
    rows["Q5-Q1"] = {"mean_spread_pct": round(q5q1_diff, 4),
                     "median_spread_pct": round(row4["median_pct"] - row0["median_pct"], 4),
                     "buckets": 5, "n": int(np.sum([rows[k]["n"] for k in range(5)]))}
    # monotonicity via spearman of bucket-mean order
    mus = [rows[i]["mean_pct"] for i in range(5)]
    rho, pv = stats.spearmanr(np.arange(5), mus)
    rows["monotonic"] = {"spearman_rho": round(float(rho), 4),
                         "pvalue": round(float(pv), 4)}
    rows["shape"] = "u_shaped" if (mus[0] > mus[2] and mus[4] > mus[2]) else \
                    ("monotonic_up" if rho > 0.7 else
                     "monotonic_down" if rho < -0.7 else "nonlinear")
    return rows


def quantile_relationship(panel: pd.DataFrame, split: str) -> dict:
    sub = panel[panel["split"] == split].dropna(subset=[FEATURE])
    return {"h1": bucket_stats(sub, FEATURE, "1"),
            "h3": bucket_stats(sub, FEATURE, "3")}


# ---------------- Phase 5: symbol / sector / liquidity concentration ----
def _per_symbol_ic(sub: pd.DataFrame, horizon: str) -> pd.DataFrame:
    rows = []
    for sym, g in sub.groupby(level="symbol"):
        f = g[FEATURE].to_numpy()
        lab = g[f"fwd_ret_{horizon}"].to_numpy()
        mask = np.isfinite(f) & np.isfinite(lab)
        if mask.sum() < 200:
            continue
        rho = stats.spearmanr(f[mask], lab[mask])[0]
        # per-symbol mean LS (tercile top-bottom) for attribution
        b = pd.qcut(pd.Series(f[mask]), 3, labels=False, duplicates="drop")
        y = lab[mask]
        ls = float((y[b == b.max()].mean() - y[b == b.min()].mean())) if (b == b.max()).any() and (b == b.min()).any() else np.nan
        rows.append({"symbol": sym, "ic": float(rho), "n": int(mask.sum()),
                     "ls_tercile_pct": round(ls * 100, 4)})
    return pd.DataFrame(rows)


def concentration(panel: pd.DataFrame, split: str) -> dict:
    out = {}
    for horizon in HORIZONS:
        sub = panel[panel["split"] == split].dropna(subset=[FEATURE])
        df = _per_symbol_ic(sub, horizon)
        ic_abs = df["ic"].abs()
        shares = (ic_abs / ic_abs.sum()).fillna(0.0)
        hhi = float((shares ** 2).sum()) if ic_abs.sum() > 0 else 0.0
        top5 = df.reindex(df["ic"].abs().sort_values(ascending=False).index).head(5)
        out[horizon] = {
            "n_symbols": len(df),
            "frac_ic_positive": round(float((df["ic"] > 0).mean()), 4),
            "median_ic": round(float(df["ic"].median()), 5),
            "mean_abs_ic": round(float(df["ic"].abs().mean()), 5),
            "hhi_ic_abs_share": round(float(hhi), 4),
            "top5_symbols_share_abs": round(float(
                df["ic"].abs().sort_values(ascending=False).head(5).sum() /
                df["ic"].abs().sum()), 4),
            "top5": df.reindex(df["ic"].abs().sort_values(ascending=False).index)
                    .head(5)[["symbol", "ic"]].to_dict("records"),
            "top5_ls": df.reindex(df["ls_tercile_pct"].abs().sort_values(ascending=False).index)
                       .head(5)[["symbol", "ls_tercile_pct"]].to_dict("records"),
            "sector_mean_ic": df.assign(sector=df["symbol"].map(sector_of))
                              .groupby("sector")["ic"].agg(["mean", "count"])
                              .round(4).to_dict("index"),
        }
        # liquidity tercile (in-sample mean daily USD turnover proxy)
        sub2 = sub.copy()
        sub2["dolvol_log"] = np.log((sub2["close"] * sub2["volume"]).clip(lower=1))
        dol = sub2.groupby(level="symbol")["dolvol_log"].mean()
        q3 = pd.qcut(dol.rank(method="first"), 3, labels=["low", "mid", "high"])
        byliq = []
        for bucket, group in df.groupby(df["symbol"].map(q3)):
            if group.empty:
                continue
            byliq.append({"bucket": str(bucket),
                          "frac_ic_positive": round(float((group["ic"] > 0).mean()), 4),
                          "median_ic": round(float(group["ic"].median()), 5),
                          "n": len(group)})
        out[horizon]["liquidity_bucket"] = byliq
    return out


# ---------------- Phase 6: market-neutral vs directional ----------------
def market_vs_relative(panel: pd.DataFrame, split: str) -> dict:
    sub = panel[panel["split"] == split].dropna(subset=[FEATURE, "fwd_ret_1"])
    sub = sub.copy()
    sub["dt"] = sub.index.get_level_values("date")
    g = sub.groupby("dt")
    # absolute: cross-sectional mean signal vs next-day mean return (market timing)
    sig_bar = g[FEATURE].mean()
    ret_bar = g["fwd_ret_1"].mean()
    out = {"n_dates": int(len(sig_bar))}
    if len(sig_bar) > 30:
        rho, pv = stats.spearmanr(sig_bar, ret_bar)
        out["market_timing"] = {"spearman_daily": round(float(rho), 4),
                                "pvalue": round(float(pv), 4)}
    # relative: within-date rank of signal vs within-date demeaned return
    sub["rel"] = g[FEATURE].transform(lambda x: x - x.mean())
    sub["rel_ret"] = g["fwd_ret_1"].transform(lambda x: x - x.mean())
    msk = sub.dropna(subset=["rel_ret"]).index
    r2, p2 = stats.spearmanr(sub.loc[msk, "rel"], sub.loc[msk, "rel_ret"])
    out["relative_ic_pooled"] = {"spearman": round(float(r2), 4),
                                 "pvalue": round(float(p2), 4)}
    # direct long-short from relative signal (10/10)
    ls = aa.long_short_by_date(sub, FEATURE, 1, split, 0.10)
    out["ls_decile_h1"] = {k: ls.get(k) for k in
                           ("ls_mean_pct", "ls_tstat", "long_mean_pct",
                            "short_mean_pct", "ls_positive_dates_frac")} if ls.get("status") == "OK" else ls
    out["panel"] = split
    return out


# ---------------- Phase 7: exposure residual IC ----------------
def _index_ret(panel: pd.DataFrame) -> pd.Series:
    close = panel["close"].unstack("symbol")
    ret = close.pct_change().mean(axis=1)
    return ret


def attach_exposures(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach rolling beta, size, liquidity (full per-symbol history)."""
    mkt = _index_ret(panel)
    sub = panel.copy()
    sub["mkt_d"] = sub.index.get_level_values("date").map(mkt)
    sub["ret"] = sub["close"].groupby(level="symbol").pct_change()
    sub = sub.sort_index()
    cols = {"beta": [], "size": [], "liq": []}
    for sym, g2 in sub.groupby(level="symbol"):
        r = g2["ret"]
        m = g2["mkt_d"]
        base = np.log(g2["close"].clip(lower=1e-9) * g2["volume"].clip(lower=1e-9))
        cols["beta"].append(r.rolling(252).cov(m) / m.rolling(252).var().replace(0, np.nan))
        cols["size"].append(base.rolling(252).mean())
        cols["liq"].append(np.log(g2["volume"].clip(lower=1)).rolling(20).mean())
    sub["beta"] = pd.concat(cols["beta"])
    sub["size"] = pd.concat(cols["size"])
    sub["liq"] = pd.concat(cols["liq"])
    return sub


def _symbol_betas(panel: pd.DataFrame, mkt: pd.Series, window: int = 252) -> pd.Series:
    ret = panel["close"].groupby(level="symbol").pct_change()
    df = panel[["close"]].copy()
    df["ret"] = ret
    df["mkt"] = df.index.get_level_values("date").map(mkt)
    out = {}
    for sym, g in df.groupby(level="symbol"):
        g = g.dropna(subset=["ret", "mkt"])
        if len(g) < window:
            out[sym] = np.nan
            continue
        cov = g["ret"].rolling(window).cov(g["mkt"])
        var = g["mkt"].rolling(window).var()
        out[sym] = (cov / var.replace(0, np.nan)).iloc[-1]
    return df.groupby(level="symbol").apply(lambda g: g.index.get_level_values(0)[0]).map(out) if False else None


def residual_ic(panel: pd.DataFrame, split: str, horizon: str) -> dict:
    """Exposure-corrected IC using full per-symbol history for lookbacks.

    Exposures (rolling beta, size, liquidity) are computed on the FULL panel so
    the ~252-day lookbacks are not truncated at split boundaries; the split is
    applied only afterwards. Base IC is reported both on the full split rows
    (base_ic_panel) and on the exposure-complete subset (base_ic_tt) so any
    selection effect of requiring exposures is visible.
    """
    mkt = _index_ret(panel)
    sub = panel.copy()
    sub["mkt_d"] = sub.index.get_level_values("date").map(mkt)
    sub = attach_exposures(panel)
    sub["vol"] = sub["vol_realized20"]
    sub["mom"] = sub["mom_roc20"]
    sub["trend"] = sub["trend_sma20_gap"]

    ss = sub[sub["split"] == split]
    allm = ss.dropna(subset=[FEATURE, f"fwd_ret_{horizon}"])
    report = {"base_ic": None, "base_ic_panel": None, "residual_ic": None,
              "corr_with_exposure": {}}
    if len(allm) >= 200:
        report["base_ic_panel"] = round(float(stats.spearmanr(
            allm[FEATURE], allm[f"fwd_ret_{horizon}"])[0]), 5)
    tt = ss.dropna(subset=[FEATURE, f"fwd_ret_{horizon}", "beta", "size", "liq",
                           "vol", "mom", "trend"]).copy()
    report["n"] = len(tt)
    report["date_coverage"] = (str(tt.index.get_level_values("date").min())[:10],
                               str(tt.index.get_level_values("date").max())[:10]) \
        if len(tt) else None
    if len(tt) < 500:
        return report
    tt["fr"] = stats.rankdata(tt[FEATURE])
    tt["fy"] = stats.rankdata(tt[f"fwd_ret_{horizon}"])
    report["base_ic"] = round(float(stats.spearmanr(tt[FEATURE],
                                                    tt[f"fwd_ret_{horizon}"])[0]), 5)
    exps = ["beta", "vol", "mom", "trend", "size", "liq"]
    for e in exps:
        report["corr_with_exposure"][e] = round(float(stats.spearmanr(tt[FEATURE],
                                                                      tt[e])[0]), 4)
    # residualize: within-date cross-sectional rank regression on exposures
    resid = {}
    for dt, gg in tt.groupby(level="date"):
        if len(gg) < 15:
            continue
        X = gg[exps].astype(float).rank().copy()
        X = (X - X.mean()) / X.std().replace(0, np.nan)
        X["const"] = 1.0
        y = gg["fr"].astype(float)
        coef, *_ = np.linalg.lstsq(X.to_numpy(), y.to_numpy(), rcond=None)
        resid[dt] = pd.Series(y.to_numpy() - X.to_numpy() @ coef, index=gg.index)
    if resid:
        r = pd.concat(resid.values())
        r = r.reindex(tt.index)
        rr = stats.spearmanr(r.dropna().to_numpy(), tt["fy"].dropna().to_numpy())
        report["residual_ic"] = round(float(rr[0]), 5)
        report["residual_pvalue"] = round(float(rr[1]), 4)
    report["panel_split"] = f"{split}"
    return report


# ---------------- Phase 11: regime analysis ----------------
def regime_analysis(panel: pd.DataFrame, split: str, horizon: str) -> list[dict]:
    return aa.regime_ic(panel, FEATURE, int(horizon), split)


# ---------------- Phase 12: temporal stability ----------------
def rolling_ic_by_block(panel: pd.DataFrame, start, end, horizon: str,
                        block: int = 63) -> dict:
    sub = panel[(panel.index.get_level_values("date") >= start) &
                (panel.index.get_level_values("date") < end)].copy()
    sub = sub.dropna(subset=[FEATURE, f"fwd_ret_{horizon}"])
    dates = pd.Index(np.sort(np.unique(sub.index.get_level_values("date"))))
    blocks = [dates[i:i + block] for i in range(0, len(dates), block)]
    rows = []
    for b in blocks:
        if len(b) < 20:
            continue
        bb = sub[sub.index.get_level_values("date").isin(b)]
        if len(bb) < 200:
            continue
        ic = float(stats.spearmanr(bb[FEATURE], bb[f"fwd_ret_{horizon}"])[0])
        rows.append({"window": str(b[0])[:7], "n": int(len(bb)),
                     "ic": round(ic, 4)})
    ics = np.array([r["ic"] for r in rows])
    if len(ics) == 0:
        return {"status": "EMPTY"}
    return {"n_windows": len(ics), "frac_positive": round(float((ics > 0).mean()), 4),
            "median_ic": round(float(np.median(ics)), 4),
            "mean_ic": round(float(ics.mean()), 4),
            "worst": {"ic": round(float(ics.min()), 4),
                      "window": rows[int(ics.argmin())]["window"]},
            "best": {"ic": round(float(ics.max()), 4),
                     "window": rows[int(ics.argmax())]["window"]},
            "q10": round(float(np.quantile(ics, 0.10)), 4),
            "q90": round(float(np.quantile(ics, 0.90)), 4),
            "windows": rows}


# ---------------- Phase 13: outlier influence ----------------
def outlier_robustness(panel: pd.DataFrame, split: str, horizon: str) -> dict:
    sub = panel[panel["split"] == split].dropna(subset=[FEATURE, f"fwd_ret_{horizon}"])
    f = sub[FEATURE].to_numpy()
    y = sub[f"fwd_ret_{horizon}"].to_numpy()
    def _ic(a, b):
        m = np.isfinite(a) & np.isfinite(b)
        return float(stats.spearmanr(a[m], b[m])[0]) if m.sum() >= 200 else np.nan
    base = _ic(f, y)
    # pre-defined robustness: winsorize labels at 1/99, then drop top-0.5% abs labels
    lo, hi = np.quantile(y, [0.01, 0.99])
    yw = np.clip(y, lo, hi)
    thr = np.quantile(np.abs(y), 0.995)
    keep = np.abs(y) <= thr
    return {"split": split, "horizon": horizon, "n": len(f),
            "base_ic": round(base, 5),
            "winsor1_99_ic": round(_ic(f, yw), 5),
            "drop_extreme0p5pct_ic": round(_ic(f[keep], y[keep]), 5),
            "n_dropped": int((~keep).sum()),
            "n_winsorized": int((y != yw).sum())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/vt_signal_diagnostics.json")
    args = ap.parse_args()

    panels = load_panels()
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "feature": FEATURE, "definition": "SMA(volume,10)/SMA(volume,50)-1",
           "note": "diagnostics only; no monetization selection performed",
           "panels": {k: {"rows": int(v.shape[0]),
                          "symbols": int(v.index.get_level_values("symbol").nunique()),
                          "splits": v["split"].value_counts().to_dict()}
                      for k, v in panels.items()}}

    for pname, panel in panels.items():
        po = {}
        for split in SPLITS:
            if split not in panel["split"].values:
                continue
            po[split] = {
                "correlations": feature_correlations(panel, split),
                "distribution": xs_distribution(panel, split),
                "quantile_relationship": quantile_relationship(panel, split),
                "concentration": concentration(panel, split),
                "market_vs_relative": market_vs_relative(panel, split),
                "residual_ic": {h: residual_ic(panel, split, h) for h in HORIZONS},
                "regime_ic": {h: regime_analysis(panel, split, h) for h in HORIZONS},
                "outlier_robustness": {h: outlier_robustness(panel, split, h)
                                       for h in HORIZONS},
            }
        # temporal stability on the OOS-relevant period and full train range
        po["temporal_stability"] = {
            "train_2014_2023": {h: rolling_ic_by_block(panel, "2014-01-01",
                                                       "2023-01-01", h) for h in HORIZONS},
            "oos_2023_2026": {h: rolling_ic_by_block(panel, "2023-01-01",
                                                     "2026-09-05", h) for h in HORIZONS},
        }
        out[pname] = po
        print(f"[{pname}] done: {len(po)-1} splits + temporal", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()