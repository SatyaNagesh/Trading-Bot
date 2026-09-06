"""Composite V3 — one-shot holdout-3 confirmation (P14 execution).

Evaluates the frozen composites COMP1 (primary) and COMP3 (secondary) on the
new untouched holdout-3 corpus under the gates/thresholds frozen in
composite_freeze.json. COMP2 + C0 baseline + inverse diagnostics are reported
for parity. Method parity with the development evaluation: eval_composite from
composite_alpha.py is reused verbatim.

Verdict per frozen protocol:
    PASS  = sign-consistent rank-IC(h=1) on the whole holdout-3 corpus
            >= 0.8 x development-VALIDATION IC  AND  net-anchored returns
            @25bps >= 0  AND  majority of 126d temporal bands positive
    else FAIL (no grade upgrade).

Usage:
  python -m packages.research.composite_holdout3
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from packages.research import composite_alpha as ca

HO_PATH = "data/alpha_v2/holdout3_v2_panel.parquet"
OUT = "data/alpha_v2/holdout3_eval.json"

# dev-validation rank-ICs (frozen evidence, composite_freeze.json narrative +
# composite_eval.json) used as the 0.8x reference.
DEV_VAL_IC = {"COMP1_REVERSAL_BREADTH": 0.037, "COMP3_REVERSAL_BREADTH_DISP": 0.029}


def main() -> None:
    frz = json.loads(ca.FRZ_PATH.read_text())
    ver = frz.get("version")
    assert ver == 2, f"freeze must be v2 (stress-side), found v{ver}"
    th = frz["thresholds_from_dev_train_medians"]

    ho = pd.read_parquet(HO_PATH)
    ho = ho[ho["split"] != ""].copy()
    print(f"holdout3 retained rows (2014+): {len(ho)}")

    cols = ca.composite_columns(ho, frz)
    H = ho.copy()
    for name, (score, _label) in cols.items():
        H[name] = score
    res = {"freeze_version": ver,
           "corpus": "holdout_3 (untouched, 38 eligible symbols)",
           "thresholds": th,
           "dev_val_ic_reference": DEV_VAL_IC,
           "pass_rule": ("sign-consistent rank-IC(h=1) >= 0.8 x dev-validation IC "
                        "AND net@25bps >= 0 AND majority positive 126d bands"),
           "composites": {}}
    for name, (score, label) in cols.items():
        print("eval", name, "...", flush=True)
        res["composites"][name] = ca.eval_composite(H, name, name, label)

    # ---- verdicts ----
    verdicts = {}
    for name, ref in DEV_VAL_IC.items():
        r = res["composites"][name]
        ic = [b["ic"] for b in r["temporal"]["bands"]]
        ic_pos = [x for x in ic if np.isfinite(x)]
        frac_pos = float(np.mean([x > 0 for x in ic_pos])) if ic_pos else None
        keep = H.dropna(subset=[name, "fwd_ret_1"])
        obs = float(pd.Series(keep[name]).corr(keep["fwd_ret_1"], method="spearman"))
        thr = 0.8 * ref
        all_corpus = H.copy()
        all_corpus["split"] = "train"  # union window for one continuous LS backtest
        net = ca.aa.cost_aware_ls(all_corpus, name, 1, "train", 0.10, 0.0025)
        net25 = net.get("net_cum_pct")
        pass_ic = np.isfinite(obs) and obs >= thr
        pass_net = (net25 is not None) and net25 >= 0
        pass_band = (frac_pos is not None) and frac_pos >= 0.5
        verdicts[name] = {
            "overall_ic_h1": round(obs, 4) if np.isfinite(obs) else None,
            "threshold_0_8x_dev_val": thr,
            "net25bps_pct": net25,
            "net25_rebalances": net.get("rebalances"),
            "bands_frac_positive": frac_pos,
            "pass_ic": bool(pass_ic), "pass_net": bool(pass_net),
            "pass_band": bool(pass_band),
            "verdict": "PASS" if (pass_ic and pass_net and pass_band) else "FAIL",
        }
    res["verdicts"] = verdicts
    open(OUT, "w").write(json.dumps(res, indent=1))
    print(json.dumps(verdicts, indent=1))


if __name__ == "__main__":
    main()