"""COMP3 program reproducibility + integrity verification (close-out, 2026-09).

Runs the exact locked pipeline and asserts byte-identical outputs:

  1. dev study            python -m packages.research.comp3_diversification
  2. holdout-5 eval       python -m packages.research.holdout5_strategy --evaluate
  3. corpus lock          dataset_lock.sha256 == sha256(manifest.json bytes)
  4. manifest checksums   every d1d parquet sha256 matches manifest entry
  5. disjointness         holdout-5 sets vs DEVELOPMENT+H1..H4 from REAL manifests
  6. decision gates       D1_CAP8 nets >0 @25/100bp, A-G = D, paper_trade = False

Independent of web/network. Prints PASS/FAIL per check; exits 1 on any FAIL.

Usage: python -m packages.research.verify_comp3_program
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
PY = sys.executable

DEV_JSON = Path("reports/comp3_diversification_results.json")
DEV_MD = Path("reports/COMP3_DIVERSIFICATION_RESEARCH_2026-09.md")
H5_RESULT = Path("data/comp3/holdout5_results.json")
H5_CLASS = Path("data/comp3/holdout5_classification.json")
H5_MD = Path("reports/COMP3_HOLDOUT5_CONFIRMATION_2026-09.md")

# byte-identical baselines captured from the 611bc17 commit (locked one-shot run)
REF_DEV_JSON = "35c3ed79728478cefe0e18790c472948427f1eeb91ece1b776792037419dc0b5"
REF_DEV_MD = "683044da821daad7cd448b8340059dfc9881802f930dbad1cb4071eadbfd21ed"
REF_H5_RESULT = "4c7a5bd2cd6d4d12a0998e871ae73bb5220fa24fe357e7ddcd0a2d39acabcb31"
REF_H5_CLASS = "667377b930e32aebf3aedf1e96df20dde6853577bc13511f4e4eecc616f460f6"
REF_H5_MD = "132aaf3a6d0ff902e7a4785988b04201f1fc4f21430c4074463a80f574fbe0e4"

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a single PASS/FAIL verification check."""
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(name)


def sha(p: Path) -> str:
    """Return sha256 hex digest of a file's bytes."""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_dev() -> None:
    """Rerun the dev study and assert byte-identical outputs."""
    subprocess.run([PY, "-m", "packages.research.comp3_diversification"],
                   check=True, cwd=".")
    check("dev-study deterministic (JSON byte-identical)",
          sha(DEV_JSON) == REF_DEV_JSON)
    check("dev-study report byte-identical",
          sha(DEV_MD) == REF_DEV_MD)


def run_holdout5_eval() -> None:
    """Rerun the one-shot holdout-5 evaluator and assert byte-identity."""
    subprocess.run([PY, "-m", "packages.research.holdout5_strategy", "--evaluate"],
                   check=True, cwd=".")
    check("holdout-5 eval reproducible (JSON byte-identical)",
          sha(H5_RESULT) == REF_H5_RESULT)
    check("holdout-5 classification byte-identical",
          sha(H5_CLASS) == REF_H5_CLASS)
    check("holdout-5 confirmation report byte-identical",
          sha(H5_MD) == REF_H5_MD)


def verify_corpus() -> None:
    """Verify lock sha, manifest checksums, audit drop and eligibility."""
    h5 = Path("data/holdout_5")
    lock = json.loads((h5 / "dataset_lock.json").read_text())
    man = json.loads((h5 / "manifest.json").read_text())
    check("holdout-5 lock matches manifest", lock["sha256"] == sha(h5 / "manifest.json"),
          lock["sha256"][:16] + " seed=" + "13a1eeb11cac628b711b146efff1c0b".split("=")[-1][:8])
    bad = [e["symbol"] for e in man
           if e.get("sha256") and e["sha256"] != sha(h5 / e["file"])]
    check("holdout-5 manifest checksums", not bad, f"checked {len(man)} files")
    elig = json.loads((h5 / "eligible_symbols.json").read_text())
    dropped = [d.get("symbol") for d in elig["dropped"]]
    check("holdout-5 audit drop = FSL.NS only", dropped == ["FSL.NS"], ",".join(dropped))
    check("holdout-5 eligible count = 39", len(elig["kept"]) == 39)


def used_from_real_manifests() -> set[str]:
    """Rebuild the used-symbol union from ACTUAL manifest files."""
    def m(p: str) -> set[str]:
        return {e["symbol"] for e in json.loads(Path(p).read_text())}
    def u(p: str) -> set[str]:
        return set(json.loads(Path(p).read_text())["selected"])
    out: set[str] = set()
    out |= m("data/historical/manifest.json")      # development
    out |= u("data/holdout/universe.json")         # holdout 1
    out |= m("data/holdout_2/manifest.json")       # holdout 2
    out |= u("data/holdout_3/universe.json")       # holdout 3
    out |= u("data/holdout_4/universe.json")       # holdout 4
    return out


def verify_disjoint() -> None:
    """Assert holdout-5 is disjoint from every prior corpus."""
    used = used_from_real_manifests()
    check("used union == 228 actual symbols", len(used) == 228, str(len(used)))
    h5 = json.loads(Path("data/holdout_5/universe.json").read_text())
    elig = json.loads(Path("data/holdout_5/eligible_symbols.json").read_text())["kept"]
    selected = h5["selected"]
    check("holdout-5 selection disjoint from real manifests",
          not (set(selected) & used), f"selected={len(selected)}")
    check("holdout-5 eligible disjoint from real manifests",
          not (set(elig) & used), f"eligible={len(elig)}")


def verify_decision() -> None:
    """Assert the frozen gates, A-G grade and paper-gate state."""
    r = json.loads(H5_RESULT.read_text())
    d = r["constructions"]["D1_CAP8"]
    c = r["concentration"]["D1_CAP8"]
    cls = r["classification"]
    check("D1_CAP8 net>0 @25bps", d["25bps"].get("net_cum_pct", 0) > 0)
    check("D1_CAP8 net>0 @100bps stress", d["100bps"].get("net_cum_pct", 0) > 0)
    check("D1_CAP8 concentration fragile",
          c["concentration_fragile"],
          f"top5={c['top5_share']} "
          f"flips={len(c['leave_one_out_sign_flips'])}")
    for nm in ("D2_QUINTILE", "V1_DECILE"):
        check(f"{nm} also fragile (same sign-flip set)",
              r["concentration"][nm]["concentration_fragile"])
    check("A-G decision == D STILL CONCENTRATION-FRAGILE",
          cls["grade"].startswith("D"), cls["grade"])
    check("paper-trade gate CLOSED", cls.get("paper_trade") is False)
    check("no-leakage gate (locked corpus verified inside eval)",
          str(r["corpus_lock"]).startswith("OK"))


if __name__ == "__main__":
    run_dev()
    run_holdout5_eval()
    verify_corpus()
    verify_disjoint()
    verify_decision()
    print("\n" + ("ALL COMP3 PROGRAM CHECKS PASS" if not FAILS
                  else f"{len(FAILS)} CHECK(S) FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
