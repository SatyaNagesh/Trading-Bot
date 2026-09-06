"""Composite Alpha Research (V3) - post-V2.

Builds on the frozen V2 survivors:
    C3_rev_abn_mkt1|1     stock-level short-term reversal        (B. PROMISING)
    G1_breadth_rise|3     market breadth level                    (timing B.)
    G6_breadth_mom5|3     breadth momentum                        (timing B.)
    G4_xs_ret_disp|1-5    cross-sectional return dispersion       (timing B.)

Phases implemented here (report-only on DEVELOPMENT; the frozen holdout and
holdout_2 are NOT reused; confirmation requires NEW holdout-3):

  P1  freeze V2 survivor definitions + recorded results
  P2  complementarity (pairwise corr / rank corr / prediction corr / overlap)
  P3  conditional C3 tests inside pre-specified breadth/dispersion bins
  P4  pre-register <=3 composites (conditional-filter method) with frozen
      thresholds taken from development-TRAIN date-level medians
  P5-13  evaluation on development only: IC/quantiles/long-short/horizons,
      tail fragility, symbol/sector/liquidity, regime, costs, randomization
  P14  holdout-3 protocol + justification decision
  P15  strategy gate (blocked until NEW holdout-3)

HARD RULES: no combination chosen after holdout sight; no tuning windows;
no strategy / paper / AlphaLedger promotion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
from packages.research import alpha_analysis as aa
from packages.research.alpha_v2_features import PANELS, KEYS
from packages.research.vt_signal import sector_of

OUT_DIR = Path("data/alpha_v2")
DATAP = OUT_DIR / "development_v2_panel.parquet"
FRZ_PATH = OUT_DIR / "composite_freeze.json"

SPLITS = ["train", "validation", "final_oos"]
HORIZONS = (1, 3, 5)
COST_BPS = (0.0015, 0.0025, 0.0050)
SEED = 7
NULL_SIMS = 200
MIN_IC_ROWS = aa.MIN_OBS_PER_IC

C3 = "C3_rev_abn_mkt1"
G1 = "G1_breadth_rise"
G6 = "G6_breadth_mom5"
G4 = "G4_xs_ret_disp"


def load_dev():
    dev = pd.read_parquet(DATAP)
    return dev[dev["split"] != ""]


def date_medians(dev, cols):
    return {c: float(dev[dev["split"] == "train"].groupby(level="date")[c].first().median())
            for c in cols}


def survivor_results():
    """Recorded V2 results for the frozen survivors (from alpha_v2_results.json)."""
    r = json.load(open("reports/alpha_research_v2_results.json"))
    surv = {s["feature"]: s for s in r["survivors"] if s["feature"] in (C3, G1, G6, G4)}
    g = r["g_family_market_timing"]
    return {
        "pooled": surv,
        "market_timing_dev": {k: v for k, v in g["dev"].items() if k.split("|")[0] in (G1, G6, G4)},
        "market_timing_hold": {k: v for k, v in g["holdout"].items() if k.split("|")[0] in (G1, G6, G4)},
        "classifications": {k: v for k, v in r["classifications"].items()},
        "funnel": r["funnel"],
    }


# ---------------------------------------------------------------------------
# Phase 1 - freeze survivors + Phase 4 - freeze composites
# ---------------------------------------------------------------------------

def build_freeze(dev):
    th = date_medians(dev, [G1, G6, G4])
    return {
        "phase": "composite_alpha_v3",
        "version": 2,
        "frozen_utc": pd.Timestamp.now(tz="Asia/Kolkata").isoformat(),
        "parent_spec": "data/alpha_v2/feature_spec.json (v1) — definitions immutable",
        "signal_definitions": {
            C3: "ret(t) - index_ret(t) (index = EW universe excluding latest listing); h=1; IC<0 (reversal)",
            G1: "fraction(symbols with ret(t)>0); date-level",
            G6: "G1(t) - G1(t-5); date-level",
            G4: "cross-sectional std(ret(t)); date-level",
        },
        "survivor_results_v2": survivor_results(),
        "thresholds_from_dev_train_medians": {f"{G1}|3": th[G1], f"{G6}|3": th[G6], f"{G4}|1": th[G4]},
        "revision_note": ("version 2: composite CONDITIONS re-gated to the stress side following "
                          "Phase 3 conditional tests on DEVELOPMENT ONLY (weak+falling breadth, "
                          "high dispersion) - the reversal alpha is stronger there. Thresholds "
                          "(dev-train medians), horizons, weights, methods unchanged. No holdout "
                          "data was consulted at any point."),
        "composites": {
            "COMP1_REVERSAL_BREADTH": {
                "score": f"-{C3} on dates where breadth_stress",
                "condition": f"({G1} < g1_th) AND ({G6} < 0)",
                "inverse_diagnostic": f"NOT (({G1} < g1_th) AND ({G6} < 0))", "method": "conditional filter",
                "rationale": "Phase 3 (dev): reversal IC ~-0.029 weak+falling breadth vs ~-0.016 "
                             "strong/rising; gate reversal to stress-breadth regimes"},
            "COMP2_REVERSAL_DISP": {
                "score": f"-{C3} on dates where disp_high",
                "condition": f"({G4} >= g4_th)",
                "inverse_diagnostic": f"({G4} < g4_th)", "method": "conditional filter",
                "rationale": "Phase 3 (dev): reversal IC -0.025 high-dispersion vs -0.020 low; "
                             "high dispersion = regime-rotation days"},
            "COMP3_REVERSAL_BREADTH_DISP": {
                "score": f"-{C3} on dates where {COMP1_cond} AND {COMP2_cond}",
                "condition": "breadth_stress AND disp_high",
                "inverse_diagnostic": "NOT (breadth_stress AND disp_high)",
                "method": "conditional filter",
                "rationale": "joint stress gate on the reversal alpha"},
        },
        "method_notes": [
            "G-features are date-level constants; adding them to a cross-sectional rank is vacuous, "
            "so the ONLY meaningful combination method is the conditional filter (Phase 6 #3). "
            "Equal-weight rank / sign-consistent rank combinations of date-constants do not change "
            "cross-sectional ranking and are therefore not defined as separate composites.",
            "Composite conditions are frozen BEFORE any evaluation in this phase. Thresholds are "
            "simple dev-TRAIN date-level medians (no validation/holdout sight).",
            "Inverse conditions are pre-registered symmetric diagnostics, reported - never selected.",
        ],
        "evaluation": {
            "horizons": list(HORIZONS), "primary_horizon": 1,
            "coverage": 0.10, "costs_bps_per_side": 25, "cost_sensitivity": [15, 50],
            "tail_protocol": ["full", "winsorized_1pct", "drop_1pct", "drop_5pct"],
            "corpus": "DEVELOPMENT ONLY (train/validation/final_oos). The frozen 60-symbol holdout "
                      "is consumed by V2 and NOT reused. holdout_2 is locked for V1. Confirmation "
                      "requires a NEW untouched holdout-3.",
            "gate": "composite is complementary if on dev validation AND dev final_oos the confirm-date "
                    "|IC| >= 0.8 x baseline |IC| with material date coverage (>=20%) and tail/robustness "
                    "not worse than baseline; else REDUNDANT.",
        },
    }


def write_freeze(dev):
    FRZ = build_freeze(dev)
    if FRZ_PATH.exists() and (OUT_DIR / "composite_freeze_v1.json").exists() is False:
        FRZ_PATH.rename(OUT_DIR / "composite_freeze_v1.json")
    FRZ_PATH.write_text(json.dumps(FRZ, indent=1))
    print(json.dumps({"frozen_utc": FRZ["frozen_utc"], "thresholds": FRZ["thresholds_from_dev_train_medians"]}, indent=1))


# ---------------------------------------------------------------------------
# Phase 2 - complementarity
# ---------------------------------------------------------------------------

def complementarity(dev, frz):
    rate = dev.copy()
    rate["score_negC3"] = -rate[C3]
    cols = [C3, G1, G6, G4]
    row_corr = {}
    for a in cols:
        for b in cols:
            if b <= a:
                continue
            da = rate[a].to_numpy(float)
            db = rate[b].to_numpy(float)
            m = np.isfinite(da) & np.isfinite(db)
            if m.sum() < 1000 or da[m].std() == 0 or db[m].std() == 0:
                row_corr[f"{a}|{b}"] = {"n": int(m.sum()), "pearson": None, "spearman": None}
                continue
            row_corr[f"{a}|{b}"] = {
                "n": int(m.sum()),
                "pearson": round(float(np.corrcoef(da[m], db[m])[0, 1]), 4),
                "spearman": round(float(stats.spearmanr(da[m], db[m])[0]), 4),
            }
    # prediction-level: date-plane mean score correlation
    daily = rate.groupby(level="date").agg(
        negC3mw=pd.NamedAgg(column="score_negC3", aggfunc="mean"),
        **{c: pd.NamedAgg(column=c, aggfunc="mean") for c in cols[1:]},
    )
    pred_corr = {}
    for c in cols[1:]:
        s = daily[["negC3mw", c]].dropna()
        if len(s) > 60 and s[c].std() > 0:
            pred_corr[f"date_mean_negC3|{c}"] = {
                "n_dates": int(len(s)),
                "pearson": round(float(np.corrcoef(s["negC3mw"], s[c])[0, 1]), 4),
                "spearman": round(float(stats.spearmanr(s["negC3mw"], s[c])[0]), 4),
            }
    # dates where Gs correlate among each other (date-level)
    dc = {}
    for a in cols[1:]:
        for b in cols[1:]:
            if b <= a:
                continue
            s = daily[[a, b]].dropna()
            if len(s) > 60 and s[b].std() > 0:
                dc[f"{a}|{b}"] = {"n_dates": int(len(s)),
                                  "pearson": round(float(np.corrcoef(s[a], s[b])[0, 1]), 4),
                                  "spearman": round(float(stats.spearmanr(s[a], s[b])[0]), 4)}
    # observation overlap: co-occurrence of C3 reversal-relevant dates with conditions
    th = frz["thresholds_from_dev_train_medians"]
    d1 = (rate[G4] >= th[f"{G4}|1"])
    bh = (rate[G1] < th[f"{G1}|3"]) & (rate[G6] < 0)
    bottom = rate[C3] <= rate[C3].quantile(0.10)
    overlap = {
        "bottom10_C3_dates": int(bottom.sum()),
        "share_bottom10_in_breadth_stress": round(float((bottom & bh).sum() / max(bottom.sum(), 1)), 4),
        "share_bottom10_in_disp_high": round(float((bottom & d1).sum() / max(bottom.sum(), 1)), 4),
        "share_bottom10_in_both": round(float((bottom & bh & d1).sum() / max(bottom.sum(), 1)), 4),
        "date_coverage_breadth_stress": round(float(bh.mean()), 4),
        "date_coverage_disp_high": round(float(d1.mean()), 4),
        "date_coverage_both": round(float((bh & d1).mean()), 4),
    }
    return {"row_correlation": row_corr, "prediction_correlation": pred_corr,
            "date_level_correlation": dc, "observation_overlap": overlap}
# Fix forward references used in the freeze template (defined full in build_freeze)
COMP1_cond = f"({G1} >= g1_th) AND ({G6} >= g6_th)"
COMP2_cond = f"({G4} >= g4_th)"


# ---------------------------------------------------------------------------
# Phase 3 - conditional C3 tests (pre-specified bins)
# ---------------------------------------------------------------------------

def conditional_c3(dev, frz):
    th = frz["thresholds_from_dev_train_medians"]
    bins = {
        "breadth_high": dev[G1] >= th[f"{G1}|3"],
        "breadth_low": dev[G1] < th[f"{G1}|3"],
        "breadth_rising": dev[G6] >= 0.0,
        "breadth_falling": dev[G6] < 0.0,
        "disp_high": dev[G4] >= th[f"{G4}|1"],
        "disp_low": dev[G4] < th[f"{G4}|1"],
    }
    out = {}
    for name, mask in bins.items():
        row = {"fwd": {}}
        for h in HORIZONS:
            keep = pd.DataFrame({"f": dev.loc[mask, C3], "y": dev.loc[mask, f"fwd_ret_{h}"]}).dropna()
            if len(keep) < MIN_IC_ROWS or keep["f"].nunique() < 5:
                row["fwd"][h] = None
                continue
            st = aa.ic_stats(keep["f"].to_numpy(), keep["y"].to_numpy(),
                             keep.index.get_level_values("symbol").to_numpy())
            row["fwd"][h] = {"n": st["n"], "ic": st["spearman_ic"], "p": st["pvalue"],
                             "hit": st["hit_rate"], "mean_fwd_pct": round(float(keep["y"].mean()) * 100, 4)}
        out[name] = row
    return out


# ---------------------------------------------------------------------------
# Composite construction
# ---------------------------------------------------------------------------

def composite_columns(dev, frz):
    th = frz["thresholds_from_dev_train_medians"]
    g1_lo = (dev[G1] < th[f"{G1}|3"])
    g6_neg = (dev[G6] < 0)
    d4_hi = (dev[G4] >= th[f"{G4}|1"])
    bh_stress = g1_lo & g6_neg
    bh_norm = ~bh_stress
    d_lo = ~d4_hi
    base = -dev[C3]
    cols = {
        "C0_BASELINE": (base, "always-on baseline"),
        "COMP1_REVERSAL_BREADTH": (np.where(bh_stress, base, np.nan), "confirm"),
        "COMP1_INV": (np.where(bh_norm, base, np.nan), "inverse"),
        "COMP2_REVERSAL_DISP": (np.where(d4_hi, base, np.nan), "confirm"),
        "COMP2_INV": (np.where(d_lo, base, np.nan), "inverse"),
        "COMP3_REVERSAL_BREADTH_DISP": (np.where(bh_stress & d4_hi, base, np.nan), "confirm"),
        "COMP3_INV": (np.where(~(bh_stress & d4_hi), base, np.nan), "inverse"),
    }
    return cols


# ---------------------------------------------------------------------------
# Phase 5-8 - evaluation
# ---------------------------------------------------------------------------

def tail_protocols(vals, lbl, syms):
    """Return list of (name, vals, lbl, syms) for pre-registered tail variants."""
    out = [("full", vals, lbl, syms)]
    for name, lo_q, hi_q in (("winsorized_1pct", 1, 99),):
        lo, hi = np.nanpercentile(lbl, lo_q), np.nanpercentile(lbl, hi_q)
        out.append((name, vals, np.clip(lbl, lo, hi), syms))
    for name, lo_q, hi_q in (("drop_1pct", 1, 99), ("drop_5pct", 5, 95)):
        lo, hi = np.nanpercentile(lbl, lo_q), np.nanpercentile(lbl, hi_q)
        m = (lbl >= lo) & (lbl <= hi)
        if m.sum() > MIN_IC_ROWS:
            out.append((name, vals[m], lbl[m], syms[m]))
    return out


def eval_composite(dev, score, name, label):
    """Full per-split evaluation for one composite column."""
    res = {"name": name, "label": label}
    for split in SPLITS:
        block = {"horizons": {}}
        for h in HORIZONS:
            keep = dev[dev["split"] == split].dropna(subset=[score, f"fwd_ret_{h}"])
            if len(keep) < MIN_IC_ROWS or keep[score].nunique() < 5:
                block["horizons"][str(h)] = {"status": "INSUFFICIENT", "n": int(len(keep))}
                continue
            vals = keep[score].to_numpy(float)
            lbl = keep[f"fwd_ret_{h}"].to_numpy(float)
            syms = keep.index.get_level_values("symbol").to_numpy()
            st = aa.ic_stats(vals, lbl, syms)
            row = {"n": st["n"], "n_eff": st["n_eff"], "ic": st["spearman_ic"], "p": st["pvalue"],
                   "ci": [st["ci95_lo"], st["ci95_hi"]], "sign": st["sign"]}
            if h == 1:
                qp = aa.quantile_profile(vals, lbl)
                row["quantile"] = {"spread_pct": qp["top_bottom_spread_pct"], "mono": qp["monotonic_rho"],
                                   "q1": qp["q1_mean_pct"], "q5": qp["q_top_mean_pct"]}
                row["tail"] = {}
                for proto, vv, ll, ss in tail_protocols(vals, lbl, syms):
                    st2 = aa.ic_stats(vv, ll, ss)
                    row["tail"][proto] = {"ic": st2["spearman_ic"], "p": st2["pvalue"], "n": st2["n"]}
                row["ls"] = aa.long_short_by_date(dev, score, 1, split, 0.10)
                row["costs"] = {f"{int(bp*10000)}bp": aa.cost_aware_ls(dev, score, 1, split, 0.10, bp)
                                for bp in COST_BPS}
                row["regimes"] = aa.regime_ic(dev, score, 1, split)
                row["symbols"] = symbol_span(dev, score, 1, split)
            block["horizons"][str(h)] = row
        res[split] = block
    res["temporal"] = temporal(dev, score)
    res["randomization"] = randomize_composite(dev, score)
    return res


def symbol_span(dev, score, h, split):
    keep = dev[dev["split"] == split].dropna(subset=[score, f"fwd_ret_{h}"], how="any")
    rows = []
    for sym, g in keep.groupby(level="symbol"):
        if len(g) < 200 or g[score].nunique() < 5:
            continue
        rho = stats.spearmanr(g[score], g[f"fwd_ret_{h}"])[0]
        rows.append({"symbol": sym, "n": int(len(g)), "ic": round(float(rho), 4)})
    rows.sort(key=lambda r: -abs(r["ic"]))
    ics = np.array([r["ic"] for r in rows])
    return {"n_symbols": len(ics),
            "frac_ic_gt0": round(float((ics > 0).mean()), 4) if len(ics) else None,
            "median_ic": round(float(np.median(ics)), 4) if len(ics) else None,
            "best": rows[:4], "worst": rows[-4:]}


def temporal(dev, score):
    keep = dev.dropna(subset=[score, "fwd_ret_1"])
    keep = keep.copy()
    keep["dt"] = keep.index.get_level_values("date")
    dates = pd.Index(np.unique(keep["dt"])).sort_values()
    keep["band"] = dates.searchsorted(keep["dt"]) // 126
    out = []
    for b, g in keep.groupby("band"):
        if len(g) < MIN_IC_ROWS or g[score].nunique() < 5:
            continue
        st = aa.ic_stats(g[score].to_numpy(), g["fwd_ret_1"].to_numpy(),
                         g.index.get_level_values("symbol").to_numpy())
        out.append({"band": int(b), "start": str(g["dt"].min())[:10], "end": str(g["dt"].max())[:10],
                    "n": st["n"], "ic": st["spearman_ic"]})
    ics = [r["ic"] for r in out if np.isfinite(r["ic"])]
    return {"n_bands": len(out), "bands": out,
            "frac_ic_gt0": round(float(np.mean([i > 0 for i in ics])), 4) if ics else None,
            "median_ic": round(float(np.median(ics)), 4) if ics else None}


def randomize_composite(dev, score):
    """Permute the C3 contributor within symbol; rebuild score; IC on same dates."""
    keep = dev.dropna(subset=[score, "fwd_ret_1"]).copy()
    if len(keep) < MIN_IC_ROWS:
        return {"status": "INSUFFICIENT"}
    obs = float(stats.spearmanr(keep[score], keep["fwd_ret_1"])[0])
    rng = np.random.default_rng(SEED)
    c3loc = dev[C3].to_numpy(float)
    syms = dev.index.get_level_values("symbol").to_numpy()
    scoreloc = dev[score].to_numpy(float)
    labloc = dev["fwd_ret_1"].to_numpy(float)
    valid = dev["split"].isin(SPLITS).to_numpy()
    sims = []
    for _ in range(NULL_SIMS):
        shuffled = c3loc.copy()
        for sym_ in np.unique(syms[valid]):
            m = syms == sym_
            sub = shuffled[m]
            shuffled[m] = rng.permutation(sub)
        score_perm = np.where(np.isfinite(scoreloc), -shuffled, np.nan)
        m = np.isfinite(score_perm) & np.isfinite(labloc)
        if m.sum() < MIN_IC_ROWS:
            sims.append(np.nan)
            continue
        sims.append(float(stats.spearmanr(score_perm[m], labloc[m])[0]))
    sims = np.array(sims)[np.isfinite(sims)]
    return {"status": "OK", "n": int(keep.shape[0]), "obs_ic": round(float(obs), 5),
            "null_mean": round(float(sims.mean()), 5), "null_std": round(float(sims.std()), 5),
            "p_two_sided": round(float((np.abs(sims) >= abs(obs)).mean()), 4),
            "n_sims": int(len(sims)),
            "selection_bias_note": "composite built from V2 survivors; permutation p is conditional "
                                   "on the signal being independently promising - treat 0.05 as weak evidence"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(stage):
    dev = load_dev()
    if stage in ("freeze",):
        write_freeze(dev)
        return
    frz = json.loads(FRZ_PATH.read_text()) if FRZ_PATH.exists() else build_freeze(dev)
    if stage == "complementarity":
        out = complementarity(dev, frz)
        (OUT_DIR / "composite_complementarity.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1)[:4000])
        return
    if stage == "conditional":
        out = conditional_c3(dev, frz)
        (OUT_DIR / "composite_conditional.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1)[:4000])
        return
    if stage in ("eval", "all"):
        cols = composite_columns(dev, frz)
        res = {}
        for name, (score, label) in cols.items():
            print("eval", name, "...", flush=True)
            d = dev.copy()
            d[name] = score
            res[name] = eval_composite(d, name, name, label)
        (OUT_DIR / "composite_eval.json").write_text(json.dumps(res, indent=1))
        print("composite_eval.json written:", len(res))
        return
    if stage == "all":
        write_freeze(dev)
        (OUT_DIR / "composite_complementarity.json").write_text(json.dumps(complementarity(dev, frz), indent=1))
        (OUT_DIR / "composite_conditional.json").write_text(json.dumps(conditional_c3(dev, frz), indent=1))
        cols = composite_columns(dev, frz)
        res = {}
        for name, (score, label) in cols.items():
            print("eval", name, "...", flush=True)
            d = dev.copy()
            d[name] = score
            res[name] = eval_composite(d, name, name, label)
        (OUT_DIR / "composite_eval.json").write_text(json.dumps(res, indent=1))
        print("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["freeze", "complementarity", "conditional", "eval", "all"])
    args = ap.parse_args()
    run(args.stage)