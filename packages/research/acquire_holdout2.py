"""holdout_2 acquisition — untouched confirmation universe for Phase 8/10.

Reuses the frozen ingestion/audit code verbatim; only the data store root is
injected (data/holdout_2). Symbols come exclusively from the pre-registered
data/holdout_2/universe.json (selected in select_holdout2_universe.py BEFORE
any download). Writes manifest, quarantine, audit, eligible_symbols,
splits.json (verbatim frozen boundaries) and dataset_lock.json.

Usage:
  python -m packages.research.acquire_holdout2             # fetch + audit
  python -m packages.research.acquire_holdout2 --verify    # checksum audit only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

HOLD2 = Path("data/holdout_2")
FREEZE_REF = "f6e3adc"  # pre-registration commit


def _wire() -> tuple:
    import packages.market.data_audit as da
    import packages.market.data_ingestion as di

    di.store_root = lambda: HOLD2
    da.store_root = di.store_root
    da.QUARANTINE_LOG = str(HOLD2 / "quarantine.json")
    return di, da


def run_acquire(di, start: str, end: str, sleep: float) -> None:
    univ = json.loads((HOLD2 / "universe.json").read_text())
    symbols = univ["selected"]
    records, failures = [], []
    for i, sym in enumerate(symbols, 1):
        try:
            rec = di.acquire_symbol(sym, "d1d", start, end, refresh=False)
            records.append(rec)
            print(f"  OK  {i:>2}/{len(symbols)} {sym:16s} bars={rec['bars']:>5} "
                  f"{rec['actual_start'][:10]} -> {rec['actual_end'][:10]}", flush=True)
        except Exception as e:  # noqa: BLE001
            failures.append({"symbol": sym, "timeframe": "d1d",
                             "error": str(e)[:160]})
            print(f"  ERR {i:>2}/{len(symbols)} {sym:16s} {e}", flush=True)
        time.sleep(sleep)
    di.collect_manifest(records)
    di.save_failed(failures)
    print(f"acquired {len(records)} / {len(symbols)}; {len(failures)} failures", flush=True)


def lock_dataset(di) -> None:
    man_bytes = (HOLD2 / "manifest.json").read_bytes()
    sha = hashlib.sha256(man_bytes).hexdigest()
    kept = json.loads((HOLD2 / "eligible_symbols.json").read_text())["kept"]
    (HOLD2 / "dataset_lock.json").write_text(json.dumps({
        "sha256": sha,
        "n_symbols": len(kept),
        "bars_total": int(sum(e["bars"] for e in di.load_manifest())),
        "freeze_ref": FREEZE_REF,
        "locked_utc": datetime.now(timezone.utc).isoformat(),
        "note": "holdout_2 confirmation universe; ANY evaluation must use exactly this corpus"
    }, indent=2))
    print("lock sha256:", sha)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default="2026-09-05")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    di, da = _wire()
    HOLD2.mkdir(parents=True, exist_ok=True)

    if args.verify:
        changed = di.verify_manifest()
        print("VERIFY:", changed if changed else "all checksums match")
        return

    run_acquire(di, args.start, args.end, args.sleep)

    log = da.cleanse()
    (HOLD2 / "quarantine.json").write_text(json.dumps(log, indent=2, default=str))
    audit = da.run_audit()
    (HOLD2 / "audit.json").write_text(json.dumps(audit, indent=2, default=str))
    print("audit overall:", audit["quality_summary"]["overall"])

    kept, dropped = [], []
    for entry in di.load_manifest():
        if entry.get("bars", 0) >= 700:
            kept.append(entry["symbol"])
        else:
            dropped.append({"symbol": entry["symbol"], "bars": entry.get("bars")})
    (HOLD2 / "eligible_symbols.json").write_text(
        json.dumps({"kept": sorted(kept), "dropped": dropped}, indent=2))
    print(f"eligible (bars>=700): {len(kept)}  dropped: {len(dropped)}")

    # verbatim frozen split boundaries (same as DEVELOPMENT and HOLDOUT)
    (HOLD2 / "splits.json").write_text(json.dumps({
        "train": {"start": "2014-01-01", "end": "2023-01-01"},
        "validation": {"start": "2023-01-01", "end": "2025-07-01"},
        "final_oos": {"start": "2025-07-01", "end": "2026-09-05"},
    }, indent=2))

    lock_dataset(di)


if __name__ == "__main__":
    main()