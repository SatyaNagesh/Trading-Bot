"""Alpha Research V2 — Pre-registered feature families (Phase 2/3).

Single source of truth for the V2 hypothesis set:
  * families A..H (market structure & cross-sectional effects),
  * exact causal formulas, lookbacks, required columns, timestamp,
    expected interpretation, forward horizons, exclusion rules.

NOTHING in this module consults any holdout. Feature values only.

The spec can be frozen to disk (feature_spec.json) and rendered to a
pre-registration markdown artifact. --build caches per-universe panels with
the V2 feature columns attached (data/alpha_v2/<name>_v2_panel.parquet).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from packages.research.vt_signal import SECTOR, sector_of  # static public labels

TZ = "Asia/Kolkata"
MIN_CS = 20          # minimum symbols per date for cross-sectional features
MIN_SECTOR = 3       # minimum same-sector members for sector-relative features
PANELS = {
    "development": ("data/historical/alpha_panel_dev.parquet", "data/historical/d1d"),
    "holdout": ("data/holdout/alpha_panel_holdout.parquet", "data/holdout/d1d"),
}

# ---------------------------------------------------------------------------
# Pre-registered hypothesis set (families A..H)
# ---------------------------------------------------------------------------

F = []  # (family, key, formula, lookback, interpretation, horizons)


def reg(family, key, formula, lookback, interpretation, horizons):
    F.append({
        "family": family, "key": key, "formula": formula,
        "lookback": lookback, "interpretation": interpretation,
        "horizons": horizons,
    })


# Family A — RELATIVE STRENGTH (vs market / sector; vol-adjusted)
reg("A_rel_strength", "A1_rs_mkt_10",
    "cumret(10d) - index_cumret(10d)", 10,
    "10-day return of the symbol minus equal-weight universe return; standard relative strength.",
    [1, 3, 5, 10, 20])
reg("A_rel_strength", "A2_rs_mkt_20",
    "cumret(20d) - index_cumret(20d)", 20,
    "20-day relative strength vs market.", [1, 3, 5, 10, 20])
reg("A_rel_strength", "A3_rs_mkt_60",
    "cumret(60d) - index_cumret(60d)", 60,
    "60-day (medium-term) relative strength vs market.", [1, 3, 5, 10, 20])
reg("A_rel_strength", "A4_rs_sector_20",
    "cumret(20d) - sector_mean_cumret(20d)", 20,
    "20-day return relative to same-sector equal-weight mean (>=3 members).",
    [1, 3, 5, 10, 20])
reg("A_rel_strength", "A5_rs_accel_10",
    "A1(t) - A1(t-5)", 15,
    "Acceleration of 10-day relative strength (change over prior 5 days).",
    [1, 3, 5, 10, 20])
reg("A_rel_strength", "A6_rs_voladj_20",
    "(cumret(20d) - index_cumret(20d)) / rv20", 20,
    "Volatility-adjusted relative strength (Sharpe-style RS).", [1, 3, 5, 10, 20])

# Family B — CROSS-SECTIONAL MOMENTUM (complete rank distribution, no assumed sign)
for L in (5, 10, 20, 60):
    reg("B_xs_momentum", f"B{1 if L == 5 else 2 if L == 10 else 3 if L == 20 else 4}_mom_{L}",
        f"date_percentile_rank(cumret({L}d))", L,
        f"Cross-sectional percentile rank of {L}d historical return at date t.",
        [1, 3, 5, 10, 20])
reg("B_xs_momentum", "B5_mom_voladj_20",
    "date_percentile_rank(cumret(20d)/rv20)", 20,
    "Cross-sectional rank of volatility-adjusted 20d momentum.", [1, 3, 5, 10, 20])

# Family C — SHORT-TERM REVERSAL
reg("C_reversal", "C1_rev_ret1",
    "ret(1d) = close_t/close_{t-1} - 1", 1,
    "1-day return; canonical short-term reversal candidate (expected negative).",
    [1, 3, 5])
reg("C_reversal", "C2_rev_ret2",
    "close_t/close_{t-2} - 1", 2,
    "2-day return; reversal at slightly longer horizon.", [1, 3, 5])
reg("C_reversal", "C3_rev_abn_mkt1",
    "ret(1d) - index_ret(1d)", 1,
    "Abnormal 1-day return vs market; idiosyncratic move reversal.", [1, 3, 5])
reg("C_reversal", "C4_rev_dist_mean20",
    "close_t/SMA(close,20) - 1", 20,
    "Distance from 20-day mean; mean-reversion distance gauge.", [1, 3, 5])
reg("C_reversal", "C5_rev_volshock",
    "ret(1d) x (rv20 / rolling_median(rv20,252))", 252,
    "Overnight/1-day move compounded by a volatility-shock multiplier; does an extreme move on a shock day revert?",
    [1, 3, 5])

# Family D — GAP / OPEN EFFECTS (overnight vs intraday separated)
reg("D_gap", "D1_gap_overnight",
    "open_t/close_{t-1} - 1", 1,
    "Overnight return (close->open).", [1, 3])
reg("D_gap", "D2_gap_intraday",
    "close_t/open_t - 1", 1,
    "Intraday return (open->close); isolates where any gap effect lives.", [1, 3])
reg("D_gap", "D3_gap_mag_atr",
    "abs(open_t - close_{t-1}) / ATR(14)", 14,
    "Gap magnitude scaled by recent true-range; big-gap fill hypothesis.", [1, 3])
reg("D_gap", "D4_gap_dir_trend",
    "sign(open_t - close_{t-1}) x sign(close_{t-1}-close_{t-6})", 6,
    "Gap direction vs prior 5-day trend aligned(+1)/against(-1)/zero.", [1, 3])
reg("D_gap", "D5_gap_vol_conf",
    "D1_gap_overnight x volume_t/SMA(volume,20)", 20,
    "Overnight gap with volume confirmation.", [1, 3])

# Family E — BREAKOUT PERSISTENCE (measure first, no rule)
reg("E_breakout", "E1_dist_high20",
    "close_t/rolling_max(high,20) - 1", 20,
    "Distance below recent 20d high (<=0); breakout proximity.", [1, 3, 5, 10, 20])
reg("E_breakout", "E2_dist_low20",
    "close_t/rolling_min(low,20) - 1", 20,
    "Distance above recent 20d low (>=0); breakdown proximity.", [1, 3, 5, 10, 20])
reg("E_breakout", "E3_break_mag20",
    "rolling_max(high,20)/rolling_max(high,60) - 1", 60,
    "Magnitude of the recent 20d excursion vs prior 60d span.", [1, 3, 5, 10, 20])
reg("E_breakout", "E4_break_vol_exp",
    "(close_t >= rolling_max(high,20).shift(1)) x volume_t/SMA(volume,20)", 20,
    "New-20d-high day indicator weighted by relative volume (volume-confirmed breakout).",
    [1, 3, 5, 10, 20])
reg("E_breakout", "E5_break_cont5",
    "rolling_mean(break_new20, 5)", 20,
    "Fraction of last 5 days that printed a new 20d high (breakout frequency).",
    [1, 3, 5, 10, 20])

# Family F — VOLUME / PRICE INTERACTION (no repeat of vol_trend_10v50)
reg("F_volume_price", "F1_vol_rel20",
    "volume_t/SMA(volume,20)", 20,
    "Relative volume; spike/quiet gauge.", [1, 3, 5])
reg("F_volume_price", "F2_vol_accel",
    "SMA(volume,5)/SMA(volume,25) - 1", 25,
    "Short volume acceleration (distinct from the failed vol_trend_10v50).", [1, 3, 5])
reg("F_volume_price", "F3_px_vol_int",
    "cumret(20d) x volume_t/SMA(volume,20)", 20,
    "Price x volume interaction at date t (trend x participation).", [1, 3, 5])
reg("F_volume_price", "F4_abn_vol_ret",
    "sign(ret(1d)) x volume_t/SMA(volume,20)", 20,
    "Abnormal volume paired with the sign of today's return.", [1, 3, 5])
reg("F_volume_price", "F5_vol_conf_mom",
    "B3_mom_20 x volume_t/SMA(volume,20)", 20,
    "Volume-confirmed cross-sectional momentum (rank x relative volume).", [1, 3, 5])

# Family G — MARKET BREADTH / DISPERSION (date-level; market-timing tests)
for k, formula, lb, interp in (
    ("G1_breadth_rise", "fraction(symbols with ret(1d) > 0)", 1,
     "Cross-sectional fraction of risers at date t."),
    ("G2_breadth_ma20", "fraction(close_t > SMA(close,20))", 20,
     "Fraction of symbols above their 20-day mean."),
    ("G3_breadth_ma50", "fraction(close_t > SMA(close,50))", 50,
     "Fraction of symbols above their 50-day mean."),
    ("G4_xs_ret_disp", "cross-sectional std(ret(1d))", 1,
     "Cross-sectional return dispersion (breadth of moves)."),
    ("G5_xs_vol_disp", "cross-sectional std(log1p(rv20))", 20,
     "Cross-sectional realized-volatility dispersion."),
    ("G6_breadth_mom5", "G1(t) - G1(t-5)", 5,
     "Breadth momentum: change in the rise-fraction over 5 days."),
):
    reg("G_breadth_dispersion", k, formula, lb, interp, [1, 3, 5])

# Family H — VOLATILITY STRUCTURE (expansion/contraction ratios; distinct from vol_rel20)
reg("H_vol_structure", "H1_vol_exp5",
    "rv20_t/rv20_{t-5} - 1", 25,
    "Volatility expansion rate over 5 days.", [1, 3, 5, 10, 20])
reg("H_vol_structure", "H2_vol_cont20",
    "rv20_t/rv20_{t-20} - 1", 40,
    "Volatility change over 20 days (negative = contraction).", [1, 3, 5, 10, 20])
reg("H_vol_structure", "H3_rv_ratio_10_60",
    "rv10/rv60 - 1", 60,
    "Short/long realized-vol ratio (vol term-structure tilt).", [1, 3, 5, 10, 20])
reg("H_vol_structure", "H4_vol_shock",
    "rv20/rolling_median(rv20,252) - 1", 252,
    "Realized-vol shock vs trailing median.", [1, 3, 5, 10, 20])
reg("H_vol_structure", "H5_vol_vs_mkt",
    "log1p(rv20) - date_mean(log1p(rv20))", 20,
    "Idiosyncratic (market-demeaned) log volatility level.", [1, 3, 5, 10, 20])
reg("H_vol_structure", "H6_xs_vol_rank",
    "date_percentile_rank(rv20)", 20,
    "Cross-sectional rank of realized volatility.", [1, 3, 5, 10, 20])

# family metadata in fixed ordering, matching the phase TOC
FAMILIES = [
    "A_rel_strength", "B_xs_momentum", "C_reversal", "D_gap",
    "E_breakout", "F_volume_price", "G_breadth_dispersion", "H_vol_structure",
]

SPEC = {
    "phase": "alpha_research_v2",
    "version": 1,
    "frozen_utc": None,  # set at write time
    "principle": ("Hypothesis families pre-registered before any OOS evaluation; "
                  "definitions immutable after freeze; two-sided tests; "
                  "no selection on any holdout."),
    "cost_assumptions": {
        "primary_cost_per_side_bps": 25.0,
        "stress_cost_per_side_bps": 50.0,
        "sensitivity_cost_per_side_bps": 15.0,
    },
    "selection_gate": {
        # multiple-testing across ALL (feature, horizon) hypotheses on development-VALIDATION
        "bh_fdr_q": 0.10,
        "require_dev_validation_q_le": 0.10,
        "require_dev_final_oos_sign_replication": True,
        "require_dev_final_oos_ic_ge_frac_of_validation_ic": 0.4,
    },
    "confirmation": {
        "corpus": "ANY future confirmation requires a GENUINELY UNTOUCHED corpus "
                  "(holdout_3 or later); the frozen 60-symbol holdout is consumed and "
                  "NOT confirmatory; holdout_2 is reserved for V1 transform confirmation "
                  "and NOT reused here.",
        "policy_if_no_new_data": "DO NOT CLAIM CONFIRMATION; classify as PROMISING-NEEDS-NEW-HOLDOUT.",
    },
    "universe_rules": {
        "development": "49 symbols (frozen alpha_panel_dev)",
        "holdout": "60 symbols (frozen alpha_panel_holdout), pre-2014 rows excluded (split=='')",
        "min_symbols_per_date_cross_section": MIN_CS,
        "min_sector_members": MIN_SECTOR,
    },
    "families": FAMILIES,
    "features": F,
    "exclusion_rules": [
        "warm-up NaNs (lookback not yet satisfied) are excluded per feature",
        "cross-sectional ranks are computed only on dates with >= MIN_CS valid symbols",
        "sector-relative features require >= MIN_SECTOR same-sector members at t",
        "forward labels are the frozen fwd_ret_{h} (strictly future) fields",
        "split filters are applied AFTER feature computation (full-history lookbacks)",
    ],
}

HORIZON_KEY = {1: "1", 3: "3", 5: "5", 10: "10", 20: "20"}
KEYS = [f["key"] for f in F]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

CARRY = ["split", "regime_bucket",
         *[f"fwd_ret_{h}" for h in (1, 3, 5, 10, 20)],
         "mom_roc20", "trend_sma20_gap", "trend_strength_20v50",
         "vol_realized20", "vol_pctile_252", "vol_atr_pct",
         "mkt_ret_5d", "mkt_vol_20", "xs_mom_rank20", "xs_rel_str20"]


def build_v2_panel(name: str) -> pd.DataFrame:
    """Assemble the V2 feature panel WITHOUT any large MultiIndex join.

    Per symbol: raw OHLCV + the corresponding frozen-panel slice are combined
    so peak memory stays ~ (panel size + per-symbol working set). All V2
    signal columns are causal; fwd/split/regime/exposure columns are carried
    over from the frozen panel untouched.
    """
    panel_path, d1d_dir = PANELS[name]
    raw_feat = [(p.stem, pd.read_parquet(p, columns=["open", "high", "low", "close", "volume"]))
                for p in sorted(Path(d1d_dir).glob("*.parquet"))]
    panel = pd.read_parquet(panel_path)

    frames = []
    for sym, raw in raw_feat:
        comp = _per_symbol_components(raw, panel.loc[sym] if sym in panel.index.get_level_values("symbol") else None)
        comp = comp.set_index(pd.MultiIndex.from_arrays(
            [np.full(len(comp), sym), comp.index]), append=False)
        comp.index.names = ["symbol", "date"]
        frames.append(comp)
    del panel
    comp = pd.concat(frames)
    comp.index.names = ["symbol", "date"]
    comp = comp.sort_index()
    return comp


def _per_symbol_components(raw: pd.DataFrame, panel_slice: pd.DataFrame | None) -> pd.DataFrame:
    c, o, h, lo, v = (raw[c] for c in ("close", "open", "high", "low", "volume"))
    ret = c.pct_change()
    rmhi20 = h.rolling(20).max()
    out = pd.DataFrame(index=raw.index)
    out["close"] = c
    out["ret"] = ret
    out["pc"] = c.shift(1)
    for L in (2, 5, 10, 20, 60):
        out[f"rcum{L}"] = c.pct_change(L)
    for w in (5, 10, 20, 60):
        out[f"rv{w}"] = ret.rolling(w).std()
    out["rvmed252"] = out["rv20"].rolling(252).median()
    out["s20"] = c.rolling(20).mean()
    out["s50"] = c.rolling(50).mean()
    out["volrel20"] = v / v.rolling(20).mean()
    out["vols5"] = v.rolling(5).mean()
    out["vols25"] = v.rolling(25).mean()
    tr = pd.concat([h - lo, (h - out["pc"]).abs(), (lo - out["pc"]).abs()],
                   axis=1).max(axis=1)
    out["atr14"] = tr.rolling(14).mean()
    out["break_new20"] = ((c >= rmhi20.shift(1)) & rmhi20.shift(1).notna()).astype(float)
    out["rmhi20"] = rmhi20
    out["rmhi60"] = h.rolling(60).max()
    out["rmlo20"] = lo.rolling(20).min()
    out["gap_overnight"] = o / out["pc"] - 1
    out["gap_intraday"] = c / o - 1
    out["gap_mag_atr"] = (o - out["pc"]).abs() / out["atr14"].replace(0, np.nan)
    out["gap_dir_trend"] = np.sign(o - out["pc"]) * np.sign(out["pc"] - out["pc"].shift(5))
    out["break_cont5"] = out["break_new20"].rolling(5).mean()
    if panel_slice is not None:
        for col in CARRY:
            if col in panel_slice.columns:
                out[col] = panel_slice[col].reindex(out.index)
    return out


def compute_v2_features(comp: pd.DataFrame) -> pd.DataFrame:
    """Derive all pre-registered V2 feature columns from the component frame."""
    d = comp.index.get_level_values("date")

    # ---- index (equal-weight level, causal): EW of pct-change, exclude latest-listing symbol ----
    close_pivot = comp["close"].unstack("symbol")
    starts = close_pivot.notna().idxmax()
    full = [s for s in close_pivot.columns if starts[s] != starts.max()]
    idx_ret = close_pivot[full].pct_change().mean(axis=1).fillna(0.0)
    idx_level = (1.0 + idx_ret).cumprod()

    out = pd.DataFrame(index=comp.index)
    idx_rcum = {L: idx_level.pct_change(L) for L in (10, 20, 60)}
    for key, L in (("A1_rs_mkt_10", 10), ("A2_rs_mkt_20", 20), ("A3_rs_mkt_60", 60)):
        out[key] = comp[f"rcum{L}"].to_numpy() - d.map(idx_rcum[L]).to_numpy()
    sec = comp.index.get_level_values("symbol").map(sector_of)
    gkey = [d, sec]
    sec_mean20 = comp["rcum20"].groupby(gkey).transform("mean")
    nsector = comp["rcum20"].groupby(gkey).transform("size")
    out["A4_rs_sector_20"] = np.where(nsector >= MIN_SECTOR,
                                      comp["rcum20"].to_numpy() - sec_mean20, np.nan)
    out["A5_rs_accel_10"] = out["A1_rs_mkt_10"] - out["A1_rs_mkt_10"].groupby(level="symbol").shift(5)
    out["A6_rs_voladj_20"] = (comp["rcum20"].to_numpy() - d.map(idx_rcum[20]).to_numpy()) / \
        comp["rv20"].replace(0, np.nan)

    for L, key in ((5, "B1_mom_5"), (10, "B2_mom_10"), (20, "B3_mom_20"), (60, "B4_mom_60")):
        out[key] = comp[f"rcum{L}"].groupby(level="date").rank(pct=True, method="average")
    out["B5_mom_voladj_20"] = (comp["rcum20"] / comp["rv20"].replace(0, np.nan)) \
        .groupby(level="date").rank(pct=True, method="average")

    out["C1_rev_ret1"] = comp["ret"]
    out["C2_rev_ret2"] = comp["rcum2"]
    out["C3_rev_abn_mkt1"] = comp["ret"].to_numpy() - d.map(idx_ret).to_numpy()
    out["C4_rev_dist_mean20"] = comp["close"] / comp["s20"] - 1
    out["C5_rev_volshock"] = comp["ret"] * (comp["rv20"] / comp["rvmed252"].replace(0, np.nan) - 1)

    out["D1_gap_overnight"] = comp["gap_overnight"]
    out["D2_gap_intraday"] = comp["gap_intraday"]
    out["D3_gap_mag_atr"] = comp["gap_mag_atr"]
    out["D4_gap_dir_trend"] = comp["gap_dir_trend"]
    out["D5_gap_vol_conf"] = comp["gap_overnight"] * comp["volrel20"]

    out["E1_dist_high20"] = comp["close"] / comp["rmhi20"] - 1
    out["E2_dist_low20"] = comp["close"] / comp["rmlo20"] - 1
    out["E3_break_mag20"] = comp["rmhi20"] / comp["rmhi60"] - 1
    out["E4_break_vol_exp"] = comp["break_new20"] * comp["volrel20"]
    out["E5_break_cont5"] = comp["break_cont5"]

    out["F1_vol_rel20"] = comp["volrel20"]
    out["F2_vol_accel"] = comp["vols5"] / comp["vols25"] - 1
    out["F3_px_vol_int"] = comp["rcum20"] * comp["volrel20"]
    out["F4_abn_vol_ret"] = np.sign(comp["ret"]) * comp["volrel20"]
    out["F5_vol_conf_mom"] = out["B3_mom_20"] * comp["volrel20"]

    out["H1_vol_exp5"] = comp["rv20"] / comp["rv20"].groupby(level="symbol").shift(5) - 1
    out["H2_vol_cont20"] = comp["rv20"] / comp["rv20"].groupby(level="symbol").shift(20) - 1
    out["H3_rv_ratio_10_60"] = comp["rv10"] / comp["rv60"].replace(0, np.nan) - 1
    out["H4_vol_shock"] = comp["rv20"] / comp["rvmed252"].replace(0, np.nan) - 1
    out["H5_vol_vs_mkt"] = np.log1p(comp["rv20"]) - \
        np.log1p(comp["rv20"]).groupby(level="date").transform("mean")
    out["H6_xs_vol_rank"] = comp["rv20"].groupby(level="date").rank(pct=True, method="average")

    # ---- breadth / dispersion (date level) ----
    g_rise = (comp["ret"] > 0).groupby(level="date").mean()
    g_ma20 = (comp["close"] > comp["s20"]).groupby(level="date").mean()
    g_ma50 = (comp["close"] > comp["s50"]).groupby(level="date").mean()
    g_disp = comp["ret"].groupby(level="date").std()
    g_vdisp = np.log1p(comp["rv20"]).groupby(level="date").std()
    g_bmom = g_rise - g_rise.shift(5)
    for key, ser in (("G1_breadth_rise", g_rise), ("G2_breadth_ma20", g_ma20),
                     ("G3_breadth_ma50", g_ma50), ("G4_xs_ret_disp", g_disp),
                     ("G5_xs_vol_disp", g_vdisp), ("G6_breadth_mom5", g_bmom)):
        out[key] = d.map(ser).to_numpy()

    # coverage guard for cross-sectional features (dates with < MIN_CS symbols)
    n = comp.groupby(level="date").size()
    bad_dates = n[n < MIN_CS].index
    guarded = [k for k in out.columns if k.startswith(("B", "G", "H5", "H6")) or
               k in ("A4_rs_sector_20", "F5_vol_conf_mom")]
    out.loc[d.isin(bad_dates), guarded] = np.nan

    out = out.loc[:, [c for c in out.columns if c in KEYS]]
    for col in CARRY:
        if col in comp.columns:
            out[col] = comp[col]
    return out


def write_spec(path: Path, prereg_md: Path | None = None):
    spec = {**SPEC, "frozen_utc": pd.Timestamp.now(tz=TZ).isoformat()}
    spec["n_features"] = len(F)
    spec["n_hypotheses"] = sum(len(f["horizons"]) for f in F)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2))
    if prereg_md:
        t = spec["frozen_utc"]
        lines = [f"# Alpha Research V2 — Pre-registration (frozen {t[:10]})", ""]
        lines.append(f"- **Frozen commit:** `{t}`")
        lines.append(f"- **Features:** {len(F)} | **Hypotheses tested:** {spec['n_hypotheses']} "
                     "(feature x horizon pairs)")
        lines.append(f"- **Selection gate:** BH-FDR q<=0.10 across all hypotheses on "
                     "development-VALIDATION + sign replication + |IC_final| >= "
                     f"{spec['selection_gate']['require_dev_final_oos_ic_ge_frac_of_validation_ic']} x |IC_validation| "
                     "on development-FINAL-OOS.")
        lines.append(f"- **Costs:** {spec['cost_assumptions']['primary_cost_per_side_bps']} bps/side "
                     "primary, "
                     f"{spec['cost_assumptions']['stress_cost_per_side_bps']} stress, "
                     f"{spec['cost_assumptions']['sensitivity_cost_per_side_bps']} sensitivity.")
        lines.append(f"- **Confirmation:** {spec['confirmation']['corpus']} "
                     f"{spec['confirmation']['policy_if_no_new_data']}")
        lines.append("")
        for fam in FAMILIES:
            fam_feats = [f for f in F if f["family"] == fam]
            lines.append(f"## Family {fam[0]} — {fam[2:]}")
            lines.append("| key | formula | lookback | interpretation | horizons |")
            lines.append("|---|---|---|---|---|")
            for f in fam_feats:
                lines.append(f"| {f['key']} | {f['formula']} | {f['lookback']} | "
                             f"{f['interpretation']} | {f['horizons']} |")
            lines.append("")
        lines.append("## Exclusion rules")
        for r in spec["exclusion_rules"]:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("> Definition freeze: formulas and horizons were written BEFORE any "
                     "evaluation. They will not be changed after holdout results are seen.")
        prereg_md.parent.mkdir(parents=True, exist_ok=True)
        prereg_md.write_text("\n".join(lines))
    return spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-spec", action="store_true")
    ap.add_argument("--build", action="store_true")
    args = ap.parse_args()
    if args.write_spec:
        spec = write_spec(Path("data/alpha_v2/feature_spec.json"),
                          Path("reports/ALPHA_RESEARCH_V2_PREREG_2026-09.md"))
        print(json.dumps({k: spec[k] for k in ("version", "n_features", "n_hypotheses",
                                               "frozen_utc")}, indent=1))
    if args.build:
        for name in PANELS:
            comp = build_v2_panel(name)
            p2 = compute_v2_features(comp)
            del comp
            out_path = Path(f"data/alpha_v2/{name}_v2_panel.parquet")
            p2.to_parquet(out_path)
            print(f"[{name}] {len(p2)} rows, {p2.shape[1]} cols -> {out_path}")
    sys.exit(0)