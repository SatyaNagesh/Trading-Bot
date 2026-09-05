"""Alpha discovery - statistical analysis core.

Measurement strategy (no strategy backtesting here):

* **IC** = Spearman rank correlation between a causal feature and a forward
  return label. Rank correlation is scale-invariant and robust to outliers.
* **Significance** uses a Fisher z transform with an **effective sample size**
  that down-weights within-symbol autocorrelation of the feature-label product
  (per-symbol n_eff = n / (1 + 2*sum_lags autocorr); pooled across symbols).
  This is a screening tool; surviving candidates get time-block bootstrap CIs.
* **Multiple testing**: BH-FDR across the hypothesis grid on the selection
  period (VALIDATION). FINAL-OOS is a holdout scored once.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

SPLIT_ORDER = ["train", "validation", "final_oos"]

MIN_OBS_PER_IC = 200
MAX_ACF_LAG = 20
BH_Q = 0.10


def _rank(a: np.ndarray) -> np.ndarray:
    return stats.rankdata(a, method="average")


def _per_symbol_eff_n(product_series, symbol_ids, n_max=MAX_ACF_LAG) -> float:
    """Sum over symbols of n_i / (1 + 2*sum_{lag<=n_max} acf_lag)."""
    total = 0.0
    df = pd.DataFrame({"z": product_series, "sym": symbol_ids})
    for _, g in df.dropna().groupby("sym"):
        n = len(g)
        if n < 6:
            continue
        z = g["z"].to_numpy(dtype=float)
        z = z - z.mean()
        var = float(z @ z) / n
        if var <= 0:
            total += n
            continue
        cross = np.correlate(z, z, mode="full")[n:n + n_max]
        acf = cross / (np.arange(n, n + len(cross)).astype(float) * var)
        acf_sum = float(np.clip(acf.sum(), -0.49, 1.0))
        total += n / (1.0 + 2.0 * acf_sum)
    return total


def ic_stats(feat: np.ndarray, lab: np.ndarray, symbol_ids) -> dict:
    """Full IC report for one feature-label pair on a homogenous split panel."""
    feat = np.asarray(feat, dtype=float)
    lab = np.asarray(lab, dtype=float)
    mask = np.isfinite(feat) & np.isfinite(lab)
    feat, lab = feat[mask], lab[mask]
    n = len(feat)
    if n < MIN_OBS_PER_IC:
        return {"n": int(n), "status": "INSUFFICIENT", "pearson_r": None,
                "spearman_ic": None, "stderr": None, "pvalue": None,
                "ci95_lo": None, "ci95_hi": None, "hit_rate": None}
    rf, rl = _rank(feat), _rank(lab)
    pearson = float(np.corrcoef(feat, lab)[0, 1])
    rho = float(np.corrcoef(rf, rl)[0, 1])
    product = (rf - rf.mean()) * (rl - rl.mean())
    n_eff = _per_symbol_eff_n(product, np.asarray(symbol_ids)[mask])
    n_eff = float(np.clip(n_eff, 3.0, n))
    rho_c = float(np.clip(rho, -0.999999, 0.999999))
    z = np.arctanh(rho_c)
    se = 1.0 / np.sqrt(n_eff - 3.0) if n_eff > 3 else np.inf
    pvalue = float(2.0 * (1.0 - stats.norm.cdf(abs(z) / se))) if np.isfinite(se) else 0.0
    lo, hi = np.tanh(z - 1.959964 * se), np.tanh(z + 1.959964 * se)
    hit = float((lab > 0).mean())
    return {"n": int(n), "status": "OK",
            "n_eff": round(n_eff, 1),
            "pearson_r": round(pearson, 5),
            "spearman_ic": round(rho, 5),
            "stderr": (round(se, 5) if np.isfinite(se) else None),
            "pvalue": pvalue,
            "ci95_lo": round(float(lo), 5),
            "ci95_hi": round(float(hi), 5),
            "hit_rate": round(hit, 5),
            "sign": (1 if rho > 0 else -1)}


def bh_fdr(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted q-values (returns None-len 0 list if empty)."""
    p = np.asarray([x for x in pvalues if x is not None], dtype=float)
    if p.size == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    m = len(ranked)
    q = ranked * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.zeros(m)
    out[order] = q
    return [float(np.clip(v, 0.0, 1.0)) for v in out]


def quantile_profile(feat: np.ndarray, lab: np.ndarray, q: int = 5) -> dict:
    """Bucket (quantile) mean forward returns + monotonicity diagnostics."""
    feat = np.asarray(feat, dtype=float)
    lab = np.asarray(lab, dtype=float)
    mask = np.isfinite(feat) & np.isfinite(lab)
    feat, lab = feat[mask], lab[mask]
    n = len(feat)
    if n < MIN_OBS_PER_IC:
        return {"status": "INSUFFICIENT", "n": int(n)}
    try:
        buckets = pd.qcut(pd.Series(feat), q, labels=False, duplicates="drop")
    except ValueError:
        return {"status": "INSUFFICIENT", "n": int(n)}
    df = pd.DataFrame({"b": buckets, "y": lab})
    g = df.groupby("b")["y"]
    means = g.mean()
    counts = g.count()
    n_buckets = len(means)
    monotonic = None
    if n_buckets >= 3:
        rho_m, _ = stats.spearmanr(np.arange(n_buckets), means.values)
        monotonic = float(rho_m)
    single_dom = float(means.abs().max() / max(means.abs().mean(), 1e-12))
    return {
        "status": "OK", "n": int(n), "q": int(q), "n_buckets": int(n_buckets),
        "bucket_means_pct": {int(k): round(float(v) * 100, 4) for k, v in means.items()},
        "bucket_counts": {int(k): int(v) for k, v in counts.items()},
        "q1_mean_pct": round(float(means.iloc[0]) * 100, 4),
        "q_top_mean_pct": round(float(means.iloc[-1]) * 100, 4),
        "top_bottom_spread_pct": round(float((means.iloc[-1] - means.iloc[0])) * 100, 4),
        "monotonic_rho": monotonic,
        "single_bucket_dominance": round(float(single_dom), 3),
    }


def regime_ic(panel: pd.DataFrame, feature: str, horizon: int,
              split: str) -> list[dict]:
    """IC per regime_bucket within a split."""
    sub = panel[panel["split"] == split].dropna(subset=["regime_bucket", feature, f"fwd_ret_{horizon}"])
    rows = []
    for bucket, g in sub.groupby("regime_bucket"):
        if len(g) < MIN_OBS_PER_IC:
            continue
        st = ic_stats(g[feature].to_numpy(), g[f"fwd_ret_{horizon}"].to_numpy(),
                      g.index.get_level_values("symbol").to_numpy())
        if st["status"] == "OK":
            rows.append({"regime_bucket": bucket, "n": st["n"],
                         "ic": st["spearman_ic"], "hit_rate": st["hit_rate"]})
    rows.sort(key=lambda r: -abs(r["ic"]))
    return rows


def long_short_by_date(panel: pd.DataFrame, feature: str, horizon: int,
                       split: str, coverage: float) -> dict:
    """Cross-sectional diagnostic: per-date ranked-group forward returns (vectorized)."""
    sub = panel[panel["split"] == split].dropna(subset=[feature, f"fwd_ret_{horizon}"])
    if len(sub) < 200:
        return {"status": "EMPTY"}
    sub = sub.copy()
    sub["dt"] = sub.index.get_level_values("date")
    sub["rank"] = sub.groupby("dt")[feature].rank(method="average", pct=True)
    sub["in_long"] = sub["rank"] >= 1.0 - coverage
    sub["in_short"] = sub["rank"] <= coverage
    long_m = sub.loc[sub["in_long"]].groupby("dt")[f"fwd_ret_{horizon}"].mean()
    short_m = sub.loc[sub["in_short"]].groupby("dt")[f"fwd_ret_{horizon}"].mean()
    mkt_m = sub.groupby("dt")[f"fwd_ret_{horizon}"].mean()
    df = pd.DataFrame({"long": long_m, "short": short_m, "mkt": mkt_m})
    df["ls"] = df["long"] - df["short"]
    df = df.dropna(subset=["ls"])
    if len(df) < 30:
        return {"status": "INSUFFICIENT", "dates": int(len(df))}
    ls = df["ls"].to_numpy()
    n = len(ls)
    t_ls = float(ls.mean() / (ls.std(ddof=1) / np.sqrt(n))) if ls.std(ddof=1) > 0 else 0.0
    rng = np.random.default_rng(7)
    boots = np.array([rng.choice(ls, size=n, replace=True).mean() for _ in range(500)])
    long_excess = df["long"] - df["mkt"].fillna(df["long"].mean())
    return {
        "status": "OK", "split": split, "coverage": coverage, "dates": n,
        "long_mean_pct": round(float(df["long"].mean()) * 100, 4),
        "short_mean_pct": round(float(df["short"].mean()) * 100, 4),
        "ls_mean_pct": round(float(ls.mean()) * 100, 4),
        "ls_tstat": round(t_ls, 3),
        "ls_ci95_pct": [round(float(np.quantile(boots, 0.025)) * 100, 4),
                        round(float(np.quantile(boots, 0.975)) * 100, 4)],
        "ls_positive_dates_frac": round(float((ls > 0).mean()), 4),
        "long_excess_vs_mkt_pct": round(float(long_excess.mean()) * 100, 4),
        "long_vs_short_monotonic": bool(df["long"].mean() > df["short"].mean()),
    }


QUALITY = ["spearman_ic", "ci95_lo", "ci95_hi", "pvalue", "n_eff", "hit_rate", "pearson_r"]


def block_bootstrap_ic(feat: np.ndarray, lab: np.ndarray, dates,
                       symbol_ids, n_sims: int = 250, block: int = 63,
                       seed: int = 7) -> dict:
    """Time-block bootstrap of the pooled Spearman IC (autocorrelation-robust CI)."""
    feat = np.asarray(feat, dtype=float)
    lab = np.asarray(lab, dtype=float)
    mask = np.isfinite(feat) & np.isfinite(lab)
    feat, lab = feat[mask], lab[mask]
    dates = np.asarray(dates)[mask]
    n = len(feat)
    if n < MIN_OBS_PER_IC:
        return {"status": "INSUFFICIENT"}
    date_u = pd.Index(np.unique(dates)).sort_values()
    idx_of_date = date_u.searchsorted(dates)
    n_dates = len(date_u)
    n_blocks = int(np.ceil(n_dates / block))
    obs_rho = float(stats.spearmanr(feat, lab)[0])
    rng = np.random.default_rng(seed)
    sims = np.empty(n_sims)
    for s in range(n_sims):
        starts = rng.integers(0, n_dates, size=n_blocks)
        keep_dates = []
        for st_ in starts:
            keep_dates.extend(date_u[st_:st_ + block])
        keep_set = set(keep_dates)
        keep = np.array([d in keep_set for d in dates])
        if keep.sum() < 100:
            sims[s] = np.nan
            continue
        sims[s] = float(stats.spearmanr(feat[keep], lab[keep])[0])
    sims = sims[np.isfinite(sims)]
    return {"status": "OK", "n": n, "obs_ic": round(float(obs_rho), 5),
            "ci95_lo": round(float(np.quantile(sims, 0.025)), 5),
            "ci95_hi": round(float(np.quantile(sims, 0.975)), 5),
            "n_sims": int(len(sims)),
            "p_gt_0": round(float((sims > 0).mean()), 4),
            "p_lt_0": round(float((sims < 0).mean()), 4)}


def randomized_null(feat: np.ndarray, lab: np.ndarray, symbol_ids,
                    n_shuffles: int = 200, seed: int = 7) -> dict:
    """Null distribution of IC under within-symbol permutation of the feature."""
    feat = np.asarray(feat, dtype=float)
    lab = np.asarray(lab, dtype=float)
    mask = np.isfinite(feat) & np.isfinite(lab)
    feat, lab = feat[mask], lab[mask]
    sym = np.asarray(symbol_ids)[mask]
    n = len(feat)
    if n < MIN_OBS_PER_IC:
        return {"status": "INSUFFICIENT"}
    obs = float(stats.spearmanr(feat, lab)[0])
    rng = np.random.default_rng(seed)
    sims = np.empty(n_shuffles)
    for s in range(n_shuffles):
        shuffled = feat.copy()
        for sym_ in np.unique(sym):
            idx = sym == sym_
            sub = shuffled[idx]
            shuffled[idx] = rng.permutation(sub)
        sims[s] = float(stats.spearmanr(shuffled, lab)[0])
    p_two = float((np.abs(sims) >= abs(obs)).mean())
    return {"status": "OK", "n": n, "obs_ic": round(obs, 5),
            "null_mean": round(float(sims.mean()), 5),
            "null_std": round(float(sims.std()), 5),
            "p_two_sided": round(p_two, 4),
            "n_shuffles": n_shuffles}


def partial_ic(a: np.ndarray, b: np.ndarray, y: np.ndarray) -> float:
    """IC of feature b on the residual of y after removing linear rank(A)."""
    mask = np.isfinite(a) & np.isfinite(b) & np.isfinite(y)
    a, b, y = a[mask], b[mask], y[mask]
    if len(a) < MIN_OBS_PER_IC:
        return None
    ra = _rank(a)
    ry = _rank(y)
    X = np.column_stack([np.ones_like(ra), (ra - ra.mean()) / ra.std()])
    coef, *_ = np.linalg.lstsq(X, ry - ry.mean(), rcond=None)
    resid = ry - X @ coef
    return float(stats.spearmanr(b, resid)[0])


def composite_z_cols(panel: pd.DataFrame, features: list[str], split: str) -> pd.DataFrame:
    """Per-symbol standardized z of a feature set, then cross-symbol mean."""
    zs = []
    for f in features:
        g = panel[panel["split"] == split]
        fmean = g.groupby(level="symbol")[f].transform("mean")
        fstd = g.groupby(level="symbol")[f].transform("std")
        zs.append((g[f] - fmean) / fstd.replace(0, np.nan))
    return pd.concat(zs, axis=1).mean(axis=1)


def ls_daily_rows(sub: pd.DataFrame, feature: str, horizon: int,
                  coverage: float = 0.10, cost_per_side: float = 0.0015):
    """Per-rebalance long-short gross/net/turnover rows for a credit-score panel slice.

    `sub` must have columns [feature, fwd_ret_{horizon}] and a (symbol, date) MultiIndex.
    Rebalance happens every `horizon` trading days (long-top / short-bottom ranked groups).
    """
    sub = sub.copy()
    sub["dt"] = sub.index.get_level_values("date")
    dates = pd.Index(np.unique(sub["dt"])).sort_values()
    grid = dates[::horizon]
    last_accepted = None
    rows = []
    prev_weights = None
    for t in grid:
        day_rows = sub[sub["dt"] == t]
        if len(day_rows) < 20:
            continue
        day_rows = day_rows.sort_values(feature)
        n = len(day_rows)
        k = max(1, int(round(n * coverage)))
        short_rows = day_rows.iloc[:k]
        long_rows = day_rows.iloc[-k:]
        w = pd.Series(0.0, index=day_rows.index)
        w.loc[long_rows.index] = 1.0 / k
        w.loc[short_rows.index] = -1.0 / k
        truth = day_rows[f"fwd_ret_{horizon}"].to_numpy()
        gross = float((w.to_numpy() * truth).sum())
        turnover = float(np.abs(w - prev_weights).sum()) if prev_weights is not None else 2.0
        cost = turnover * cost_per_side
        rows.append({"date": str(t), "gross": gross, "net": gross - cost, "turnover": turnover})
        prev_weights = w
        last_accepted = t
    return rows, last_accepted, grid


def cost_aware_ls(panel: pd.DataFrame, feature: str, horizon: int,
                  split: str, coverage: float = 0.10,
                  cost_per_side: float = 0.0015) -> dict:
    """Long-short decile portfolio held `horizon` days, gross vs net of costs."""
    sub = panel[panel["split"] == split].dropna(subset=[feature, f"fwd_ret_{horizon}"])
    if len(sub) < 200:
        return {"status": "INSUFFICIENT", "n": int(len(sub))}
    rows, last_accepted, grid = ls_daily_rows(sub, feature, horizon, coverage, cost_per_side)
    if len(rows) < 5:
        return {"status": "INSUFFICIENT", "rebalances": len(rows)}
    gross_cum = float(np.prod([1 + r["gross"] for r in rows]) - 1) * 100
    net_cum = float(np.prod([1 + r["net"] for r in rows]) - 1) * 100
    # equal-weight index buy&hold over the same span as a market benchmark
    idx_ret = sub.groupby("date")[f"fwd_ret_{horizon}"].mean()
    bench_span = idx_ret.loc[:last_accepted]
    mkt_bh = float(np.prod([1 + r for r in
                            bench_span.groupby(pd.cut(bench_span.index, len(grid))).mean()
                            if np.isfinite(r)]) - 1) * 100
    return {
        "status": "OK", "horizon_days": horizon, "rebalances": len(rows),
        "gross_cum_pct": round(gross_cum, 4),
        "net_cum_pct": round(net_cum, 4),
        "cost_drag_pct": round(gross_cum - net_cum, 4),
        "avg_turnover": round(float(np.mean([r["turnover"] for r in rows])), 4),
        "gross_positive": bool(gross_cum > 0),
        "net_positive": bool(net_cum > 0),
        "cost_fragile": bool(gross_cum > 0 and net_cum <= 0),
        "market_bh_pct": round(mkt_bh, 4),
    }