"""holdout_4 - locked COMP3 strategy confirmation evaluator (Phases 12E..12M).

Pre-registered, written BEFORE any holdout-4 data is acquired. Nothing on this
file is recomputed, re-selected or re-weighted after result sight (Phase 12B/L).

Flow:
  1. verify corpus lock: data/holdout_4/dataset_lock.json sha256 == manifest sha256
  2. build panels if missing (alpha_dataset.build_panel + alpha_v2_features v2),
     plus TRUE SESSION returns close[t+1]/open[t+1] - 1 from raw d1d bars
     (the frozen trading rule P&L; close-to-close fwd_ret_1 is kept for IC
     diagnostics only)            [step --build]
  3. reconstruct frozen COMP3 score/gate from composite_freeze.json v2 verbatim
  4. constructions: quintile_eq (PRIMARY) + decile_eq (comparison) @ 25/50/100 bps
  5. Phase 12F metrics  | 12G robustness | 12H concentration | 12I tail
     | 12J uncertainty | 12M A-G classification
  6. emit reports/COMP3_HOLDOUT4_CONFIRMATION_2026-09.md + data/comp3/holdout4_results.json

Usage:
  python -m packages.research.holdout4_strategy --build     # build panels (needs corpus)
  python -m packages.research.holdout4_strategy --evaluate  # locked evaluation
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

HOLD4 = Path("data/holdout_4")
D1D = HOLD4 / "d1d"
PANEL = HOLD4 / "alpha_panel_holdout4.parquet"
V2PANEL = Path("data/alpha_v2/holdout4_v2_panel.parquet")
SESS_PANEL = HOLD4 / "session_returns_holdout4.parquet"
RESULT = Path("data/comp3/holdout4_results.json")
CLASS_OUT = Path("data/comp3/holdout4_classification.json")
REPORT = Path("reports/COMP3_HOLDOUT4_CONFIRMATION_2026-09.md")

COSTS_BPS = (25, 50, 100)
Q5, D10 = 0.20, 0.10          # quintile_eq primary / decile_eq comparison
MIN_DAYS = 20
TAIL_PROTO = [("full", None), ("winsorized_1pct", (1, 99)),
              ("drop_1pct", (1, 99)), ("drop_5pct", (5, 95))]
SEED = 7

SCORE = "COMP3_REVERSAL_BREADTH_DISP"
A_GRADE = ("A CONFIRMED", "B PROMISING", "C FAILED TO REPLICATE",
           "D COST-FRAGILE", "E CONCENTRATION-FRAGILE", "F UNSTABLE", "G INCONCLUSIVE")


# ---------------------------------------------------------------------------
# corpus lock + panels
# ---------------------------------------------------------------------------
def corpus_ready() -> bool:
    return (HOLD4 / "dataset_lock.json").exists() and (HOLD4 / "eligible_symbols.json").exists()


def verify_lock() -> str:
    lock = json.loads((HOLD4 / "dataset_lock.json").read_text())
    actual = hashlib.sha256((HOLD4 / "manifest.json").read_bytes()).hexdigest()
    ok = lock.get("sha256") == actual
    return f"{'OK' if ok else 'MISMATCH'} locked={lock.get('sha256')} actual={actual}"


def build(self) -> None:
    ad.store_root = lambda: HOLD4
    p = ad.build_panel(verbose=True)
    p.to_parquet(PANEL)
    fv.PANELS["holdout4"] = (str(PANEL), str(HOLD4 / "d1d"))
    comp = fv.build_v2_panel("holdout4")
    p2 = fv.compute_v2_features(comp)
    p2.sort_index().to_parquet(V2PANEL)

    # true session returns close[t+1] / open[t+1] - 1, aligned to signal date t
    frames = []
    for f in sorted(D1D.glob("*.parquet")):
        d1 = pd.read_parquet(f)
        d1 = d1[(d1["volume"] > 0)]
        d1["symbol"] = f.stem.replace(".", "_")
        sess = d1.groupby("symbol", group_keys=False).apply(
            lambda g: pd.Series((g["close"].shift(-1) / g["open"] - 1).values,
                                index=g.index, name="session_ret"))
        frames.append(sess)
    sess = pd.concat(frames).rename("session_ret").to_frame()
    sess.index = sess.index.rename(["ts"])
    sess["symbol"] = sess.index.get_level_values(0)
    sess = sess.set_index("symbol", append=True).swaplevel("symbol", "ts")
    sess.to_parquet(SESS_PANEL)
    print(f"wrote {PANEL}, {V2PANEL}, {SESS_PANEL}")


# ---------------------------------------------------------------------------
# locked reconstruction
# ---------------------------------------------------------------------------
def load() -> tuple[pd.DataFrame, dict]:
    frz = json.loads(ca.FRZ_PATH.read_text())
    assert frz.get("version") == 2
    p = pd.read_parquet(V2PANEL)
    p = p[p["split"] != ""].copy() if "split" in p.columns else p
    cols = ca.composite_columns(p, frz)
    for name, (score, _lbl) in cols.items():
        p[name] = score
    sess = pd.read_parquet(SESS_PANEL)
    s = sess["session_ret"]
    p = p.join(s, how="left")
    return p, frz


# ---------------------------------------------------------------------------
# construction backtests on ACTIVE dates using session returns
# ---------------------------------------------------------------------------
def ls_active(panel, coverage, cost_bp):
    sub = panel.dropna(subset=[SCORE, "session_ret"]).copy()
    sub["dt"] = sub.index.get_level_values("date")
    dates = pd.Index(np.unique(sub["dt"])).sort_values()
    rows, prev_w = [], None
    for t in dates:
        day = sub[sub["dt"] == t]
        if len(day) < MIN_DAYS:
            continue
        k = max(1, int(round(len(day) * coverage)))
        day = day.sort_values(SCORE)
        w = pd.Series(0.0, index=day.index)
        w.loc[day.iloc[-k:].index] = 1.0 / k
        w.loc[day.iloc[:k].index] = -1.0 / k
        net = day["session_ret"].to_numpy()
        gross = float((w.to_numpy() * net).sum())
        turnover = float(np.abs(w - prev_w).sum()) if prev_w is not None else 2.0
        rows.append({"date": str(t)[:10], "gross": gross,
                     "net": gross - turnover * cost_bp / 1e4, "turnover": turnover,
                     "symbols": sorted(day.index.get_level_values("symbol"))})
        prev_w = w
    return rows


def metrics(rows):
    if len(rows) < 5:
        return {"status": "INSUFFICIENT", "active_days": len(rows)}
    net = np.array([r["net"] for r in rows])
    equity = pd.Series(np.cumprod(1 + net))
    gp, gl = float(net[net > 0].sum()), abs(float(net[net <= 0].sum()))
    return {"status": "OK", "active_days": len(rows),
            "avg_turnover": round(float(np.mean([r["turnover"] for r in rows])), 4),
            "gross_cum_pct": round(float(np.prod(1 + [r["gross"] for r in rows]) - 1) * 100, 4),
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


def run_constructions(panel, cost_bp):
    return {"quintile_eq": metrics(ls_active(panel, Q5, cost_bp)),
            "decile_eq": metrics(ls_active(panel, D10, cost_bp))}


# ---------------------------------------------------------------------------
# Phase 12H concentration
# ---------------------------------------------------------------------------
def concentration(panel, primary="quintile_eq", cost_bp=25):
    base_rows = ls_active(panel, Q5, cost_bp)
    base = np.array([r["net"] for r in base_rows])
    base_cum = float(np.prod(1 + base) - 1)
    contrib = {}
    for r in base_rows:
        for s in r["symbols"]:
            contrib[s] = contrib.get(s, 0.0) + r["net"]
    ranked = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))
    top5 = {s: round(v, 5) for s, v in ranked[:5]}
    top10 = {s: round(v, 5) for s, v in ranked[:10]}
    top5_share = abs(sum(v for _, v in ranked[:5])) / max(abs(base.sum()), 1e-9)
    # leave-one-symbol-out
    loso = {}
    for s in list(contrib):
        rows = [r for r in base_rows if s not in r["symbols"]]
        if len(rows) < 5:
            continue
        cum = float(np.prod(1 + np.array([r["net"] for r in rows])) - 1)
        loso[s] = round(cum, 4)
    sign_flips = [s for s, cum in loso.items() if (cum >= 0) != (base_cum >= 0)]
    fragile = top5_share >= 0.5 or any((loso.get(s, base_cum) * base_cum < 0) for s in sign_flips)
    return {"base_net_cum_pct": round(base_cum * 100, 4), "top5_share_abs": round(float(top5_share), 4),
            "top5": top5, "top10": top10, "leave_one_out_sign_flips": sign_flips,
            "leave_one_out": loso,
            "concentration_fragile": bool(fragile)}


# ---------------------------------------------------------------------------
# Phase 12I tail + 12J uncertainty
# ---------------------------------------------------------------------------
def tail_diag(panel, cost_bp=25):
    rows = ls_active(panel, Q5, cost_bp)
    net = np.array([r["net"] for r in rows])
    out = {}
    for name, bounds in TAIL_PROTO:
        if bounds is None:
            series = net
        else:
            lo, hi = np.nanpercentile(net, bounds[0]), np.nanpercentile(net, bounds[1])
            if name.startswith("winsorized"):
                series = np.clip(net, lo, hi)
            else:
                m = (net >= lo) & (net <= hi)
                series = net[m]
        if len(series) < 5:
            out[name] = {"status": "INSUFFICIENT"}
            continue
        cum = float(np.prod(1 + series) - 1) * 100
        out[name] = {"n": int(len(series)), "net_cum_pct": round(cum, 4),
                     "worst_day_bps": round(float(series.min() * 1e4), 4),
                     "share_of_full": round(float(cum) / float(np.prod(1 + net) - 1) * 100, 1)
                     if np.prod(1 + net) != 1 else None}
    return out


def uncertainty(panel, cost_bp=25, n_sims=5000):
    rows = ls_active(panel, Q5, cost_bp)
    net = np.array([r["net"] for r in rows])
    n = len(net)
    rho1 = float(pd.Series(net).autocorr(1)) if n > 3 else None
    n_eff = int(n * (1 - rho1) / (1 + rho1)) if rho1 is not None else n
    rng = np.random.default_rng(SEED)
    block = max(2, int(round(abs(rho1) * n))) if rho1 is not None else 1
    boot = np.array([np.concatenate([rng.choice(net, size=block)
                                     for _ in range(int(np.ceil(n / block)))])[:n].mean()
                     for _ in range(n_sims)])
    lo, hi = sorted(np.percentile(boot, [2.5, 97.5]).tolist())
    return {"n_days": n, "autocorr_lag1": rho1, "n_eff": n_eff,
            "block_size": block, "sims": n_sims,
            "ci95_expectancy_bps": [round(lo * 1e4, 4), round(hi * 1e4, 4)]}


# ---------------------------------------------------------------------------
# Phase 12G robustness (diagnosis only)
# ---------------------------------------------------------------------------
def robustness(panel, cost_bp=25):
    rows = ls_active(panel, Q5, cost_bp)
    net_by = {}
    for r in rows:
        net_by[r["date"]] = r["net"]
    s = pd.Series(net_by)
    tiles = s.groupby(pd.cut(s.index, bins=6)).agg(["mean", "count", "sum"])
    regime = {}
    sub = panel.dropna(subset=[SCORE, "session_ret"])
    if "regime_bucket" in panel.columns:
        sub = sub.copy()
        sub["dt"] = sub.index.get_level_values("date")
        for b, g in sub.groupby("regime_bucket"):
            rws = [x for x in rows if x["date"] in set(g["dt"].astype(str).str[:10])]
            if rws:
                net = np.array([x["net"] for x in rws])
                regime[b] = {"active_days": len(net), "net_cum_pct": round(float(np.prod(1 + net) - 1) * 100, 4)}
    return {"half_year_tiles": tiles, "regime_breakdown": regime}


# ---------------------------------------------------------------------------
# Phase 12M classification
# ---------------------------------------------------------------------------
def classify(res):
    q = res["constructions"]["quintile_eq"]
    r25 = q.get("25bps", {})
    if r25.get("status") == "INSUFFICIENT" or r25.get("active_days", 0) < 50:
        return {"grade": "G INCONCLUSIVE", "reason": "insufficient active days / sample"}
    net_pos = (r25.get("net_cum_pct") or 0) > 0
    exp_pos = (r25.get("expectancy_bps") or 0) > 0
    d = res["constructions"]["decile_eq"]
    r100 = q.get("100bps", {})
    survivable = (r100.get("net_cum_pct") or 0) > 0
    cost_fragile = (r25.get("gross_cum_pct") or 0) > 0 and not net_pos
    conc_frag = res["concentration"].get("concentration_fragile", False)
    mdd_ok = abs(r25.get("max_drawdown_pct") or 0) < 50
    st = res["uncertainty"]
    ci_lo = st["ci95_expectancy_bps"][0] if isinstance(st.get("ci95_expectancy_bps"), list) else 0
    if cost_fragile:
        grade, reason = "D COST-FRAGILE", "gross positive but net<=0 @25bps"
    elif conc_frag:
        grade, reason = "E CONCENTRATION-FRAGILE", "top-5 share>=50% or sign flip on leave-one-out"
    elif not net_pos:
        grade, reason = "C FAILED TO REPLICATE", "net cumulative<=0 @25bps"
    elif not survivable:
        grade, reason = "D COST-FRAGILE", "does not survive 100bps stress"
    elif not mdd_ok:
        grade, reason = "F UNSTABLE", "drawdown>=50%"
    elif exp_pos and ci_lo > 0 and res["robustness"].get("positive_tile_frac", None):
        grade, reason = "A CONFIRMED", "positive expectancy, CI>0, positive majority tiles"
    elif exp_pos:
        grade, reason = "B PROMISING", "positive expectancy but CI includes 0 or limited robustness"
    else:
        grade, reason = "G INCONCLUSIVE", "no positive edge identified"
    return {"grade": grade, "reason": reason}


# ---------------------------------------------------------------------------
# evaluation + report
# ---------------------------------------------------------------------------
def evaluate() -> dict:
    panel, frz = load()
    res = {"freeze_version": frz["version"], "corpus": "holdout_4 (untouched)",
           "corpus_lock": verify_lock(), "score": SCORE,
           "constructions": {c: {f"{bp}bps": metrics(ls_active(panel, cov, bp))
                                 for bp in COSTS_BPS}
                             for c, cov in (("quintile_eq", Q5), ("decile_eq", D10))}}
    res["robustness"] = robustness(panel)
    res["concentration"] = concentration(panel)
    res["tail"] = tail_diag(panel)
    res["uncertainty"] = uncertainty(panel)
    res["ic_diagnostics"] = _pooled_ic(panel)
    res["classification"] = classify(res)
    res["locked"] = "File written before holdout_4 acquisition; single evaluation; no reruns."
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(res, indent=1, default=str))
    CLASS_OUT.write_text(json.dumps(res["classification"], indent=1, default=str))
    report(res)
    return res


def _pooled_ic(panel):
    keep = panel.dropna(subset=[SCORE, "fwd_ret_1"])
    st = aa.ic_stats(keep[SCORE].to_numpy(float), keep["fwd_ret_1"].to_numpy(float),
                     keep.index.get_level_values("symbol").to_numpy())
    return {k: st[k] for k in ("n", "n_eff", "spearman_ic", "pvalue", "sign")}


def report(res):
    c = res["classification"]
    lk = res["corpus_lock"]
    header = [
        "# COMP3 holdout-4 Confirmation (Phase 12M)",
        "",
        f"- **Grade:** `{c['grade']}` — {c['reason']}",
        f"- **Corpus lock:** {lk}",
        f"- **Score:** {res['score']}",
        "",
    ]
    body = [f"### quintile_eq (primary)",
            "```", json.dumps({k: res['constructions']['quintile_eq'][f'{b}bps'] for b in COSTS_BPS}, indent=1)[:3000], "```"]
    body += [f"### decile_eq (comparison)",
             "```", json.dumps({k: res['constructions']['decile_eq'][f'{b}bps'] for b in COSTS_BPS}, indent=1)[:3000], "```"]
    body += [f"### concentration / tail / uncertainty",
             "```", json.dumps({k: res[k] for k in ('concentration', 'tail', 'uncertainty')}, indent=1)[:3000], "```"]
    body += ["", "Single locked evaluation. Negative results are reported as-is; no reruns."]
    REPORT.write_text("\n".join(header + body))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    args = ap.parse_args()
    if args.build:
        if not corpus_ready():
            print("holdout_4 corpus not acquired yet; run select + acquire first")
            return
        build(None)
    if args.evaluate:
        if not corpus_ready():
            print(f"holdout_4 corpus missing ({HOLD4}); nothing to evaluate yet. "
                  f"verify_lock guide: {verify_lock()}")
            return
        res = evaluate()
        print(json.dumps(res["classification"], indent=1))
        print(f"wrote {RESULT} {REPORT}")


if __name__ == "__main__":
    main()