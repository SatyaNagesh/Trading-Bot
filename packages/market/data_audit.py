"""Reproducible dataset audit + cleansing.

Reads every file recorded in the ingestion manifest, optionally quarantines
invalid bars (``data_quality.quarantine_rows``), runs the full DataFrame-level
quality validation (``data_quality.validate_dataset``), and writes
``data/historical/audit.json`` plus (when cleansing) a quarantine log.

Usage:
  python -m packages.market.data_audit --cleanse
  python -m packages.market.data_audit --out data/historical/audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import pandas as pd

from packages.market.data_ingestion import (
    checksum,
    load_failed,
    load_manifest,
    save_manifest,
    store_root,
)
from packages.market.data_quality import quarantine_rows, validate_dataset

QUARANTINE_LOG = "data/historical/quarantine.json"


def cleanse() -> dict[str, list[dict]]:
    manifest = load_manifest()
    log: dict[str, list[dict]] = {"removed": [], "kept_special_sessions": []}
    updated = []
    for entry in manifest:
        path = store_root() / str(entry["file"])
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if getattr(df.index, "tz", None) is None and "ts" in df.columns:
            df = df.set_index("ts")
        clean, removed = quarantine_rows(df, entry["timeframe"])
        if removed:
            for r in removed:
                r["symbol"] = entry["symbol"]
                r["timeframe"] = entry["timeframe"]
                r["file"] = entry["file"]
            log["removed"].extend(removed)
            clean.to_parquet(path)
        entry["sha256"] = checksum(path)
        entry["cleanse_utc"] = datetime.now(timezone.utc).isoformat()
        updated.append(entry)
    save_manifest(updated)
    return log


def run_audit() -> dict:
    manifest = load_manifest()
    failed = load_failed()
    datasets = []
    rejected = []

    for entry in manifest:
        path = store_root() / str(entry["file"])
        if not path.exists():
            rejected.append({"symbol": entry["symbol"], "timeframe": entry["timeframe"],
                             "reason": "file missing"})
            continue
        try:
            df = pd.read_parquet(path)
            if getattr(df.index, "tz", None) is None and "ts" in df.columns:
                df = df.set_index("ts")
        except Exception as e:  # noqa: BLE001
            rejected.append({"symbol": entry["symbol"], "timeframe": entry["timeframe"],
                             "reason": f"unreadable: {e}"})
            continue
        report = validate_dataset(df, entry["symbol"], entry["timeframe"])
        report["sha256_ok"] = checksum(path) == entry.get("sha256")
        report["actual_start"] = str(df.index[0])
        report["actual_end"] = str(df.index[-1])
        datasets.append(report)

    overall = Counter(r["overall"] for r in datasets)
    by_tf = defaultdict(Counter)
    for r in datasets:
        by_tf[r["timeframe"]][r["overall"]] += 1

    audit = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance (auto_adjust=True)",
        "datasets_expected": len(manifest),
        "datasets_validated": len(datasets),
        "rejected": rejected,
        "failed_ingestion": failed,
        "quality_summary": {
            "overall": dict(overall),
            "by_timeframe": {tf: dict(c) for tf, c in by_tf.items()},
        },
        "datasets": datasets,
        "deficiencies": {
            "intraday_depth": "yfinance serves only last ~5-7 sessions (1m) and ~55 days (15m) "
                               "for NSE; no 6-12 month intraday history available.",
            "daily_holidays": "missing business days in daily series are expected NSE holidays "
                              "(flagged WARN, not FAIL).",
        },
    }
    return audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanse", action="store_true", help="quarantine invalid bars first")
    ap.add_argument("--out", default="data/historical/audit.json")
    args = ap.parse_args()

    if args.cleanse:
        log = cleanse()
        Path(QUARANTINE_LOG).write_text(json.dumps(log, indent=2, default=str))
        print(f"cleansed: {len(log['removed'])} bars quarantined -> {QUARANTINE_LOG}")

    audit = run_audit()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2, default=str))
    print(f"wrote {out}")
    print("quality_summary.overall:", audit["quality_summary"]["overall"])
    for r in audit["rejected"]:
        print("  REJECTED:", r)
    sys.stdout.flush()


if __name__ == "__main__":
    main()