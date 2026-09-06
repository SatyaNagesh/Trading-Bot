"""holdout_2 universe selection: pre-registered, return-independent.

Pre-registered rule (recorded in reports/..._PRE_REGISTRATION_*.md before any
price-history download or transform evaluation):

  1. Candidate pool CAND2 = REMAINING_FROZEN_POOL (frozen `select_holdout_universe`
     pool entries that were neither selected into HOLDOUT nor dropped as
     resolution failures) UNION SUPP2 (static NSE mid/large-cap list below).
  2. Every candidate MUST be disjoint from DEVELOPMENT(49) and HOLDOUT(60);
     asserted at runtime.
  3. Rank candidates by Yahoo fast_info['marketCap'] at the selection instant.
     Ranking uses NO price-history returns.
  4. Select the top 40 by market cap (ties alphabetized). Symbols that fail to
     resolve (bad ticker / no marketCap) are dropped and logged - NO
     return-based substitution.
  5. The selected universe + rule + snapshot are written to universe.json.
     Any later price-history fetch / transform evaluation may ONLY use this set.

This module performs universe selection only. It does not download price history.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

REMAINING_FROZEN_POOL = [
    "ACC.NS", "ANGELONE.NS", "APOLLOTYRE.NS", "BATAINDIA.NS", "CDSL.NS",
    "CEATLTD.NS", "DEVYANI.NS", "JYOTHYLAB.NS", "PGHH.NS", "RAILTEL.NS",
    "TATACHEM.NS", "TATAELXSI.NS",
]

SUPP2 = [
    "ABB.NS", "AARTIIND.NS", "ABCAPITAL.NS", "ABFRL.NS", "ABBOTINDIA.NS",
    "AMBER.NS", "APLAPOLLO.NS", "APTUS.NS", "ASTRAL.NS", "ATGL.NS",
    "ATUL.NS", "AUTHUM.NS", "AVENTUS.NS", "BAJAJELEC.NS", "BALRAMCHIN.NS",
    "BANDHANBNK.NS", "BANKINDIA.NS", "BERGEPAINT.NS", "BSE.NS",
    "CANFINHOME.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", "CROMPTON.NS",
    "EXIDEIND.NS", "FEDERALBNK.NS", "GLENMARK.NS", "GODFRYPHLP.NS",
    "GUJGASLTD.NS", "HONAUT.NS", "HUDCO.NS", "IDBI.NS", "IDFC.NS", "IEX.NS",
    "INDIGO.NS", "IOC.NS", "IPCA.NS", "JSWENERGY.NS", "KAJARIACER.NS",
    "KALYANKJIL.NS", "LICHSGFIN.NS", "LICI.NS", "LODHA.NS", "MAXHEALTH.NS",
    "METROPOLIS.NS", "MOTILALOFS.NS", "NAMINDIA.NS", "NATCOPHARM.NS",
    "NAVINFLUOR.NS", "NMDC.NS", "OIL.NS", "PCBL.NS", "PETRONET.NS",
    "PIIND.NS", "RAMCOCEM.NS", "SBICARD.NS", "SRF.NS", "SUNDARMFIN.NS",
    "SYNGENE.NS", "TIINDIA.NS", "TORNTPOWER.NS", "UBL.NS", "UPL.NS",
    "WHIRLPOOL.NS", "ZENTEC.NS",
]

N_SELECT = 40
OUT = Path("data/holdout_2/universe.json")


def dev_symbols() -> list[str]:
    with open("data/historical/manifest.json") as fh:
        return sorted({rec["symbol"] for rec in json.load(fh)})


def holdout_symbols() -> list[str]:
    with open("data/holdout/universe.json") as fh:
        return json.load(fh)["selected"]


def market_cap(symbol: str, retries: int = 2) -> dict:
    import yfinance as yf

    for attempt in range(retries):
        try:
            t = yf.Ticker(symbol)
            cap = t.fast_info.get("marketCap")
            if cap is None or not cap:
                return {"symbol": symbol, "market_cap_usd": None, "error": "no marketCap"}
            return {"symbol": symbol, "market_cap_usd": float(cap), "error": None}
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                return {"symbol": symbol, "market_cap_usd": None, "error": str(e)[:160]}
            time.sleep(2 * (attempt + 1))
    return {"symbol": symbol, "market_cap_usd": None, "error": "retries exhausted"}


def main() -> None:
    cand = REMAINING_FROZEN_POOL + SUPP2
    dev = set(dev_symbols())
    ho = set(holdout_symbols())
    assert not (set(cand) & dev), "candidates overlap DEVELOPMENT universe"
    assert not (set(cand) & ho), "candidates overlap HOLDOUT universe"
    snapshot_utc = datetime.now(timezone.utc).isoformat()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(market_cap, sym): sym for sym in cand}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            print(f"  {i:>3}/{len(cand)} {r['symbol']:16s} "
                  f"cap={r['market_cap_usd']!r} "
                  f"{('ERR:'+r['error'][:60]) if r['error'] else ''}",
                  flush=True)

    resolvable = [r for r in rows if not r["error"]]
    ranked = sorted(resolvable, key=lambda r: (-r["market_cap_usd"], r["symbol"]))
    selected = ranked[:N_SELECT]
    selected_syms = [r["symbol"] for r in selected]

    out = {
        "snapshot_utc": snapshot_utc,
        "rule": (
            "top-40 by Yahoo fast_info['marketCap'] snapshot at selection instant; "
            "ties alphabetized; candidate pool predetermined (remaining frozen "
            "holdout pool + static supplement) and disjoint from DEVELOPMENT and "
            "HOLDOUT; NO price-history/return information used for selection; "
            "failures dropped without substitution"
        ),
        "n_select": N_SELECT,
        "n_candidates": len(cand),
        "resolved": len(resolvable),
        "remaining_frozen_pool": REMAINING_FROZEN_POOL,
        "supplement": SUPP2,
        "failures": [r["symbol"] for r in rows if r["error"]],
        "failure_reasons": rows,
        "selected": selected_syms,
        "selected_with_caps": selected,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}: selected {len(selected_syms)} symbols")


if __name__ == "__main__":
    main()