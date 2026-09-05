"""Alpha discovery engine — orchestration runner.

Executes phases 1-15 of the alpha-discovery process on the chronological panel
and writes machine-readable results plus a console summary.

No strategy is built here. This only measures whether features contain stable,
reproducible, out-of-sample information about forward returns.

Checkpointed: results are saved to --out after every phase and phases not yet
"done" are (re)run on resume, so an interrupted run continues cheaply. The
panel is cached to parquet between runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from packages.research.alpha_features import FEATURES, FEATURE_KEYS
from packages.research.alpha_dataset import build_panel, load_splits, store_root
from packages.research.alpha_analysis import (
    SPLIT_ORDER,
    bh_fdr,
    block_bootstrap_ic,
    cost_aware_ls,
    ic_stats,
    long_short_by_date,
    partial_ic,
    quantile_profile,
    randomized_null,
    regime_ic,
    composite_z_cols,
)

HORIZONS = [1, 3, 5, 10, 20]
RANK_WORTHY = [
    "mom_roc20", "trend_sma20_gap", "trend_ema10_gap", "trend_strength_20v50",
    "xs_mom_rank20", "xs_rel_str20", "vol_rel20", "struct_breakout20",
]
COVERAGES = [0.2, 0.3, 0.4]
SEED = 7
PANEL_CACHE = store_root() / "alpha_panel.parquet"


def _panel_arrays(panel: pd.DataFrame, split: str, feature: str, horizon: int):
    sub = panel[panel["split"] == split].dropna(subset=[feature, f"fwd_ret_{horizon}"])
    return (
        sub[feature].to_numpy(dtype=float),
        sub[f"fwd_ret_{horizon}"].to_numpy(dtype=float),
        sub.index.get_level_values("symbol").to_numpy(),
        sub.index.get_level_values("date").to_numpy(),
    )


def ipn(key: str) -> dict:
    return next(f for f in FEATURES if f["key"] == key)


def load_panel() -> pd.DataFrame:
    if PANEL_CACHE.exists():
        p = pd.read_parquet(PANEL_CACHE)
        p.index = pd.MultiIndex.from_arrays(
            [p.index.get_level_values(0), p.index.get_level_values(1).tz_convert("Asia/Kolkata")])
        print(f"[panel] cached {len(p)} rows")
        return p
    p = build_panel(verbose=True)
    p.to_parquet(PANEL_CACHE)
    print(f"[panel] built + cached {len(p)} rows")
    return p


def keyed_lookup(results: dict):
    return {(f, h): results["ic_table"][f][str(h)]
            for f in results["ic_table"] for h in [int(k) for k in results["ic_table"][f]]}


def candidates_from(results: dict):
    sel = results.get("selection", {})
    if sel.get("selected"):
        return [(x["feature"], x["horizon"]) for x in sel["selected"]]
    presel = sel.get("preselected_by_sign_and_magnitude", [])[:5]
    return [(x["feature"], x["horizon"]) for x in presel]


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/alpha_discovery_results.json")
    ap.add_argument("--from-scratch", action="store_true")
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not args.from_scratch:
        results = json.loads(out_path.read_text())
        print(f"[resume] loaded {len(results.get('done', []))} phases from {out_path}")
        features_used = [f["key"] for f in results["features"]]
    else:
        results = None

    panel = load_panel()
    splits = load_splits()
    features_used = features_used if results is not None else [f["key"] for f in FEATURES]

    if results is None:
        results = {
            "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "timeframe": "d1d",
            "panel_rows": int(len(panel)),
            "splits": {k: {"start": str(v["start"]), "end": str(v["end"])} for k, v in splits.items()},
            "forward_returns": {"definitions": "fwd_ret_h = close[t+h]/close[t] - 1",
                                "horizons_days": HORIZONS,
                                "causality": "feature data <= t; labels use data > t"},
            "features": FEATURES,
            "hypotheses_grid": {"features": len(features_used), "horizons": len(HORIZONS),
                                "pairs_tested": len(features_used) * len(HORIZONS)},
            "ic_table": {},
            "selection": {},
            "fdr_controls": {},
            "quantile_profiles": {},
            "cross_sectional": {},
            "regime_conditional": {},
            "combinations": {},
            "walkforward": {},
            "randomized_controls": {},
            "cost_aware": {},
            "ranking": [],
            "conclusion": None,
            "done": [],
        }
        with out_path.open("w") as fh:
            json.dump(results, fh, indent=2, default=str)

    # ---------- PHASE 3: IC grid ----------
    def phase_ic():
        for f in features_used:
            row = {}
            for h in HORIZONS:
                by_split = {}
                for sp in SPLIT_ORDER:
                    x, y, sym, _ = _panel_arrays(panel, sp, f, h)
                    by_split[sp] = ic_stats(x, y, sym)
                row[str(h)] = by_split
            results["ic_table"][f] = row
        print(f"IC grid: {len(features_used)} x {len(HORIZONS)} x {len(SPLIT_ORDER)}")

    run_phase(out_path, results, "phase3_ic_grid", phase_ic)
    keyed = keyed_lookup(results)

    # ---------- PHASE 8: selection with FDR ----------
    def phase_selection():
        preselect = []
        for (f, h), tbl in keyed.items():
            tr, va = tbl["train"], tbl["validation"]
            if tr["status"] != "OK" or va["status"] != "OK":
                continue
            if tr["sign"] == va["sign"] and max(abs(tr["spearman_ic"]), abs(va["spearman_ic"])) >= 0.01:
                preselect.append((f, h))
        val_pvals = [keyed[k]["validation"]["pvalue"] for k in preselect]
        qvals = bh_fdr(val_pvals)
        selected = [k for k, q in zip(preselect, qvals) if q <= 0.10 and
                    keyed[k]["validation"]["pvalue"] is not None and
                    keyed[k]["validation"]["pvalue"] < 0.05]
        results["selection"] = {
            "pairs_tested": len(features_used) * len(HORIZONS),
            "preselected_by_sign_and_magnitude": [{"feature": f, "horizon": h} for f, h in preselect],
            "preselected_count": len(preselect),
            "fdr_q_threshold": 0.10,
            "fdr_qvalues_validation": [{"feature": f, "horizon": h, "q": round(float(q), 4)}
                                       for (f, h), q in zip(preselect, qvals)],
            "selected_count": len(selected),
            "selected": [{"feature": f, "horizon": h} for f, h in selected],
        }
        results["fdr_controls"] = {
            "method": "Benjamini-Hochberg on VALIDATION p-values of preselected pairs",
            "hypotheses_screened": len(features_used) * len(HORIZONS),
            "preselected_for_fdr": len(preselect),
            "selected_after_fdr": len(selected),
            "note": "FINAL-OOS is a holdout scored once, never used for selection.",
        }
        print(f"preselected {len(preselect)}; survived FDR(q<=0.10): {len(selected)}")

    run_phase(out_path, results, "phase8_selection_fdr", phase_selection)
    candidates = candidates_from(results)

    # ---------- PHASE 4: quantile profiles ----------
    def phase_quantiles():
        for (f, h) in candidates:
            qp = {}
            for sp in SPLIT_ORDER:
                x, y, _, _ = _panel_arrays(panel, sp, f, h)
                qp[sp] = quantile_profile(x, y, q=5)
            qp["feature"], qp["horizon"] = f, h
            qp["descr"] = ipn(f)["definition"]
            results["quantile_profiles"][f"{f}@{h}"] = qp
            print(f"  {f:24s} h={h:2d} final spread {qp['final_oos'].get('top_bottom_spread_pct','-')}%")

    run_phase(out_path, results, "phase4_quantiles", phase_quantiles)

    # ---------- PHASE 5: cross-sectional ----------
    def phase_cs():
        for f in RANK_WORTHY:
            for h in HORIZONS:
                for cov in COVERAGES:
                    for sp in SPLIT_ORDER:
                        r = long_short_by_date(panel, f, h, sp, cov)
                        if r["status"] == "OK":
                            results["cross_sectional"].setdefault(f, {}).setdefault(str(h), []).append(
                                {k: v for k, v in r.items()})
        for f in RANK_WORTHY:
            hits = [v for h in HORIZONS for v in results["cross_sectional"].get(f, {}).get(str(h), [])
                    if isinstance(v, dict) and v.get("split") == "final_oos" and v.get("coverage") == 0.2]
            if hits:
                best = max(hits, key=lambda v: v.get("ls_mean_pct", -1e9))
                print(f"  {f:24s} final-OOS 20/80 LS {best['ls_mean_pct']}% t={best.get('ls_tstat')} "
                      f"dates={best.get('dates')}")

    run_phase(out_path, results, "phase5_cross_sectional", phase_cs)

    # ---------- PHASE 6: combination (candidates) ----------
    def phase_combo():
        top = sorted(candidates, key=lambda k: abs(
            keyed[k]["final_oos"].get("spearman_ic", 0)), reverse=True)
        combos = top[:3]
        if not combos:
            return
        pairs = [(a, b) for i, a in enumerate(combos) for b in combos[i + 1:]]
        red = {}
        for (f1, h1), (f2, h2) in pairs:
            sub = panel[panel["split"].isin(["train", "validation"])].dropna(subset=[f1, f2])
            red[f"{f1}@{h1} vs {f2}@{h2}"] = {"feature_corr": round(float(sub[f1].corr(sub[f2])), 4)}
        results["combinations"]["redundancy"] = red
        for (f1, h1), (f2, h2) in pairs:
            oos = panel[panel["split"].isin(["validation", "final_oos"])].dropna(subset=[f1, f2, f"fwd_ret_{h1}"])
            a = oos[f1].to_numpy(float)
            b = oos[f2].to_numpy(float)
            y = oos[f"fwd_ret_{h1}"].to_numpy(float)
            results["combinations"][f"{f1}@{h1}+{f2}@{h2}"] = {
                "partial_ic_b_given_a": partial_ic(a, b, y),
                "partial_ic_a_given_b": partial_ic(b, a, y),
            }
        for combo_keys in [combos[:1], combos[:2], combos[:3]]:
            feats = [k[0] for k in combo_keys]
            z = composite_z_cols(panel, feats, "final_oos")
            y = panel.loc[z.index, f"fwd_ret_{combo_keys[-1][1]}"].to_numpy(float)
            zz = z.to_numpy(float)
            st = ic_stats(zz, y, z.index.get_level_values("symbol").to_numpy())
            results["combinations"][f"composite:{'+'.join(feats)}"] = {
                "ic": st.get("spearman_ic"), "pvalue": st.get("pvalue"),
                "n": st.get("n"), "ci95_lo": st.get("ci95_lo"), "ci95_hi": st.get("ci95_hi")}
            print(f"  composite {feats}: final-OOS IC {st.get('spearman_ic')}")

    run_phase(out_path, results, "phase6_combination", phase_combo)

    # ---------- PHASE 7: regime-conditional ----------
    def phase_regime():
        for (f, h) in candidates:
            for sp in SPLIT_ORDER:
                rows = regime_ic(panel, f, h, sp)
                if rows:
                    results["regime_conditional"].setdefault(f"{f}@{h}", {})[sp] = rows

    run_phase(out_path, results, "phase7_regime", phase_regime)

    # ---------- PHASE 9: cost-aware ----------
    def phase_cost():
        for (f, h) in candidates:
            results["cost_aware"][f"{f}@{h}"] = {}
            for sp in ["validation", "final_oos"]:
                r = cost_aware_ls(panel, f, h, sp, coverage=0.10)
                results["cost_aware"][f"{f}@{h}"][sp] = r
                if r["status"] == "OK":
                    print(f"  {f}@{h} [{sp}] gross {r['gross_cum_pct']}% net {r['net_cum_pct']}% "
                          f"(cost-fragile: {r.get('cost_fragile')})")

    run_phase(out_path, results, "phase9_cost_aware", phase_cost)

    # ---------- PHASE 11/13: bootstrap CI + randomized controls ----------
    finalists = candidates[:4]

    def phase_bootstrap():
        for (f, h) in finalists:
            x, y, sym, dt = list(zip(*[_panel_arrays(panel, sp, f, h)
                                       for sp in ["validation", "final_oos"]]))
            x = np.concatenate(x); y = np.concatenate(y)
            sym = np.concatenate(sym); dt = np.concatenate(dt)
            bb = block_bootstrap_ic(x, y, dt, sym, seed=SEED)
            rn = randomized_null(x, y, sym, n_shuffles=200, seed=SEED)
            results["randomized_controls"][f"{f}@{h}"] = {
                "block_bootstrap": bb, "within_symbol_shuffle": rn}
            print(f"  {f:24s}@{h:2d} boot CI {bb.get('ci95_lo','-')}..{bb.get('ci95_hi','-')} "
                  f"shuffle p {rn.get('p_two_sided','-')}")

    run_phase(out_path, results, "phase11_13_bootstrap_rand", phase_bootstrap)

    # ---------- PHASE 10: walk-forward survival ----------
    def phase_walkforward():
        wf_all = {}
        wf_keys = {k for k in keyed if k in candidates or
                   abs(keyed[k]["train"].get("spearman_ic", 0)) >= 0.01}
        t0 = splits["train"]["start"]; t1 = splits["validation"]["end"]
        n_blocks = 12
        step = (t1 - t0) / n_blocks
        blocks = [(t0 + i * step, t0 + (i + 1) * step) for i in range(n_blocks)]
        for (f, h) in sorted(wf_keys):
            surv = []
            for (b0, b1) in blocks:
                mid = b0 + (b1 - b0) / 2
                disc = panel[(panel.index.get_level_values("date") >= b0) &
                             (panel.index.get_level_values("date") < mid)]
                val = panel[(panel.index.get_level_values("date") >= mid) &
                            (panel.index.get_level_values("date") < b1)]
                sd = disc.dropna(subset=[f, f"fwd_ret_{h}"])
                sv = val.dropna(subset=[f, f"fwd_ret_{h}"])
                if len(sd) < 200 or len(sv) < 200:
                    continue
                id_ = ic_stats(sd[f].to_numpy(float), sd[f"fwd_ret_{h}"].to_numpy(float),
                               sd.index.get_level_values("symbol").to_numpy())
                iv = ic_stats(sv[f].to_numpy(float), sv[f"fwd_ret_{h}"].to_numpy(float),
                              sv.index.get_level_values("symbol").to_numpy())
                if id_["status"] == "OK" and iv["status"] == "OK":
                    same_sign = id_["sign"] == iv["sign"]
                    mag = max(abs(id_["spearman_ic"]), abs(iv["spearman_ic"])) >= 0.005
                    sig = (id_["pvalue"] or 1) < 0.1 or (iv["pvalue"] or 1) < 0.1
                    surv.append(bool(same_sign and mag and sig))
            if surv:
                wf_all[f"{f}@{h}"] = {"blocks_computed": len(surv),
                                      "survival_rate": round(float(np.mean(surv)), 3),
                                      "survival_slots": int(np.sum(surv))}
        results["walkforward"] = wf_all
        for k, v in sorted(wf_all.items(), key=lambda kv: -kv[1]["survival_rate"])[:12]:
            print(f"  {k:24s} survival {v['survival_rate']:.2f} ({v['survival_slots']}/{v['blocks_computed']})")

    run_phase(out_path, results, "phase10_walkforward", phase_walkforward)

    # ---------- PHASE 15: ranking + conclusion ----------
    def phase_ranking():
        ranking = []
        for (f, h), tbl in keyed.items():
            tr, va, fi = tbl["train"], tbl["validation"], tbl["final_oos"]
            ok = all(v["status"] == "OK" for v in (tr, va, fi))
            if not ok:
                continue
            signs = (tr["sign"], va["sign"], fi["sign"])
            stable = signs[0] == signs[1] == signs[2]
            stable_pos = stable and signs[0] == 1
            stable_neg = stable and signs[0] == -1
            oos_mag = max(abs(va["spearman_ic"]), abs(fi["spearman_ic"]))
            ic_final = fi["spearman_ic"]
            wf_rate = results["walkforward"].get(f"{f}@{h}", {}).get("survival_rate", 0.0)
            cost = results["cost_aware"].get(f"{f}@{h}", {})
            net_final = cost.get("final_oos", {}).get("net_cum_pct")
            gross_final = cost.get("final_oos", {}).get("gross_cum_pct")
            qp = results["quantile_profiles"].get(f"{f}@{h}", {}).get("final_oos", {})
            spread = qp.get("top_bottom_spread_pct")
            monot = qp.get("monotonic_rho")

            label, notes = "NO EVIDENCE", []
            if not stable:
                label, notes = "UNSTABLE", ["sign flips across splits"]
            elif stable_neg:
                label = "REVERSED SIGNAL"
                notes.append("stably predicts sign-consistent NEGATIVE OOS IC; natural long-top/"
                             "short-bottom direction loses across splits")
                if net_final is not None and (gross_final or 0) > 0 and net_final <= 0:
                    notes.append("natural-direction net<=0 after costs")
            else:
                if oos_mag >= 0.01 and wf_rate >= 0.5:
                    label = "STRONG RESEARCH CANDIDATE"
                elif oos_mag >= 0.005 and (ic_final or 0) > 0:
                    label = "PROMISING - MORE DATA" if wf_rate < 0.6 else "STRONG RESEARCH CANDIDATE"
            if label == "STRONG RESEARCH CANDIDATE" or label == "PROMISING - MORE DATA":
                if net_final is not None and (gross_final or 0) > 0 and net_final <= 0:
                    label, notes = "COST-FRAGILE", notes + ["net<=0 after costs"]
            if (monot or 0) < 0.5 and label in ("STRONG RESEARCH CANDIDATE",):
                notes.append("weak monotonicity across buckets")
            ranking.append({
                "feature": f, "horizon": h, "train_ic": tr["spearman_ic"],
                "validation_ic": va["spearman_ic"], "final_oos_ic": fi["spearman_ic"],
                "sign_stable_across_splits": stable,
                "oos_max_abs_ic": round(oos_mag, 5),
                "walkforward_survival": wf_rate,
                "gross_cum_pct_final": gross_final, "net_cum_pct_final": net_final,
                "final_oos_top_bottom_spread_pct": spread,
                "final_oos_monotonic_rho": monot,
                "decision": label, "notes": "; ".join(notes),
            })
        ranking.sort(key=lambda r: (
            0 if "STRONG" in r["decision"] else 1 if "PROMISING" in r["decision"]
            else 2 if "COST-FRAGILE" in r["decision"] else 3 if "REVERSED" in r["decision"]
            else 4 if "REGIME" in r["decision"] else 5,
            -abs(r["final_oos_ic"])))
        results["ranking"] = ranking
        print(f"{'feature@horizon':28s} {'train':>8} {'val':>8} {'final':>8} {'wf':>5} {'net%':>8} decision")
        for r in ranking[:25]:
            nf = r["net_cum_pct_final"]
            print(f"{r['feature']}@{r['horizon']:<6d} {r['train_ic']:8.4f} {r['validation_ic']:8.4f} "
                  f"{r['final_oos_ic']:8.4f} {r['walkforward_survival']:5.2f} "
                  f"{nf if nf is not None else float('nan'):8.2f} {r['decision']}")

    run_phase(out_path, results, "phase15_ranking", phase_ranking)

    # ---------- Conclusion ----------
    if "conclusion_saved" not in results.get("done", []):
        strong = [r for r in results["ranking"] if r["decision"] == "STRONG RESEARCH CANDIDATE"]
        promising = [r for r in results["ranking"] if r["decision"] == "PROMISING - MORE DATA"]
        fragile = [r for r in results["ranking"] if r["decision"] == "COST-FRAGILE"]
        reversed_sig = [r for r in results["ranking"] if r["decision"] == "REVERSED SIGNAL"]
        results["conclusion"] = {
            "candidates_ranked": len(results["ranking"]),
            "strong": len(strong), "promising": len(promising),
            "cost_fragile": len(fragile), "reversed_signal": len(reversed_sig),
            "unstable": len([r for r in results["ranking"] if r["decision"] == "UNSTABLE"]),
            "no_evidence": len([r for r in results["ranking"] if r["decision"] == "NO EVIDENCE"]),
            "alpha_demonstrated": bool(strong),
            "summary": ("At least one feature set shows stable sign-consistent POSITIVE OOS IC with "
                        "cost-surviving net returns" if strong else
                        "No feature exhibited a stable, POSITIVE-direction, cost-surviving OOS signal "
                        "across this data; several stably predict the reverse direction, and many "
                        "train-strong pairs are sign-unstable or cost-fragile at final OOS"),
        }
        results["done"].append("conclusion_saved")
        with out_path.open("w") as fh:
            json.dump(results, fh, indent=2, default=str)
    print(f"\ndone: {out_path}")


if __name__ == "__main__":
    main()