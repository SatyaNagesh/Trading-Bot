"""Rebuild the DEVELOPMENT corpus parquet from the frozen source spec.

The DEVELOPMENT price parquet files were lost with the /tmp workspace (they
are gitignored). This re-acquires the same 49 symbols / same range via the
frozen ingestion path (yfinance 1.7.0, auto_adjust=True, 1d, Asia/Kolkata)
into `data/historical/d1d/`. It writes its own `reacquire_manifest.json`
and does NOT mutate the original `manifest.json` provenance record.

Purpose: Phase-1 exact reproduction of the frozen vol_trend_10v50 IC on the
DEVELOPMENT corpus, and a clean DEVELOPMENT/VALIDATION panel for defining
pre-specified monetization transforms. Does not touch `data/holdout/`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

REACQ = Path("data/historical/reacquire_manifest.json")


def main() -> None:
    import packages.market.data_ingestion as di

    # default store root IS data/historical; leave it alone
    symbols = sorted({e["symbol"] for e in di.load_manifest() if e["timeframe"] == "d1d"})
    print(f"re-acquiring {len(symbols)} DEVELOPMENT d1d symbols from manifest spec")
    records, failures = [], []
    for i, sym in enumerate(symbols, 1):
        try:
            rec = di.acquire_symbol(sym, "d1d", "2014-01-01", "2026-09-05",
                                    refresh=True)
            records.append(rec)
            print(f"  OK  {i:>2}/{len(symbols)} {sym:16s} bars={rec['bars']:>5} "
                  f"{rec['actual_start'][:10]} -> {rec['actual_end'][:10]}",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            failures.append({"symbol": sym, "error": str(e)[:150]})
            print(f"  ERR {i:>2}/{len(symbols)} {sym:16s} {e}", flush=True)
        time.sleep(0.25)
    REACQ.write_text(json.dumps(
        {"entries": records, "failures": failures,
         "note": "re-acquisition for Phase-1 reproduction; original manifest.json untouched"},
        indent=2, default=str))
    print(f"done: {len(records)} ok, {len(failures)} failed -> {REACQ}")


if __name__ == "__main__":
    main()