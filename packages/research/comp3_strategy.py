"""COMP3 strategy research driver - Phases 2-11 (development study).

Runs the pre-registered Phase-2..11 analysis for the frozen COMP3 composite
(spec: reports/COMP3_STRATEGY_SPEC_2026-09.md). Development corpus only.

  F02 signal interpretation      -> data/comp3/interpretation.json
  F03 component attribution      -> data/comp3/component_contrib.json
  F04 strategy backtest          -> data/comp3/strategy_backtest.json
  F05 statistical uncertainty    -> data/comp3/stat_uncertainty.json
  F06 walk-forward stability     -> data/comp3/walk_forward.json
  F07 bias & robustness          -> data/comp3/bias_analysis.json

The strategy rule evaluated here (1-day hold, daily rebalance, weights set at
the close of t, realised 1-day forward returns from the frozen panel) matches
the trading rule frozen for holdout-4: inputs through close(t), enter at
open[t+1], exit at close[t+1] => session P&L = close[t+1]/open[t+1] - 1.
Dev panels carry only close-to-close fwd returns, so dev game P&L uses
fwd_ret_1 (close-to-close) and holdout-4 uses true open-to-close session
returns from raw bars; both are 1-day holds under the frozen gate.

Usage:
  python -m packages.research.comp3_strategy [--stages F02,F03,...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from packages.research import alpha_analysis as aa
from packages.research import composite_alpha as ca
from packages.research.metrics import _max_drawdown, _sharpe, _sortino
from packages.research.vt_signal import sector_of

OUT_DIR = Path("data/comp3")
DEV_PATH = ca.DATAP

COSTS_BPS = (25, 50, 100)
SEED = 7
C3 = "C3_rev_abn_mkt1"
G1 = "G1_breadth_rise"
G6 = "G6_breadth_mom5"
G4 = "G4_xs_ret_disp"
SCORE = "COMP3_REVERSAL_BREADTH_DISP"

# pre-registered walk-forward windows (contiguous, non-overlapping, dev timeline)
WF_WINDOWS = [
    ("W1", "2014-01-01", "2017-12-31"),
    ("W2", "2018-01-01", "2020-12-31"),
    ("W3", "2021-01-01", "2023-12-31"),
    ("W4", "2024-01-01", "2026-09-04"),
]


def load() -> pd.DataFrame:
    frz = json.loads(ca.FRZ_PATH.read_text())
    assert frz.get("version") == 2
    dev = pd.read_parquet(DEV_PATH)
    dev = dev[dev["split"] != ""].copy()
    cols = ca.composite_columns(dev, frz)
    for name, (score, _lbl) in cols.items():
        dev[name] = score
    return frz, dev


def _pooled_ic(panel, score, label="fwd_ret_1", min_rows=aa.MIN_OBS_PER_IC):
    keep = panel.dropna(subset=[score, label])
    if len(keep) < min_rows or keep[score].nunique() < 5:
        return {"status": "INSUFFICIENT", "n": int(len(keep))}
    st = aa.ic_stats(keep[score].to_numpy(float), keep[label].to_numpy(float),
                     keep.index.get_level_values("symbol").to_numpy())
    return {k: st[k] for k in ("n", "n_eff", "spearman_ic", "pvalue", "ci95_lo", "ci95_hi", "sign")}


def _construction_rows(panel, score, coverage, voladj=False, cost_bp=25):
    """Daily-rebalanced long/short rows over ACTIVE dates for one construction."""
    sub = panel.dropna(subset=[score, "fwd_ret_1"]).copy()
    sub["dt"] = sub.index.get_level_values("date")
    dates = pd.Index(np.unique(sub["dt"])).sort_values()
    rows, prev_w = [], None
    for t in dates:
        day = sub[sub["dt"] == t]
        if len(day) < 20:
            continue
        k = max(1, int(round(len(day) * coverage)))
        day = day.sort_values(score)
        longs = day.iloc[-k:]
        shorts = day.iloc[:k]
        w = pd.Series(0.0, index=day.index)
        w.loc[longs.index] = 1.0 / k
        w.loc[shorts.index] = -1.0 / k
        if voladj:
            vol = day["vol_realized20"].replace(0, np.nan)
            raw = (w.abs() / vol).where(w.abs() > 0)
            if raw.isna().all() or raw.sum() <= 0 or not np.isfinite(raw).all():
                continue  # degenerate date -> dropped (vol-adjusted construction)
            raw = raw.where(np.isfinite(raw))
            w = w * (raw / raw.sum())
        truth = day["fwd_ret_1"].to_numpy()
        gross = float((w.to_numpy() * truth).sum())
        turnover = float(np.abs(w - prev_w).sum()) if prev_w is not None else 2.0
        rows.append({"date": str(t)[:10], "n_positions": int((w != 0).sum()),
                     "gross": gross, "net": gross - turnover * cost_bp / 1e4,
                     "turnover": turnover})
        prev_w = w
    return rows


def _backtest(panel, score, coverage, voladj=False):
    out = {"constructions": []}
    for cost_bp in COSTS_BPS:
        rows = _construction_rows(panel, score, coverage, voladj, cost_bp)
        if len(rows) < 5:
            out["constructions"].append({"cost_bps": cost_bp, "status": "INSUFFICIENT",
                                         "active_days": len(rows)})
            continue
        net = np.array([r["net"] for r in rows])
        equity = pd.Series(np.cumprod(1 + net))
        wins, losses = net[net > 0], net[net <= 0]
        frac_w = float((net > 0).mean())
        expiry_bps = float(net.mean() * 1e4)
        pf = (float(net[net > 0].sum()) / abs(float(net[net <= 0].sum()))
              if net[net <= 0].sum() != 0 else float("inf"))
        mdd_t = _max_drawdown(equity)
        out["constructions"].append({
            "cost_bps": cost_bp, "status": "OK",
            "active_days": len(rows),
            "avg_positions": float(np.mean([r["n_positions"] for r in rows if r["n_positions"]])),
            "avg_turnover": float(np.mean([r["turnover"] for r in rows])),
            "gross_cum_pct": round(float(np.prod(1 + np.array([r["gross"] for r in rows])) - 1) * 100, 4),
            "net_cum_pct": round(float(np.prod(1 + net) - 1) * 100, 4),
            "avg_net_bps": round(expiry_bps, 4),
            "median_net_bps": round(float(np.median(net) * 1e4), 4),
            "profit_factor": round(float(pf) if np.isfinite(pf) else np.inf, 4),
            "win_rate": round(frac_w, 4),
            "expectancy_bps": round(expiry_bps, 4),
            "max_drawdown_pct": round(mdd_t * 100, 4),
            "sharpe": round(_sharpe(net, 1), 4),
            "sortino": round(_sortino(net, 1), 4),
            "worst_day_bps": round(float(net.min() * 1e4), 4),
            "best_day_bps": round(float(net.max() * 1e4), 4),
            "n_wins": int(wins.size), "n_losses": int(losses.size),
        })
    return out


# ---------------------------------------------------------------------------
# F02 interpretation
# ---------------------------------------------------------------------------
def f02(dev, frz, score=SCORE, c3=C3):
    active = dev[score].notna()
    dates = dev.index.get_level_values("date")
    active_dates = pd.Index(np.unique(dates[active])).sort_values()
    fwd_mean_act = float(dev.loc[active, "fwd_ret_1"].mean())
    fwd_mean_inact = float(dev.loc[~active, "fwd_ret_1"].mean())
    ic_act = _pooled_ic(dev, score)
    ic_gate = dev.loc[active, [c3, "fwd_ret_1"]].dropna()
    c3_ic = {"spearman_ic": None, "pvalue": None, "n": 0}
    if len(ic_gate) >= aa.MIN_OBS_PER_IC:
        st = aa.ic_stats(ic_gate[c3].to_numpy(float), ic_gate["fwd_ret_1"].to_numpy(float),
                         ic_gate.index.get_level_values("symbol").to_numpy())
        c3_ic = {k: st[k] for k in ("spearman_ic", "pvalue", "n")}
    return {
        "signal": score,
        "gate": frz["composites"][score if False else "COMP3_REVERSAL_BREADTH_DISP"]["condition"],
        "active_rows": int(active.sum()), "total_rows": int(len(dev)),
        "active_dates": int(len(active_dates)),
        "date_coverage": round(float(active_dates.size / np.unique(dates).size), 4),
        "mean_fwd_active_pct": round(fwd_mean_act * 100, 4),
        "mean_fwd_inactive_pct": round(fwd_mean_inact * 100, 4),
        "pooled_ic_active": ic_act,
        "c3_ic_within_active": c3_ic,
    }


# ---------------------------------------------------------------------------
# F03 component attribution
# ---------------------------------------------------------------------------
def f03(dev):
    cols = [SCORE, "COMP1_REVERSAL_BREADTH", "C3_rev_abn_mkt1", "C0_BASELINE"]
    out = {"pooled_ic_h1": {}, "bands_pos_frac": {}, "quantiles": {}, "cost_robustness": {}}
    for c in cols:
        out["pooled_ic_h1"][c] = _pooled_ic(dev, c)
        keep = dev.dropna(subset=[c, "fwd_ret_1"])
        if len(keep) >= aa.MIN_OBS_PER_IC and keep[c].nunique() >= 5:
            out["quantiles"][c] = aa.quantile_profile(keep[c].to_numpy(float),
                                                      keep["fwd_ret_1"].to_numpy(float), 5)
            tmp = dev.copy(); tmp["c"] = dev[c]
            out["bands_pos_frac"][c] = ca.temporal(tmp, "c")["frac_ic_gt0"]
    for bp in COSTS_BPS:
        out["cost_robustness"][f"{bp}bp"] = aa.cost_aware_ls(
            dev, SCORE, 1, "train", 0.10, bp / 1e4)
    return out


# ---------------------------------------------------------------------------
# F04 strategy backtest
# ---------------------------------------------------------------------------
def f04(dev):
    out = {"score": SCORE, "constructions": {}}
    out["constructions"]["decile_eq"] = _backtest(dev, SCORE, 0.10, voladj=False)
    out["constructions"]["quintile_eq"] = _backtest(dev, SCORE, 0.20, voladj=False)
    out["constructions"]["decile_voladj"] = _backtest(dev, SCORE, 0.10, voladj=True)
    return out


# ---------------------------------------------------------------------------
# F05 statistical uncertainty (primary construction decile_eq @25bps)
# ---------------------------------------------------------------------------
def f05(dev, n_sims=5000):
    rows = _construction_rows(dev, SCORE, 0.10, voladj=False, cost_bp=25)
    net = np.array([r["net"] for r in rows])
    n = len(net)
    rho1 = float(pd.Series(net).autocorr(1)) if n > 3 else None
    n_eff = int(n * (1 - rho1) / (1 + rho1)) if rho1 is not None else n
    rng = np.random.default_rng(SEED)
    block = max(2, int(round(abs(rho1) * n))) if rho1 is not None else 1
    boot = np.array([
        float(np.concatenate([rng.choice(net, size=block) for _ in range(int(np.ceil(n / block)))])[:n].mean())
        for _ in range(n_sims)])
    lo, hi = sorted(np.percentile(boot, [2.5, 97.5]).tolist())
    return {"n_days": n, "autocorr_lag1": rho1, "block_size": block, "n_eff": n_eff,
            "sims": n_sims, "ci95_expectancy_bps": [round(lo * 1e4, 4), round(hi * 1e4, 4)],
            "bootstrap_mean_bps": round(float(boot.mean() * 1e4), 4)}


# ---------------------------------------------------------------------------
# F06 walk-forward (frozen contiguous windows)
# ---------------------------------------------------------------------------
def f06(dev):
    per = {}
    for name, s, e in WF_WINDOWS:
        dt = dev.index.get_level_values("date")
        w = dev[(dt >= pd.Timestamp(s, tz=dt.tz)) & (dt <= pd.Timestamp(e, tz=dt.tz))]
        r = _backtest(w, SCORE, 0.10, voladj=False)
        row = r["constructions"][0] if r["constructions"] else {"status": "INSUFFICIENT"}
        per[name] = {"window": [s, e], "active_days": row.get("active_days"),
                     "net_cum_pct": row.get("net_cum_pct"), "sharpe": row.get("sharpe")}
    nets = [v["net_cum_pct"] for v in per.values() if isinstance(v.get("net_cum_pct"), (int, float))]
    return {"windows": per, "n_positive": int(sum(x > 0 for x in nets)),
            "n_windows": len(per), "median_net_pct": float(np.median(nets)) if nets else None}


# ---------------------------------------------------------------------------
# F07 bias & robustness
# ---------------------------------------------------------------------------
def f07(dev, d1d_root="data/historical/d1d"):
    keep = dev.dropna(subset=[SCORE, "fwd_ret_1"])
    syms = pd.Index(keep.index.get_level_values("symbol"))
    keep2 = keep.copy()
    keep2["sym"] = syms
    keep2["sector"] = [sector_of(s) for s in syms]
    sec_ic = {}
    for sec, g in keep2.groupby("sector"):
        if len(g) >= aa.MIN_OBS_PER_IC and g[SCORE].nunique() >= 5:
            st = aa.ic_stats(g[SCORE].to_numpy(float), g["fwd_ret_1"].to_numpy(float),
                             g.index.get_level_values("symbol").to_numpy())
            sec_ic[sec] = {"n": st["n"], "ic": st["spearman_ic"], "p": st["pvalue"]}
    sym_ic = {s: aa.ic_stats(g[SCORE].to_numpy(float), g["fwd_ret_1"].to_numpy(float),
                             g.index.get_level_values("symbol").to_numpy())["spearman_ic"]
              for s, g in keep2.groupby("sym") if len(g) >= 200 and g[SCORE].nunique() >= 5}
    liq = {}
    vol_root = Path(d1d_root)
    if vol_root.exists():
        adv = {}
        for p in sorted(vol_root.glob("*.parquet")):
            sym = p.stem.replace(".", "_")
            if sym not in sym_ic:
                continue
            df = pd.read_parquet(p, columns=["volume"])
            adv[sym] = float(df["volume"].tail(252).mean())
        keys = [s for s in sym_ic if s in adv and adv[s] > 0]
        if len(keys) >= 10:
            liq = {"n_symbols": len(keys),
                   "corr_ln_adv_ic": round(float(np.corrcoef(np.log([adv[k] for k in keys]),
                                                               [sym_ic[k] for k in keys])[0, 1]), 4)}
    top_sector = sorted(sec_ic.items(), key=lambda kv: -abs(kv[1]["ic"]))[:5]
    return {"sector_ic": sec_ic, "top_sectors_by_abs_ic": [{"sector": s, **v} for s, v in top_sector],
            "symbol_ic": sym_ic, "liquidity_ln_adv_ic_corr": liq}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="F02,F03,F04,F05,F06,F07")
    args = ap.parse_args()
    stages = [s.strip() for s in args.stages.split(",")]

    frz, dev = load()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"dev panel: {dev.shape}")

    if "F02" in stages:
        r = f02(dev, frz); (OUT_DIR / "interpretation.json").write_text(json.dumps(r, indent=1, default=str))
        print("F02", {k: r[k] for k in ("active_dates", "date_coverage", "mean_fwd_active_pct")})
    if "F03" in stages:
        r = f03(dev); (OUT_DIR / "component_contrib.json").write_text(json.dumps(r, indent=1, default=str))
        print("F03 pooled IC:", {k: (v.get("spearman_ic") if isinstance(v, dict) else v)
                                 for k, v in r["pooled_ic_h1"].items()})
    if "F04" in stages:
        r = f04(dev); (OUT_DIR / "strategy_backtest.json").write_text(json.dumps(r, indent=1, default=str))
        for c, blk in r["constructions"].items():
            row = blk["constructions"][0]
            print("F04", c, "25bp:", {k: row.get(k) for k in ("active_days", "net_cum_pct", "sharpe", "max_drawdown_pct")})
    if "F05" in stages:
        r = f05(dev); (OUT_DIR / "stat_uncertainty.json").write_text(json.dumps(r, indent=1, default=str))
        print("F05", {k: r[k] for k in ("n_eff", "ci95_expectancy_bps")})
    if "F06" in stages:
        r = f06(dev); (OUT_DIR / "walk_forward.json").write_text(json.dumps(r, indent=1, default=str))
        print("F06", {k: r[k] for k in ("n_positive", "n_windows", "median_net_pct")})
    if "F07" in stages:
        r = f07(dev); (OUT_DIR / "bias_analysis.json").write_text(json.dumps(r, indent=1, default=str))
        print("F07 top sectors:", r["top_sectors_by_abs_ic"][:3], "liq:", r["liquidity_ln_adv_ic_corr"])
    print("done.")


if __name__ == "__main__":
    main()