"""holdout_5 acquisition — untouched COMP3 V2 (diversified) confirmation corpus.

Same frozen ingestion/audit code as acquire_holdout4.py; only the store root is
data/holdout_5. Symbols come exclusively from the pre-registered
data/holdout_5/universe.json (written by select_holdout5_universe.py BEFORE any
download). Writes manifest, quarantine, audit, eligible_symbols, splits.json and
dataset_lock.json. Single window 2014-01-01 -> acquisition date.

Usage:
  python -m packages.research.acquire_holdout5 [--start .. --end ..]
  python -m packages.research.acquire_holdout5 --verify
  python -m packages.research.acquire_holdout5 --finish
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

HOLD5 = Path("data/holdout_5")


def _wire() -> tuple:
    import packages.market.data_audit as da
    import packages.market.data_ingestion as di

    di.store_root = lambda: HOLD5
    da.store_root = di.store_root
    da.QUARANTINE_LOG = str(HOLD5 / "quarantine.json")
    return di, da


def run_acquire(di, start: str, end: str, sleep: float) -> None:
    univ = json.loads((HOLD5 / "universe.json").read_text())
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
    man_bytes = (HOLD5 / "manifest.json").read_bytes()
    sha = hashlib.sha256(man_bytes).hexdigest()
    kept = json.loads((HOLD5 / "eligible_symbols.json").read_text())["kept"]
    (HOLD5 / "dataset_lock.json").write_text(json.dumps({
        "sha256": sha,
        "n_symbols": len(kept),
        "bars_total": int(sum(e["bars"] for e in di.load_manifest())),
        "universe_ref": "data/holdout_5/universe.json (BEFORE any download)",
        "locked_utc": datetime.now(timezone.utc).isoformat(),
        "note": "holdout_5 COMP3 V2 strategy-confirmation universe (D1 C=8% m=13, "
                "D2 quintile m=8); ANY strategy evaluation must use exactly this "
                "corpus, locked BEFORE evaluation"
    }, indent=2))
    print("lock sha256:", sha)


def purge_empty(di, log: dict) -> list[dict]:
    """Remove parquets with zero rows after cleansing (cannot be audited)."""
    import pandas as pd

    import packages.market.data_audit as _da

    entries = di.load_manifest()
    kept, purged = [], []
    for entry in entries:
        path = HOLD5 / str(entry["file"])
        if not path.exists():
            purged.append({"symbol": entry["symbol"], "reason": "file missing"})
            continue
        try:
            df = pd.read_parquet(path)
        except Exception as e:  # noqa: BLE001
            purged.append({"symbol": entry["symbol"], "reason": f"unreadable: {e}"})
            path.unlink()
            continue
        if getattr(df.index, "tz", None) is None and "ts" in df.columns:
            df = df.set_index("ts")
        if len(df) == 0:
            path.unlink()
            purged.append({"symbol": entry["symbol"], "reason": "empty after cleanse"})
        else:
            entry["sha256"] = _da.checksum(path)
            kept.append(entry)
    di.save_manifest(kept)
    log["purged_empty"] = purged
    return purged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-09-13")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--finish", action="store_true",
                    help="skip download; run cleanse/audit/eligible/lock from manifest")
    args = ap.parse_args()

    di, da = _wire()
    HOLD5.mkdir(parents=True, exist_ok=True)

    if args.verify:
        changed = di.verify_manifest()
        print("VERIFY:", changed if changed else "all checksums match")
        return

    if not args.finish:
        run_acquire(di, args.start, args.end, args.sleep)

    log = da.cleanse()
    (HOLD5 / "quarantine.json").write_text(json.dumps(log, indent=2, default=str))
    purged = purge_empty(di, log)
    audit = da.run_audit()
    (HOLD5 / "audit.json").write_text(json.dumps(audit, indent=2, default=str))
    audit["purged_empty"] = purged
    (HOLD5 / "audit.json").write_text(json.dumps(audit, indent=2, default=str))
    print("audit overall:", audit["quality_summary"]["overall"])

    kept, dropped = [], []
    for entry in di.load_manifest():
        if entry.get("bars", 0) >= 700:
            kept.append(entry["symbol"])
        else:
            dropped.append({"symbol": entry["symbol"], "bars": entry.get("bars")})
    (HOLD5 / "eligible_symbols.json").write_text(
        json.dumps({"kept": sorted(kept), "dropped": dropped}, indent=2))
    print(f"eligible (bars>=700): {len(kept)}  dropped: {len(dropped)}")

    # Pre-registered holdout-5 confirmation window (freeze doc). Evaluated as ONE
    # undivided strategy sample, not split by dev boundaries. Schema matches
    # alpha_dataset.load_splits: {split_name: {start, end}}.
    (HOLD5 / "splits.json").write_text(json.dumps({
        "holdout5": {"start": args.start, "end": args.end},
    }, indent=2))

    lock_dataset(di)


if __name__ == "__main__":
    main()