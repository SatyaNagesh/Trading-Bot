"""Reproducible historical market-data acquisition via yfinance.

Builds a curated, provenance-tracked dataset store under ``data/historical/``
with one parquet file per symbol per timeframe plus a machine-readable
``manifest.json`` recording source, retrieval time, requested vs actual range,
timezone, adjustment status, bar counts and per-file SHA-256 checksums so that
the dataset can be verified or re-acquired at any time.

Timeframes supported:
  * ``d1d`` - daily (multi-year; full depth available)
  * ``1m``  - 1 minute (yfinance limit: ~ last 5-7 sessions for NSE)
  * ``15m`` - 15 minute (yfinance limit: ~ last 60 calendar days for NSE)

Usage:
  python -m packages.market.ingest_historical --universe nifty50 \\
      --start 2014-01-01 --end 2026-09-04 [--intraday-symbols RELIANCE,TCS]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

import pandas as pd

from packages.market.data_pipeline import get_available_symbols

logger = logging.getLogger("data_ingestion")

SOURCE = "yfinance"
TZ = "Asia/Kolkata"
YF_INTERVALS = {"d1d": "1d", "1m": "1m", "15m": "15m"}
ADJUSTED = True


def store_root() -> Path:
    return Path("data/historical")


def tf_dir(tf: str) -> Path:
    return store_root() / tf


def file_for(symbol: str, tf: str) -> Path:
    base = symbol.replace(".", "_")
    return tf_dir(tf) / f"{base}.parquet"


def _siblings(symbol: str) -> tuple[str, str]:
    yf_ticker = symbol.replace("_", "-") if symbol.endswith(".NS") else symbol
    return symbol, yf_ticker


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    keep = {"open", "high", "low", "close", "volume"}
    keep |= {"dividends", "stock splits"} & set(df.columns)
    missing = keep - set(df.columns)
    if missing:
        raise ValueError(f"{symbol}: missing columns {sorted(missing)}")
    df = df[list(keep)]
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize(TZ)
    else:
        df.index = df.index.tz_convert(TZ)
    df.index.name = "ts"
    return df.sort_index()


def fetch_ohlcv(
    yf_ticker: str,
    interval: str,
    start: str | date,
    end: str | date,
    symbol: str,
    retries: int = 3,
    backoff: float = 2.0,
) -> pd.DataFrame:
    import yfinance as yf

    kwargs: dict[str, Any] = {"interval": interval, "auto_adjust": ADJUSTED}
    if interval == "1d":
        kwargs.update(start=start, end=end)
    else:
        kwargs.update(start=start, end=end)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            df = yf.Ticker(yf_ticker).history(**kwargs)
            if df is not None and not df.empty:
                return _normalize(df, symbol)
            raise ValueError(f"empty response for {symbol}")
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning(
                "attempt_failed", extra={"symbol": symbol, "attempt": attempt + 1, "error": str(e)}
            )
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"failed to fetch {symbol} after {retries} attempts: {last_err}")


def manifest_path() -> Path:
    return store_root() / "manifest.json"


def failed_path() -> Path:
    return store_root() / "failed.json"


def load_manifest() -> list[dict[str, Any]]:
    if manifest_path().exists():
        return json.loads(manifest_path().read_text())
    return []


def save_manifest(entries: list[dict[str, Any]]) -> None:
    manifest_path().parent.mkdir(parents=True, exist_ok=True)
    manifest_path().write_text(json.dumps(entries, indent=2, default=str))


def load_failed() -> list[dict[str, Any]]:
    if failed_path().exists():
        return json.loads(failed_path().read_text())
    return []


def save_failed(entries: list[dict[str, Any]]) -> None:
    failed_path().parent.mkdir(parents=True, exist_ok=True)
    failed_path().write_text(json.dumps(entries, indent=2, default=str))


def intraday_range(tf: str, end: str | date) -> tuple[str, str]:
    from datetime import timedelta

    e = date.fromisoformat(str(end)) if isinstance(end, str) else end
    if tf == "1m":
        s = (e - timedelta(days=6)).isoformat()
    else:
        s = (e - timedelta(days=55)).isoformat()
    return s, str(e)


def acquire_symbol(
    symbol: str,
    tf: str,
    start: str | date,
    end: str | date,
    refresh: bool = False,
) -> dict[str, Any]:
    canonical, yf_ticker = _siblings(symbol)
    out = file_for(canonical, tf)
    record = {"symbol": canonical, "timeframe": tf, "source": SOURCE,
              "interval": YF_INTERVALS[tf]}
    if out.exists() and not refresh:
        entry = _find_manifest(canonical, tf)
        if entry is not None:
            logger.info("already_present", extra={"symbol": canonical, "tf": tf})
            return entry
    req_start, req_end = (intraday_range(tf, end) if tf != "d1d" else (str(start), str(end)))
    df = fetch_ohlcv(yf_ticker, YF_INTERVALS[tf], req_start, req_end, canonical)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    record.update(
        {
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "requested_start": str(start),
            "requested_end": str(end),
            "intraday_requested_start": (req_start if tf != "d1d" else None),
            "actual_start": df.index[0].isoformat(),
            "actual_end": df.index[-1].isoformat(),
            "bars": int(len(df)),
            "first_close": float(df["close"].iloc[0]),
            "last_close": float(df["close"].iloc[-1]),
            "timezone": str(df.index.tz),
            "adjusted": ADJUSTED,
            "adjustment_notes": "auto_adjust=True (splits + dividends)",
            "yfinance_version": _yf_version(),
            "file": str(out.relative_to(store_root())),
            "sha256": checksum(out),
            "quality": "PENDING",
        }
    )
    return record


def _yf_version() -> str:
    try:
        import yfinance
        return getattr(yfinance, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


def _find_manifest(symbol: str, tf: str) -> dict[str, Any] | None:
    for entry in load_manifest():
        if entry.get("symbol") == symbol and entry.get("timeframe") == tf:
            return entry
    return None


def verify_manifest() -> list[dict[str, Any]]:
    changed = []
    for entry in load_manifest():
        path = store_root() / str(entry["file"])
        if path.exists():
            current = checksum(path)
            if current != entry.get("sha256"):
                changed.append({"symbol": entry["symbol"], "tf": entry["timeframe"],
                                "expected": entry["sha256"], "actual": current})
    return changed


def collect_manifest(records: list[dict[str, Any]]) -> None:
    existing = [e for e in load_manifest() if (e["symbol"], e["timeframe"])
                not in {(r["symbol"], r["timeframe"]) for r in records}]
    save_manifest(existing + records)


def main() -> None:
    ap = argparse.ArgumentParser(description="Acquire reproducible historical market data.")
    ap.add_argument("--universe", default="nifty50", choices=["nifty50", "core"])
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-09-05")
    ap.add_argument("--intraday-symbols", default="RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK,TATAMOTORS")
    ap.add_argument("--refresh", action="store_true", help="re-download even if present")
    ap.add_argument("--sleep", type=float, default=0.4, help="seconds between requests")
    ap.add_argument("--verify", action="store_true", help="verify checksums, then exit")
    args = ap.parse_args()

    if args.verify:
        changed = verify_manifest()
        if changed:
            print("VERIFY FAILED (checksum mismatch):")
            for c in changed:
                print(" ", c)
            sys.exit(1)
        print(f"VERIFY OK: {len(load_manifest())} entries, all checksums match")
        return

    universes = {"core": ["RELIANCE", "TCS"], "nifty50": get_available_symbols()}
    daily_symbols = universes[args.universe]
    intraday_symbols = [s.strip() for s in args.intraday_symbols.split(",") if s.strip()]

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    jobs: list[tuple[str, str]] = []
    for sym in daily_symbols:
        jobs.append((sym, "d1d"))
    for sym in intraday_symbols:
        jobs.append((sym, "1m"))
        jobs.append((sym, "15m"))

    for sym, tf in jobs:
        canonical, _ = _siblings(sym if sym.endswith(".NS") else f"{sym}.NS")
        try:
            record = acquire_symbol(canonical, tf, args.start, args.end, args.refresh)
            records.append(record)
            print(f"  OK  {canonical:16s} {tf:4s} bars={record['bars']:>5} "
                  f"{record['actual_start'][:10]} -> {record['actual_end'][:10]}")
        except Exception as e:  # noqa: BLE001
            failures.append({"symbol": canonical, "timeframe": tf, "error": str(e),
                             "retrieved_utc": datetime.now(timezone.utc).isoformat()})
            print(f"  ERR {canonical:16s} {tf:4s} {e}")
        time.sleep(args.sleep)

    collect_manifest(records)
    save_failed(failures)
    print(f"\ndone: {len(records)} datasets acquired, {len(failures)} failures")
    print(f"store: {store_root()}")
    print(f"manifest: {manifest_path()}")


if __name__ == "__main__":
    main()