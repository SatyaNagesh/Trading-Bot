"""FROZEN HOLDOUT acquisition — Phase 2 of the independent-holdout plan.

Reuses the frozen ingestion/audit code verbatim; only the data store root is
injected (data/holdout). No algorithmic change. Selection of symbols comes
exclusively from the pre-registered data/holdout/universe.json.

Usage:
  python -m packages.research.acquire_holdout            # fetch + audit
  python -m packages.research.acquire_holdout --verify   # checksum audit only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

HOLD = Path("data/holdout")


def _wire() -> tuple:
    import packages.market.data_audit as da
    import packages.market.data_ingestion as di

    di.store_root = lambda: HOLD
    da.store_root = di.store_root
    da.QUARANTINE_LOG = str(HOLD / "quarantine.json")
    return di, da


def run_acquire(di, start: str, end: str, sleep: float) -> None:
    univ = json.loads((HOLD / "universe.json").read_text())
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default="2026-09-05")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--audit-only", action="store_true")
    args = ap.parse_args()

    di, da = _wire()

    import packages.market.data_ingestion as _di
    HOLD.mkdir(parents=True, exist_ok=True)

    if args.verify:
        changed = di.verify_manifest()
        print("VERIFY:", changed if changed else "all checksums match")
        return

    if not args.audit_only:
        run_acquire(di, args.start, args.end, args.sleep)

    # cleanse + audit (frozen logic)
    log = da.cleanse()
    (HOLD / "quarantine.json").write_text(json.dumps(log, indent=2, default=str))
    audit = da.run_audit()
    (HOLD / "audit.json").write_text(json.dumps(audit, indent=2, default=str))
    print("audit overall:", audit["quality_summary"]["overall"])

    # daily quality gate (frozen rule: daily bars >= 700)
    kept, dropped = [], []
    for entry in di.load_manifest():
        if entry.get("bars", 0) >= 700:
            kept.append(entry["symbol"])
        else:
            dropped.append({"symbol": entry["symbol"], "bars": entry.get("bars")})
    (HOLD / "eligible_symbols.json").write_text(
        json.dumps({"kept": sorted(kept), "dropped": dropped}, indent=2))
    print(f"eligible (bars>=700): {len(kept)}  dropped: {len(dropped)}")


if __name__ == "__main__":
    main()