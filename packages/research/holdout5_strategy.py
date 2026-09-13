"""holdout_5 — locked COMP3 STRATEGY V2 confirmation evaluator (Phase 12-14).

One-shot evaluation of the frozen V2 constructions on the NEW untouched
holdout-5 corpus (data/holdout_5, lock 13a1eeb11cac...). Pre-registered in
reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md (incl. Amendment 1) and
reports/COMP3_STRATEGY_V2_SPEC_2026-09.md. NOTHING is re-selected or re-run
after sight.

Flow:
  1. verify corpus lock sha256 == manifest sha256
  2. build panels if missing (alpha_dataset.build_panel + alpha_v2_features),
     plus TRUE session returns close[t+1]/open[t+1]-1 from raw d1d bars
     (the frozen trading-rule P&L)                      [step --build]
  3. reconstruct frozen COMP3 score/gate verbatim
  4. constructions (frozen, one-shot): D1_CAP8 m=13 (PRIMARY), D2_QUINTILE m=8,
     V1_DECILE m=4 (benchmark), all @ 25/50/100 bps
  5. metrics | concentration | tail | regimes | sector/symbol | IC diagnostic
  6. Phase 14 A-G decision on D1_CAP8 + Phase 15 paper-trading gate
  7. emit reports/COMP3_HOLDOUT5_CONFIRMATION_2026-09.md + data/comp3/holdout5_results.json

Usage:
  python -m packages.research.holdout5_strategy --build     # build panels
  python -m packages.research.holdout5_strategy --evaluate  # locked evaluation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from packages.research import alpha_analysis as aa
from packages.research import alpha_dataset as ad
from packages.research import alpha_v2_features as fv
from packages.research import composite_alpha as ca
from packages.research.metrics import _max_drawdown, _sharpe, _sortino
from packages.research.vt_signal import sector_of

HOLD5 = Path("data/holdout_5")
D1D = HOLD5 / "d1d"
PANEL = HOLD5 / "alpha_panel_holdout5.parquet"
V2PANEL = Path("data/alpha_v2/holdout5_v2_panel.parquet")
SESS_PANEL = HOLD5 / "session_returns_holdout5.parquet"
RESULT = Path("data/comp3/holdout5_results.json")
CLASS_OUT = Path("data/comp3/holdout5_classification.json")
REPORT = Path("reports/COMP3_HOLDOUT5_CONFIRMATION_2026-09.md")

COSTS_BPS = (25, 50, 100)
# frozen V2 constructions (Amendment 1 / V2 spec): m per side, equal weight 1/m
CONSTRUCTIONS = {
    "D1_CAP8": {"m": 13, "role": "PRIMARY (diversified D1, cap C=8%)"},
    "D2_QUINTILE": {"m": 8, "role": "control (quintile EW = V1 quintile)"},
    "V1_DECILE": {"m": 4, "role": "V1 benchmark (decile EW, concentrated)"},
}
TOP5_BAR = 0.30
MIN_DAYS = 20
TAIL_PROTO = [("full", None), ("winsorized_1pct", (1, 99)),
              ("drop_1pct", (1, 99)), ("drop_5pct", (5, 95))]
SEED = 7
SCORE = "COMP3_REVERSAL_BREADTH_DISP"


# ---------------------------------------------------------------------------
# corpus lock + panels
# ---------------------------------------------------------------------------
def corpus_ready() -> bool:
    return (HOLD5 / "dataset_lock.json").exists() and (HOLD5 / "eligible_symbols.json").exists()


def verify_lock() -> str:
    lock = json.loads((HOLD5 / "dataset_lock.json").read_text())
    actual = hashlib.sha256((HOLD5 / "manifest.json").read_bytes()).hexdigest()
    ok = lock.get("sha256") == actual
    return f"{'OK' if ok else 'MISMATCH'} locked={lock.get('sha256')} actual={actual}"


def build() -> None:
    ad.store_root = lambda: HOLD5
    p = ad.build_panel(verbose=True)
    p.to_parquet(PANEL)
    fv.PANELS["holdout5"] = (str(PANEL), str(D1D))
    comp = fv.build_v2_panel("holdout5")
    p2 = fv.compute_v2_features(comp)
    p2.sort_index().to_parquet(V2PANEL)

    # true session returns close[t+1] / open[t+1] - 1, aligned to signal date t
    frames = []
    for f in sorted(D1D.glob("*.parquet")):
        d1 = pd.read_parquet(f, columns=["open", "close", "volume"])
        d1 = d1[d1["volume"] > 0]
        ratio = (d1["close"] / d1["open"] - 1).shift(-1).rename("session_ret")
        df = ratio.to_frame()
        df["symbol"] = f.stem                       # SYMBOL_NS (panel convention)
        frames.append(df.set_index("symbol", append=True).swaplevel("symbol", "ts"))
    sess = pd.concat(frames).sort_index()
    sess.to_parquet(SESS_PANEL)
    print(f"wrote {PANEL}, {V2PANEL}, {SESS_PANEL}")


# ---------------------------------------------------------------------------
# locked reconstruction
# ---------------------------------------------------------------------------
def load() -> tuple[pd.DataFrame, dict]:
    frz = json.loads(ca.FRZ_PATH.read_text())
    assert frz.get("version") == 2
    p = pd.read_parquet(V2PANEL)
    cols = ca.composite_columns(p, frz)
    for name, (score, _lbl) in cols.items():
        p[name] = score
    sess = pd.read_parquet(SESS_PANEL)
    s = sess["session_ret"].copy()
    s.index = s.index.rename(["symbol", "date"])
    p = p.join(s, how="left")
    return p, frz


# ---------------------------------------------------------------------------
# construction backtests on ACTIVE dates using session returns
# ---------------------------------------------------------------------------
def ls_active(panel, m, cost_bp):
    sub = panel.dropna(subset=[SCORE, "session_ret"]).copy()
    sub["dt"] = sub.index.get_level_values("date")
    dates = pd.Index(np.unique(sub["dt"])).sort_values()
    rows, prev_w = [], None
    for t in dates:
        day = sub[sub["dt"] == t]
        if len(day) < MIN_DAYS:
            continue
        k = min(m, len(day) // 2)
        if k < 1:
            continue
        day = day.sort_values(SCORE)
        w = pd.Series(0.0, index=day.index)
        w.loc[day.iloc[-k:].index] = 1.0 / k
        w.loc[day.iloc[:k].index] = -1.0 / k
        net = day["session_ret"].to_numpy()
        gross = float((w.to_numpy() * net).sum())
        turnover = float(np.abs(w - prev_w).sum()) if prev_w is not None else 2.0
        pnl = dict(zip(day.index.get_level_values("symbol").astype(str),
                       np.around(w.to_numpy() * net, 12)))
        rows.append({"date": str(t)[:10], "gross": gross,
                     "net": gross - turnover * cost_bp / 1e4, "turnover": turnover,
                     "symbols": sorted(day.index.get_level_values("symbol")),
                     "w": np.round(w.to_numpy(), 6), "pnl": pnl})
        prev_w = w
    return rows


def metrics(rows):
    if len(rows) < 5:
        return {"status": "INSUFFICIENT", "active_days": len(rows)}
    net = np.array([r["net"] for r in rows])
    equity = pd.Series(np.cumprod(1 + net))
    gp, gl = float(net[net > 0].sum()), abs(float(net[net <= 0].sum()))
    return {"status": "OK", "active_days": len(rows),
            "avg_positions_side": round(float(np.mean([int(np.count_nonzero(r["w"])) // 2 for r in rows])), 2),
            "avg_turnover": round(float(np.mean([r["turnover"] for r in rows])), 4),
            "gross_cum_pct": round(float(np.prod(1 + np.array([r["gross"] for r in rows])) - 1) * 100, 4),
            "net_cum_pct": round(float(np.prod(1 + net) - 1) * 100, 4),
            "avg_net_bps": round(float(net.mean() * 1e4), 4),
            "median_net_bps": round(float(np.median(net) * 1e4), 4),
            "expectancy_bps": round(float(net.mean() * 1e4), 4),
            "win_rate": round(float((net > 0).mean()), 4),
            "profit_factor": round(float(gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0), 4),
            "max_drawdown_pct": round(_max_drawdown(equity) * 100, 4),
            "sharpe": round(_sharpe(net, 1), 4), "sortino": round(_sortino(net, 1), 4),
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
    conc_days = float(np.mean([max(np.abs(r["w"])) > 1.5 / (len(r["w"]) // 2)
                               for r in rows if len(r["w"])]))
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
            "leave_one_out_sign_flips": flips, "leave_one_out": loso,
            "concentration_fragile": bool(fragile),
            "top5_pass": float(shares["top5_share"]) < TOP5_BAR}


def tail_diag(rows):
    net = np.array([r["net"] for r in rows])
    sizes = np.array([np.count_nonzero(r["w"]) for r in rows])
    out = {}
    for name, bounds in TAIL_PROTO:
        if bounds is None:
            series = net
        else:
            lo, hi = np.nanpercentile(net, bounds[0]), np.nanpercentile(net, bounds[1])
            series = np.clip(net, lo, hi) if name.startswith("winsorized") else net[(net >= lo) & (net <= hi)]
        if len(series) < 5:
            out[name] = {"status": "INSUFFICIENT"}
            continue
        out[name] = {"n": int(len(series)),
                     "net_cum_pct": round(float(np.prod(1 + series) - 1) * 100, 4),
                     "worst_day_bps": round(float(series.min() * 1e4), 4)}
    return out


def regimes(panel, rows):
    daily = panel[["date_str", "G1_breadth_rise", "G6_breadth_mom5", "G4_xs_ret_disp",
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
                         "expectancy_bps": round(float(np.mean(vals) * 1e4), 4)}
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


def _pooled_ic(panel):
    keep = panel.dropna(subset=[SCORE, "session_ret"])
    st = aa.ic_stats(keep[SCORE].to_numpy(float), keep["session_ret"].to_numpy(float),
                     keep.index.get_level_values("symbol").to_numpy())
    return {k: st[k] for k in ("n", "n_eff", "spearman_ic", "pvalue", "sign")}


# ---------------------------------------------------------------------------
# Phase 14 A-G decision on PRIMARY (D1_CAP8) + paper-trading gate
# ---------------------------------------------------------------------------
def classify(res):
    d = res["constructions"]["D1_CAP8"]
    r25 = d.get("25bps", {})
    if r25.get("status") == "INSUFFICIENT" or r25.get("active_days", 0) < 50:
        return {"grade": "G INCONCLUSIVE", "paper_trade": False,
                "reason": "insufficient active days / sample"}
    net_pos = (r25.get("net_cum_pct") or 0) > 0
    exp_pos = (r25.get("expectancy_bps") or 0) > 0
    c = res["concentration"]["D1_CAP8"]
    tail = res["tail"]["D1_CAP8"]
    conc_ok = not c["concentration_fragile"] and float(c["top5_share"]) < TOP5_BAR
    mdd_ok = abs(r25.get("max_drawdown_pct") or 0) < 40
    cost_ok = (res["constructions"]["D1_CAP8"].get("100bps", {}).get("net_cum_pct") or 1) > 0
    exp_bps = r25.get("expectancy_bps") or 0
    n_same = sum(1 for tbl in ("full", "winsorized_1pct", "drop_1pct", "drop_5pct")
                 if (tail.get(tbl, {}).get("net_cum_pct") or 0) > 0)
    tail_ok = n_same >= 3
    suf_ok = r25.get("active_days", 0) >= 300
    wf = res.get("walk_forward_split", {})
    temporal_ok = wf.get("n_positive_half_years", 0) / max(wf.get("n_half_years", 1), 1) > 0.5

    gates = {"positive_net_expectancy": net_pos and exp_pos,
             "sufficient_sample": suf_ok,
             "acceptable_drawdown": mdd_ok,
             "acceptable_concentration": conc_ok,
             "positive_under_realistic_costs": cost_ok,
             "temporal_robustness": temporal_ok and tail_ok,
             "no_leakage": res.get("corpus_lock", "").startswith("OK")}
    passed = all(gates.values())

    if not net_pos:
        grade, reason = "E FAILED TO REPLICATE", "D1_CAP8 net cumulative <= 0 @25bps"
    elif not cost_ok:
        grade, reason = "F COST-FRAGILE", "gross positive but net<=0 @100bps stress"
    elif not conc_ok:
        grade, reason = "D STILL CONCENTRATION-FRAGILE", "top-5 share>=30% or sign flip on leave-one-out"
    elif not mdd_ok:
        grade, reason = "G INCONCLUSIVE", "drawdown >= 40% (unstable)"
    elif exp_pos and suf_ok and conc_ok and cost_ok and mdd_ok and temporal_ok and tail_ok:
        grade, reason = "A ROBUST DIVERSIFIED", "all A-grade gates satisfied on D1_CAP8"
    elif exp_pos and suf_ok and conc_ok:
        grade, reason = "B PROMISING-INSUFFICIENT", "positive expectancy, acceptable concentration, residual robustness/cost still open"
    else:
        grade, reason = "G INCONCLUSIVE", "mixed signals; no clean classification"

    return {"grade": grade, "reason": reason, "paper_trade": bool(passed), "gates": gates}


# ---------------------------------------------------------------------------
# evaluation + report
# ---------------------------------------------------------------------------
def evaluate() -> dict:
    panel, frz = load()
    panel["date_str"] = panel.index.get_level_values("date").astype(str).str[:10]
    res = {"freeze_version": frz["version"], "corpus": "holdout_5 (untouched)",
           "corpus_lock": verify_lock(), "score": SCORE,
           "constructions": {}, "concentration": {}, "tail": {}, "regimes": {}, "symbol_sector": {}}
    for name, cfg in CONSTRUCTIONS.items():
        res["constructions"][name] = {"role": cfg["role"], "m": cfg["m"],
                                      **{f"{bp}bps": metrics(ls_active(panel, cfg["m"], bp))
                                         for bp in COSTS_BPS}}
    r25 = {name: ls_active(panel, cfg["m"], 25) for name, cfg in CONSTRUCTIONS.items()}
    for name in CONSTRUCTIONS:
        res["concentration"][name] = concentration(r25[name])
        res["tail"][name] = tail_diag(r25[name])
        res["regimes"][name] = regimes(panel, r25[name])
        res["symbol_sector"][name] = symbol_sector(r25[name])
    # temporal robustness across contiguous half-year splits (primary only)
    prim_rows = r25["D1_CAP8"]
    idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in prim_rows])
    tiles = []
    for (y, h), g in pd.Series(range(len(idx))).groupby([idx.year, (idx.month - 1) // 6]):
        vals = [prim_rows[i]["net"] for i in g.index]
        tiles.append(round(float(np.prod(1 + np.array(vals)) - 1) * 100, 4))
    res["walk_forward_split"] = {"n_half_years": len(tiles),
                                 "n_positive_half_years": int(sum(x > 0 for x in tiles)),
                                 "half_year_net_pct": tiles}
    res["ic_diagnostics"] = _pooled_ic(panel)
    res["classification"] = classify(res)
    res["locked"] = "Frozen V2 spec + one-shot evaluation on untouched holdout-5; no reruns."
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(res, indent=1, default=str))
    CLASS_OUT.write_text(json.dumps(res["classification"], indent=1, default=str))
    report(res)
    return res


def report(res):
    c = res["classification"]
    header = [
        "# COMP3 STRATEGY V2 — Holdout-5 Confirmation (Phase 12-14)",
        "",
        f"- **Grade:** `{c['grade']}` — {c['reason']}",
        f"- **Paper-trading gate (Phase 15):** "
        f"{'ALLOWED for COMP3_STRATEGY_V2' if c.get('paper_trade') else 'DO NOT PAPER TRADE'}"
        f"{'' if c.get('paper_trade') else ' — gate closed'}",
        f"- **Corpus lock:** {res['corpus_lock']}",
        f"- **Score:** {res['score']}",
        f"- **D1_CAP8 (PRIMARY) @25bps:** net {res['constructions']['D1_CAP8']['25bps'].get('net_cum_pct')}% "
        f"exp {res['constructions']['D1_CAP8']['25bps'].get('expectancy_bps')}bps "
        f"MDD {res['constructions']['D1_CAP8']['25bps'].get('max_drawdown_pct')}% "
        f"top5 {res['concentration']['D1_CAP8'].get('top5_share')}",
        "",
    ]
    if c.get("gates"):
        header += ["### Phase 15 gates", "```",
                   json.dumps(c["gates"], indent=1), "```", ""]
    body = []
    for name, cfg in CONSTRUCTIONS.items():
        body += [f"### {name} ({cfg['role']})",
                 "```",
                 json.dumps({b: res['constructions'][name][f'{b}bps'] for b in COSTS_BPS}, indent=1)[:2600],
                 "```"]
    body += ["### concentration / tail / regimes / sectors",
             "```",
             json.dumps({k: res[k] for k in ("concentration", "tail", "regimes", "symbol_sector")}, indent=1)[:4000],
             "```"]
    body += ["", f"### Walk-forward (half-year tiles, D1_CAP8): {json.dumps(res['walk_forward_split'])}",
             "", "One locked evaluation on untouched holdout-5. Negative/uncertain "
                 "results reported as-is; no reruns. Holdout-4 (+115%) is NOT used "
                 "as confirmation."]
    REPORT.write_text("\n".join(header + body))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    args = ap.parse_args()
    if args.build:
        if not corpus_ready():
            print("holdout_5 corpus not acquired yet; run select + acquire first")
            return
        build()
    if args.evaluate:
        if not corpus_ready():
            print(f"holdout_5 corpus missing ({HOLD5}); nothing to evaluate yet.")
            return
        res = evaluate()
        print(json.dumps(res["classification"], indent=1))
        print(f"wrote {RESULT} {REPORT}")


if __name__ == "__main__":
    main()