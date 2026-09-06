"""Holdout-3 reproducibility checker (Phase 0 / audit trail).

Re-runs the committed one-shot confirmation inputs and verifies the reported
holdout-3 result reproduces. Steps:
  1. universe.json  -> assert manifest.json symbol set == universe selected
  2. manifest.json  -> assert dataset_lock sha256 matches manifest bytes
  3. rebuild the V2 panel from data/holdout_3 (splits.json + d1d) using the
     frozen builders (panel + compute_v2_features)
  4. recompute the frozen COMposite verdict metrics (pooled rank-IC h=1,
     whole-corpus net @25bps, temporal band fraction) for COMP1/COMP3
  5. compare against the committed data/alpha_v2/holdout3_eval.json

Exit 0 => the committed trail reproduces the reported result.

NOTE: data/holdout_3/d1d parquets are the corpus store (not tracked); a fresh
repro requires that store to be present locally, exactly as locked.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from packages.research import alpha_v2_features as fv
from packages.research import composite_alpha as ca

ROOT3 = Path("data/holdout_3")
V2OUT = Path("data/alpha_v2/holdout3_v2_panel.parquet")
EVAL = Path("data/alpha_v2/holdout3_eval.json")
TOL_IC = 1e-4
TOL_NET = 1e-3  # percentage-point tolerance


def check_universe_manifest(u: dict, man: list[dict]) -> None:
    kept = json.loads((ROOT3 / "eligible_symbols.json").read_text())["kept"]
    dropped = json.loads((ROOT3 / "eligible_symbols.json").read_text())["dropped"]
    syms = {e["symbol"] for e in man}
    bars = {e["symbol"]: e.get("bars") for e in man}
    assert all(d["symbol"] in syms for d in dropped), "dropped subset of manifest"
    assert not (set(kept) & {d["symbol"] for d in dropped}), "kept and dropped disjoint"
    assert all(bars[s] >= 700 for s in kept), "kept all bars>=700"
    failed = {e["symbol"] for e in json.loads((ROOT3 / "failed.json").read_text())}
    audit = json.loads((ROOT3 / "audit.json").read_text())
    purged = {e["symbol"] for e in audit.get("purged_empty", [])}
    assert set(u["selected"]) <= (syms | failed | purged), \
        "universe selected must be in manifest, failed, or purged"


def check_lock(man: list[dict]) -> None:
    lock = json.loads((ROOT3 / "dataset_lock.json").read_text())
    sha = hashlib.sha256((ROOT3 / "manifest.json").read_bytes()).hexdigest()
    assert lock["sha256"] == sha, "dataset_lock sha256 mismatch"
    n_kept = len(json.loads((ROOT3 / "eligible_symbols.json").read_text())["kept"])
    assert lock["n_symbols"] == n_kept, "n_symbols mismatch"


def build_v2_holdout3() -> pd.DataFrame:
    fv.PANELS["holdout3"] = (str(ROOT3 / "alpha_panel_holdout3.parquet"), str(ROOT3 / "d1d"))
    comp = fv.build_v2_panel("holdout3")
    p2 = fv.compute_v2_features(comp)
    del comp
    return p2


def verdict_metrics(ho: pd.DataFrame, name: str, val_ic_ref: float) -> dict:
    frz = json.loads(ca.FRZ_PATH.read_text())
    cols = ca.composite_columns(ho, frz)
    H = ho.copy()
    H[name] = cols[name][0]
    keep = H.dropna(subset=[name, "fwd_ret_1"])
    ic = float(pd.Series(keep[name]).corr(keep["fwd_ret_1"], method="spearman"))
    A = H.copy()
    A["split"] = "train"
    net = ca.aa.cost_aware_ls(A, name, 1, "train", 0.10, 0.0025)["net_cum_pct"]
    sub = H.dropna(subset=[name, "fwd_ret_1"]).copy()
    sub["dt"] = sub.index.get_level_values("date")
    dates = pd.Index(np.unique(sub["dt"])).sort_values()
    sub["band"] = dates.searchsorted(sub["dt"]) // 126
    frac = 0.0
    n = 0
    for _b, g in sub.groupby("band"):
        if len(g) < ca.MIN_IC_ROWS or g[name].nunique() < 5:
            continue
        icb = float(pd.Series(g[name]).corr(g["fwd_ret_1"], method="spearman"))
        frac += (icb > 0)
        n += 1
    return {"ic": ic, "net25": float(net), "bands_frac": (frac / n) if n else None,
            "n_bands": n, "threshold": 0.8 * val_ic_ref}


def main() -> None:
    u = json.loads((ROOT3 / "universe.json").read_text())
    man = json.loads((ROOT3 / "manifest.json").read_text())
    check_universe_manifest(u, man)
    check_lock(man)
    print("corpus integrity: universe/manifest/eligible/lock consistent")

    ho = build_v2_holdout3()
    ho = ho[ho["split"] != ""]
    print(f"rebuilt panel {ho.shape} (2014+ rows {len(ho)})")

    ev = json.loads(EVAL.read_text())
    ok = True
    for name, ref in (("COMP1_REVERSAL_BREADTH", 0.03725), ("COMP3_REVERSAL_BREADTH_DISP", 0.02894)):
        got = verdict_metrics(ho, name, ref)
        exp = ev["verdicts"][name]
        ic_ok = abs(got["ic"] - exp["overall_ic_h1"]) <= TOL_IC
        net_ok = abs(got["net25"] - exp["net25bps_pct"]) <= TOL_NET * max(1, abs(exp["net25bps_pct"]))
        band_ok = exp["bands_frac_positive"] is not None and got["bands_frac"] is not None \
            and abs(got["bands_frac"] - exp["bands_frac_positive"]) <= 0.02
        ok &= ic_ok and net_ok and band_ok
        print(f"{name}: ic={got['ic']:.4f} (ok={ic_ok})  net25={got['net25']:.2f} (ok={net_ok}) "
              f"bands={got['bands_frac']:.2f}/{got['n_bands']} (ok={band_ok})")
    v1 = ev["verdicts"]["COMP1_REVERSAL_BREADTH"]["verdict"]
    v3 = ev["verdicts"]["COMP3_REVERSAL_BREADTH_DISP"]["verdict"]
    print(f"committed verdicts: COMP1={v1}  COMP3={v3}")
    print("REPRODUCES" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()