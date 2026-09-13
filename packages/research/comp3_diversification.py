"""COMP3 diversification research — Phases 4-11 (development study).

Pre-registered in reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md.

Runs on DEVELOPMENT ONLY:
  Phase 4   V1_DECILE_EQ vs D2 (V1_QUINTILE_EQ) vs D1(cap candidates)
  Phase 5   concentration metrics (top-1/3/5/10 shares, Herfindahl,
            max single |w|, avg positions, % concentrated days, LOTO)
  Phase 6   edge-survival comparison (concentrated vs diversified)
  Phase 7   cost stress 25/50/100 bps (gross -> cost -> net)
  Phase 8   regime robustness (breadth / dispersion / volatility states)
  Phase 9   symbol + sector contribution
  Phase 10  walk-forward (4 contiguous dev windows)
  Phase 11  tail robustness (full / winsorized_1pct / drop_1pct / drop_5pct)

Deterministic D1 cap selection on dev-TRAIN (report-only on validation):

Usage:
  python -m packages.research.comp3_diversification
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from packages.research import composite_alpha as ca
from packages.research.metrics import _max_drawdown, _sharpe, _sortino
from packages.research.vt_signal import sector_of

OUT = Path("reports/comp3_diversification_results.json")
REPORT = Path("reports/COMP3_DIVERSIFICATION_RESEARCH_2026-09.md")

COSTS_BPS = (25, 50, 100)
SEED = 7
SCORE = "COMP3_REVERSAL_BREADTH_DISP"
TOP5_BAR = 0.30          # concentration ceiling for cap qualification
D1_BASE = "D1_CAP"

# pre-registered candidate caps (feasible on a 40-symbol universe: 2*m_C <= N)
CAPS = {0.05: 20, 0.06: 17, 0.08: 13, 0.10: 10, 0.125: 8}

CONSTRUCTIONS = {
    "V1_DECILE_EQ": {"m": 4, "label": "V1 decile equal weight (concentrated baseline)"},
    "D2": {"m": 8, "label": "D2 / V1 quintile equal weight (no cap, diversification benchmark)"},
    **{f"{D1_BASE}{int(c * 100)}": {"m": m, "label": f"D1 weight cap {int(c * 100)}% (m={m}, w=1/{m})"}
       for c, m in CAPS.items()},
}

WF_WINDOWS = [
    ("W1", "2014-01-01", "2017-12-31"),
    ("W2", "2018-01-01", "2020-12-31"),
    ("W3", "2021-01-01", "2023-12-31"),
    ("W4", "2024-01-01", "2026-09-04"),
]
TAIL_PROTO = [("full", None), ("winsorized_1pct", (1, 99)),
              ("drop_1pct", (1, 99)), ("drop_5pct", (5, 95))]


def load():
    frz = json.loads(ca.FRZ_PATH.read_text())
    assert frz.get("version") == 2
    dev = pd.read_parquet(ca.DATAP)
    dev = dev[dev["split"] != ""].copy()
    cols = ca.composite_columns(dev, frz)
    for name, (score, _lbl) in cols.items():
        dev[name] = score
    dev["dt"] = dev.index.get_level_values("date")
    dev["date_str"] = dev["dt"].astype(str).str[:10]
    return dev


def run_construction(dev, m, cost_bp):
    """Daily-rebalanced L/S; per-side top-m equal weight 1/m.

    Uses the LOCKED holdout-4 execution conventions: pandas-aligned
    `|w - prev_w|.sum()` turnover (NaN-skip) and fwd_ret_1 forward label.
    """
    sub = dev.dropna(subset=[SCORE, "fwd_ret_1", "dt"]).copy()
    rows, prev_w = [], None
    for t in pd.Index(np.unique(sub["dt"])).sort_values():
        day = sub[sub["dt"] == t]
        k = min(m, len(day) // 2)
        if k < 1:
            continue
        day = day.sort_values(SCORE)
        w = pd.Series(0.0, index=day.index)
        w.loc[day.iloc[-k:].index] = 1.0 / k
        w.loc[day.iloc[:k].index] = -1.0 / k
        rets = day["fwd_ret_1"].to_numpy()
        gross = float((w.to_numpy() * rets).sum())
        turnover = float(np.abs(w - prev_w).sum()) if prev_w is not None else 2.0
        pnl = dict(zip(day.index.get_level_values("symbol").astype(str),
                       np.around(w.to_numpy() * rets, 12)))
        rows.append({"date": str(t)[:10], "gross": gross,
                     "net": gross - turnover * cost_bp / 1e4, "turnover": turnover,
                     "symbols": sorted(day.index.get_level_values("symbol").astype(str)),
                     "w": sorted(np.round(w.to_numpy(), 6).tolist()), "pnl": pnl})
        prev_w = w
    return rows


def book_metrics(rows):
    if len(rows) < 5:
        return {"status": "INSUFFICIENT", "active_days": len(rows)}
    net = np.array([r["net"] for r in rows])
    gross = np.array([r["gross"] for r in rows])
    equity = pd.Series(np.cumprod(1 + net))
    gp, gl = float(net[net > 0].sum()), abs(float(net[net <= 0].sum()))
    return {"status": "OK", "active_days": len(rows),
            "avg_positions_per_side": float(np.mean([int(np.count_nonzero(r["w"])) // 2 for r in rows])),
            "avg_turnover": round(float(np.mean([r["turnover"] for r in rows])), 4),
            "gross_cum_pct": round(float(np.prod(1 + gross) - 1) * 100, 4),
            "net_cum_pct": round(float(np.prod(1 + net) - 1) * 100, 4),
            "expectancy_bps": round(float(net.mean() * 1e4), 4),
            "win_rate": round(float((net > 0).mean()), 4),
            "profit_factor": round(float(gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0), 4),
            "max_drawdown_pct": round(_max_drawdown(equity) * 100, 4),
            "sharpe": round(_sharpe(net, 1), 4),
            "sortino": round(_sortino(net, 1), 4),
            "worst_day_bps": round(float(net.min() * 1e4), 4),
            "best_day_bps": round(float(net.max() * 1e4), 4)}


def concentration(rows):
    contrib = {}
    for r in rows:
        for s, c in r["pnl"].items():
            contrib[s] = contrib.get(s, 0.0) + c
    ranked = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))
    net_sum = float(sum(r["net"] for r in rows))
    denom = max(abs(net_sum), 1e-9)
    shares = {}
    for t in (1, 3, 5, 10):
        shares[f"top{t}_share"] = round(abs(sum(v for _, v in ranked[:t])) / denom, 4)
    herf = float(np.sum([v * v for v in contrib.values()]))
    maxw = max(max(np.abs(r["w"])) for r in rows)
    conc_days = float(np.mean([max(np.abs(r["w"])) > 1.5 / m for r in rows
                               for m in (len(r["w"]) // 2,)]))
    loso = {}
    for s in list(contrib):
        dropped = [r for r in rows if s not in r["symbols"]]
        if len(dropped) < 5:
            continue
        loso[s] = round(float(np.prod(1 + np.array([r["net"] for r in dropped])) - 1), 4)
    base_cum = float(np.prod(1 + np.array([r["net"] for r in rows])) - 1)
    flips = [s for s, v in loso.items() if (v >= 0) != (base_cum >= 0)]
    fragile = float(shares["top5_share"]) >= 0.5 or any(loso.get(s, base_cum) * base_cum < 0
                                                        for s in flips)
    return {"top1_share": shares["top1_share"], "top3_share": shares["top3_share"],
            "top5_share": shares["top5_share"], "top10_share": shares["top10_share"],
            "herfindahl_gross": round(herf, 4), "max_single_weight": round(maxw, 4),
            "pct_days_concentrated": round(conc_days, 4),
            "avg_active_positions_side": round(float(np.mean([len(r["w"]) // 2 for r in rows])), 2),
            "leave_one_out_sign_flips": flips, "leave_one_out": loso,
            "concentration_fragile": bool(fragile)}


def regimes(dev, rows):
    daily = dev[["date_str", "G1_breadth_rise", "G6_breadth_mom5", "G4_xs_ret_disp",
                 "mkt_vol_20", "regime_bucket"]].groupby("date_str").first()
    acc = {r["date"]: r["net"] for r in rows}
    med_g4 = daily["G4_xs_ret_disp"].median()
    q67, q33 = daily["mkt_vol_20"].quantile(0.67), daily["mkt_vol_20"].quantile(0.33)
    conds = {"breadth_high": daily["G1_breadth_rise"] >= 0.5,
             "breadth_low": daily["G1_breadth_rise"] < 0.5,
             "breadth_rising": daily["G6_breadth_mom5"] >= 0,
             "breadth_falling": daily["G6_breadth_mom5"] < 0,
             "disp_high": daily["G4_xs_ret_disp"] >= med_g4,
             "disp_low": daily["G4_xs_ret_disp"] < med_g4,
             "vol_high": daily["mkt_vol_20"] >= q67,
             "vol_low": daily["mkt_vol_20"] <= q33}
    out = {}
    for name, mask in conds.items():
        dates = daily.index[mask]
        vals = [acc[d] for d in dates if d in acc]
        if vals:
            out[name] = {"active_days": len(vals),
                         "expectancy_bps": round(float(np.mean(vals) * 1e4), 4),
                         "net_cum_pct": round(float(np.prod(1 + np.array(vals)) - 1) * 100, 4)}
    rb = {}
    for b, gd in daily.groupby("regime_bucket"):
        vals = [acc[d] for d in gd.index if d in acc]
        if vals:
            rb[str(b)] = {"active_days": len(vals),
                          "expectancy_bps": round(float(np.mean(vals) * 1e4), 4)}
    out["regime_bucket"] = rb
    return out


def symbol_sector(rows):
    contrib = {}
    for r in rows:
        for s, c in r["pnl"].items():
            contrib[s] = contrib.get(s, 0.0) + c
    sec = {}
    for s, c in contrib.items():
        sec.setdefault(sector_of(s), 0.0)
        sec[sector_of(s)] += c
    return {"symbols": {k: round(v, 5) for k, v in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))},
            "sectors": {k: round(v, 5) for k, v in sorted(sec.items(), key=lambda kv: -abs(kv[1]))}}


def walkforward(dev):
    dt = dev["dt"]
    out = {}
    for name, s, e in WF_WINDOWS:
        mask = (dt >= pd.Timestamp(s, tz=dt.dt.tz)) & (dt <= pd.Timestamp(e, tz=dt.dt.tz))
        wdev = dev[mask]
        rows = run_construction(wdev, CAPS[0.05], 25)
        out[name] = {"window": [s, e], "active_days": len(rows),
                     "net_cum_pct": book_metrics(rows).get("net_cum_pct"),
                     "expectancy_bps": book_metrics(rows).get("expectancy_bps"),
                     "sharpe": book_metrics(rows).get("sharpe")}
    nets = [v["net_cum_pct"] for v in out.values() if isinstance(v.get("net_cum_pct"), (int, float))]
    return {"windows": out, "n_positive": int(sum(x > 0 for x in nets)), "n_windows": len(out),
            "median_net_pct": float(np.median(nets)) if nets else None}


def tail(rows):
    net = np.array([r["net"] for r in rows])
    ret = {}
    for name, bounds in TAIL_PROTO:
        if bounds is None:
            series = net
        else:
            lo, hi = np.nanpercentile(net, bounds[0]), np.nanpercentile(net, bounds[1])
            series = np.clip(net, lo, hi) if name.startswith("winsorized") else net[(net >= lo) & (net <= hi)]
        if len(series) < 5:
            ret[name] = {"status": "INSUFFICIENT"}
            continue
        ret[name] = {"n": int(len(series)),
                     "net_cum_pct": round(float(np.prod(1 + series) - 1) * 100, 4),
                     "worst_day_bps": round(float(series.min() * 1e4), 4)}
    return ret


def select_cap(train_res):
    """Deterministic dev-TRAIN rule: largest cap with top5_share<0.30 and expectancy>0."""
    rows = []
    for cap, m in CAPS.items():
        r = train_res[f"D1_CAP{int(cap * 100)}"]
        rows.append((cap, r["top5_share"], r["expectancy_bps"]))
    both = [c for c, t, e in rows if t < TOP5_BAR and e > 0]
    if both:
        return max(both), "top5<30% AND expectancy>0"
    conc = [c for c, t, e in rows if t < TOP5_BAR]
    if conc:
        return max(conc), "top5<30% only (economic result may be <=0)"
    return 0.05, "fallback: no cap met concentration bar (flagged)"


def main() -> None:
    dev = load()
    res = {"phase": "COMP3 diversification (dev study)", "score": SCORE,
           "constructions": {}, "selection": {}, "walk_forward": {}, "report": str(REPORT)}
    print(f"dev panel {dev.shape}", flush=True)
    for name, cfg in CONSTRUCTIONS.items():
        blk = {"label": cfg["label"], "m": cfg["m"], "costs": {}}
        for bp in COSTS_BPS:
            rows = run_construction(dev, cfg["m"], bp)
            blk["costs"][f"{bp}bps"] = book_metrics(rows)
        r25 = run_construction(dev, cfg["m"], 25)
        blk["costs"]["25bps_summary"] = book_metrics(r25)["net_cum_pct"] if r25 else None
        blk["concentration"] = concentration(r25)
        blk["regimes"] = regimes(dev, r25)
        blk["symbol_sector"] = symbol_sector(r25)
        blk["tail"] = tail(r25)
        blk["walk_forward"] = walkforward(dev)
        res["constructions"][name] = blk
        m = blk["metrics_25"] = book_metrics(r25)
        print(f"  {name:10s} m={cfg['m']:>2} net25={m.get('net_cum_pct')} exp={m.get('expectancy_bps')} "
              f"top5={blk['concentration']['top5_share']} MDD={m.get('max_drawdown_pct')}", flush=True)

    # ---- train / validation tables for D1 selection ----
    def _by_split(span):
        d = dev[dev["split"] == span]
        out = {}
        for cap, m in CAPS.items():
            rows = run_construction(d, m, 25)
            met = book_metrics(rows)
            conc = concentration(rows)
            out[f"D1_CAP{int(cap * 100)}"] = {"expectancy_bps": met.get("expectancy_bps"),
                                              "net_cum_pct": met.get("net_cum_pct"),
                                              "top5_share": conc["top5_share"],
                                              "active_days": met.get("active_days")}
        return out

    train_tab = _by_split("train")
    val_tab = _by_split("validation")
    chosen, reason = select_cap(train_tab)
    res["selection"] = {
        "candidate_caps": {f"{int(c*100)}%": {"m": m, "train": train_tab[f"D1_CAP{int(c*100)}"],
                                               "validation_report": val_tab[f"D1_CAP{int(c*100)}"]}
                           for c, m in CAPS.items()},
        "selection_split": "train", "validation": "report only, no re-selection",
        "rule": f"largest cap with top5_share<{TOP5_BAR} AND expectancy>0 on dev-TRAIN",
        "chosen_cap": chosen, "reason": reason,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    md(res, chosen, reason)
    print(f"\nchosen D1 cap = {chosen}  ({reason})\nwrote {OUT} {REPORT}", flush=True)


def md(res, chosen, reason):
    L = ["# COMP3 Diversification Research — Development Study (Phases 4-11)",
         "", "Pre-registered in `reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md`.",
         f"\n### D1 cap selection (dev-TRAIN): **C = {int(chosen*100)}%** — {reason}",
         "\n| Cap | m/side | train exp bps | train top5 | train net% | val exp bps | val top5 | val net% |",
         "|---|---|---|---|---|---|---|---|"]
    for cap, m in CAPS.items():
        t = res["selection"]["candidate_caps"][f"{int(cap*100)}%"]["train"]
        v = res["selection"]["candidate_caps"][f"{int(cap*100)}%"]["validation_report"]
        L.append(f"| {int(cap*100)}% | {m} | {t['expectancy_bps']} | {t['top5_share']} | "
                 f"{t['net_cum_pct']} | {v['expectancy_bps']} | {v['top5_share']} | {v['net_cum_pct']} |")
    L += ["", "### Constructions @25bp (full dev)", "",
          "| Name | net% | exp bps | PF | MDD% | Sharpe | top5 | HHI | sign flips |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, b in res["constructions"].items():
        m = b["metrics_25"]
        c = b["concentration"]
        L.append(f"| {name} | {m.get('net_cum_pct')} | {m.get('expectancy_bps')} | {m.get('profit_factor')} "
                 f"| {m.get('max_drawdown_pct')} | {m.get('sharpe')} | {c['top5_share']} | "
                 f"{c['herfindahl_gross']} | {len(c['leave_one_out_sign_flips'])} |")
    L += ["", "See `reports/comp3_diversification_results.json` for full metrics incl. 50/100bp cost "
              "stress, regimes, sectors, walk-forward and tail. Holdout-5 was not touched."]
    REPORT.write_text("\n".join(L))


if __name__ == "__main__":
    main()