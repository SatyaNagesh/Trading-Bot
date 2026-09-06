"""Alpha Research V2 — Phase 1 freeze & dataset manifest.

Records the immutable baseline on which the new research phase starts:
current git commit, previous decision records, and hash/manifest of all
frozen data corpora. Nothing in this module mutates previous results.

Output: data/alpha_v2/baseline_freeze.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *cmd], capture_output=True,
                          text=True).stdout.strip()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def manifest_dir(name: str, d: Path) -> dict:
    files = sorted(d.rglob("*.parquet")) if d.is_dir() else []
    sizes = [f.stat().st_size for f in files]
    return {
        "name": name,
        "root": str(d.relative_to(ROOT)),
        "n_parquet": len(files),
        "total_bytes": int(sum(sizes)),
        "sha256_tree": _sha256_file(files[0]) if files else None,
    }


def freeze() -> dict:
    rec = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "1-freeze",
        "purpose": "Immutable benchmark for Alpha Research V2; no new hypothesis selection on this data.",
        "git": {
            "commit": _git(["rev-parse", "HEAD"]),
            "short": _git(["rev-parse", "--short=7", "HEAD"]),
            "remote": _git(["remote", "get-url", "origin"]),
            "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        },
        "previous_decision_records": [
            "reports/INDEPENDENT_HOLDOUT_VALIDATION_2026-09.md",
            "reports/VOL_TREND_SIGNAL_TO_ALPHA_PRE_REGISTRATION_2026-09.md",
            "reports/VOL_TREND_SIGNAL_TO_ALPHA_2026-09.md",
            "reports/vol_trend_signal_to_alpha.json",
        ],
        "corpora": {
            "development": manifest_dir("development", ROOT / "data/historical"),
            "frozen_holdout": manifest_dir("frozen_holdout", ROOT / "data/holdout"),
            "holdout_2": manifest_dir("holdout_2", ROOT / "data/holdout_2/d1d"),
        },
        "holdout_2_lock": json.loads((ROOT / "data/holdout_2/dataset_lock.json").read_text())
        if (ROOT / "data/holdout_2/dataset_lock.json").exists() else None,
        "frozen_splits": {
            "train_start": "2014-01-01", "train_end": "2023-01-01",
            "validation_start": "2023-01-01", "validation_end": "2025-07-01",
            "final_oos_start": "2025-07-01", "final_oos_end": "2026-09-04",
        },
        "immutability_note": ("No file under data/ or reports/ from these commits may be "
                              "modified by the V2 research phase."),
    }
    out = ROOT / "data/alpha_v2/baseline_freeze.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2))
    return rec


if __name__ == "__main__":
    r = freeze()
    print(json.dumps(r, indent=2))
    print(f"\nwrote {ROOT / 'data/alpha_v2/baseline_freeze.json'}")
    sys.exit(0)