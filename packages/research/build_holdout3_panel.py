"""Build the frozen holdout-3 alpha panel + V2 feature panel.

Reuses the frozen pipeline builders verbatim by injecting the store root and
the PANELS registry entry at runtime (no frozen-file edits):

  1. alpha_dataset.build_panel on data/holdout_3  -> alpha_panel_holdout3.parquet
     (carries exactly the frozen CARRY columns: split, regime_bucket,
      fwd_ret_1..20, mkt_*, xs_*, vol/trend features)
  2. alpha_v2_features.build_v2_panel("holdout3") -> data/alpha_v2/holdout3_v2_panel.parquet

Usage:
  python -m packages.research.build_holdout3_panel
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from packages.research import alpha_dataset as ad
from packages.research import alpha_v2_features as fv

ROOT3 = Path("data/holdout_3")
PANEL3 = ROOT3 / "alpha_panel_holdout3.parquet"
V2OUT = Path("data/alpha_v2/holdout3_v2_panel.parquet")


def main() -> None:
    ad.store_root = lambda: ROOT3
    p = ad.build_panel(verbose=True)
    p.to_parquet(PANEL3)
    print(f"wrote {PANEL3}: {p.shape}")

    fv.PANELS["holdout3"] = (str(PANEL3), str(ROOT3 / "d1d"))
    comp = fv.build_v2_panel("holdout3")
    p2 = fv.compute_v2_features(comp)
    del comp
    p2.sort_index().to_parquet(V2OUT)
    print(f"wrote {V2OUT}: {p2.shape}")


if __name__ == "__main__":
    main()