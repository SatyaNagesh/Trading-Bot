"""Holdout universe selection: pre-registered, return-independent.

Rule (frozen before any price-history download or evaluation):
  1. Candidate pool = predetermined NSE large/mid-cap tickers NOT among the
     49 DEVELOPMENT symbols, listed statically below.
  2. Rank candidates by Yahoo fast_info['marketCap'] (a snapshot at the
     selection instant). Ranking uses NO price-history returns.
  3. Select the top {N} by market cap (ties alphabetized). Symbols that fail
     to resolve (bad ticker / no marketCap) are dropped and logged — no
     return-based substitution.
  4. The selected universe + rule + snapshot are written to universe.json.
     Any later price-history fetch / evaluation may ONLY use this selected set.

This module performs universe selection only. It does not download price history.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

DEV_SYMBOLS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJFINSV.NS", "BAJAJ_AUTO.NS", "BAJFINANCE.NS",
    "BEL.NS", "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "INDUSINDBK.NS", "INFY.NS", "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS",
    "LT.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS",
]

# static candidate pool: NSE large/mid caps, no overlap with DEV_SYMBOLS
POOL = [
    "ACC.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBUJACEM.NS",
    "ANGELONE.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "AUROPHARMA.NS",
    "BALKRISIND.NS", "BANKBARODA.NS", "BATAINDIA.NS", "BHARATFORG.NS",
    "BHEL.NS", "BLUESTARCO.NS", "CANBK.NS", "CDSL.NS", "CEATLTD.NS",
    "COFORGE.NS", "CONCOR.NS", "CUMMINSIND.NS", "DABUR.NS", "DEVYANI.NS",
    "DIXON.NS", "DLF.NS", "DMART.NS", "GAIL.NS", "GODREJCP.NS",
    "GODREJPROP.NS", "HAVELLS.NS", "HINDZINC.NS", "IDFCFIRSTB.NS",
    "INDIAMART.NS", "INDIANB.NS", "IRCTC.NS", "IRFC.NS", "JINDALSTEL.NS",
    "JUBLFOOD.NS", "JYOTHYLAB.NS", "KEI.NS", "LTIM.NS", "LUPIN.NS",
    "MARICO.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "NHPC.NS",
    "OBEROIRLTY.NS", "PAGEIND.NS", "PERSISTENT.NS", "PFC.NS", "PGHH.NS",
    "PNB.NS", "POLYCAB.NS", "PRESTIGE.NS", "RAILTEL.NS", "RECLTD.NS",
    "SAIL.NS", "SIEMENS.NS", "TATACHEM.NS", "TATACOMM.NS", "TATACONSUM.NS",
    "TATAELXSI.NS", "TATAMOTORS.NS", "TATAMTRDVR.NS", "TATAPOWER.NS",
    "THERMAX.NS", "TORNTPHARM.NS", "TVSMOTOR.NS", "UNIONBANK.NS", "VBL.NS",
    "VEDL.NS", "VOLTAS.NS", "YESBANK.NS", "ZOMATO.NS", "ZYDUSLIFE.NS",
]

N_SELECT = 60
OUT = Path("data/holdout/universe.json")


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
    assert not set(POOL) & set(DEV_SYMBOLS), "pool overlaps development universe"
    snapshot_utc = datetime.now(timezone.utc).isoformat()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(market_cap, sym): sym for sym in POOL}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            print(f"  {i:>3}/{len(POOL)} {r['symbol']:16s} "
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
            "top-N by Yahoo fast_info['marketCap'] snapshot at selection instant; "
            "ties alphabetized; pool predetermined and disjoint from DEVELOPMENT; "
            "NO price-history/return information used for selection; "
            "failures dropped without substitution"
        ),
        "dev_excluded": sorted(DEV_SYMBOLS),
        "pool": sorted(POOL),
        "n_pool": len(POOL),
        "n_selected": N_SELECT,
        "resolved": len(resolvable),
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