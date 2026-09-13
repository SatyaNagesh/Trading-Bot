"""holdout_4 universe selection: pre-registered, return-independent.

Phase 12C. Same protocol as holdout-3 but for the strategy-level holdout-4.

  1. Candidate pool POOL4 = predetermined NSE large/mid-cap tickers below,
     statically listed and NOT present in any previously-used corpus.
  2. Used set USED = union of DEVELOPMENT + HOLDOUT + HOLDOUT_2 + HOLDOUT_3;
     asserted disjoint from POOL4 at runtime (unexpected overlap excluded and
     logged BEFORE ranking - no return info involved).
  3. Rank candidates by Yahoo fast_info['marketCap'] snapshot at selection
     instant (NO price-history returns used).
  4. Select the top N by market cap (ties alphabetized). Symbols that fail to
     resolve are dropped and logged - NO return-based substitution.
  5. Selected universe + rule + snapshot written to universe.json BEFORE any
     download; any later fetch/evaluation may ONLY use this set.

Selection only; does not download price history.

Usage: python -m packages.research.select_holdout4_universe
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

N_SELECT = 40
OUT = Path("data/holdout_4/universe.json")

# Static tranche-4 candidate pool: NSE names NOT in DEVELOPMENT/HOLDOUT/
# HOLDOUT_2/HOLDOUT_3. Runtime guard re-checks; unexpected overlap excluded+logged.
POOL4 = [
    "AARTIIND.NS", "ABB.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS",
    "ACE.NS", "ADANIENSOL.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "AJANTPHARM.NS",
    "ALKEM.NS", "AMBER.NS", "AMBUJACEM.NS", "APLAPOLLO.NS", "APOLLOTYRE.NS",
    "ARE&M.NS", "ASHOKLEY.NS", "ATGL.NS", "AUROPHARMA.NS", "AVANTEL.NS",
    "BANKBARODA.NS", "BASF.NS", "BATAINDIA.NS", "BERGEPAINT.NS", "BIOCON.NS",
    "BOSCHLTD.NS", "CGPOWER.NS", "CHAMBLFERT.NS", "CHOLAHLDNG.NS", "CIEINDIA.NS",
    "COLPAL.NS", "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DALBHARAT.NS", "DIXON.NS", "DLF.NS", "DMART.NS", "EASEMYTRIP.NS",
    "EXIDEIND.NS", "FEDERALBNK.NS", "FORTIS.NS", "GAIL.NS", "GLENMARK.NS",
    "GODREJCP.NS", "GODREJPROP.NS", "GODREJIND.NS", "GUJGASLTD.NS", "HAL.NS",
    "HAVELLS.NS", "HINDCOPPER.NS", "HINDZINC.NS", "IDBI.NS", "IDEA.NS",
    "IDFC.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS", "INDIGO.NS",
    "INDIAMART.NS", "INDIANB.NS", "INDIANHOTEL.NS", "INDIGOPNTS.NS", "INTERGLBEV.NS",
    "IPCALAB.NS", "IRCTC.NS", "IRFC.NS", "JINDALSTEL.NS", "JIOFIN.NS",
    "JUBLFOOD.NS", "JYOTHYLAB.NS", "KALPATPOWR.NS", "KPIL.NS", "LICI.NS",
    "LODHA.NS", "LTIM.NS", "LUPIN.NS", "LTTS.NS",
    "M&MFIN.NS", "MFSL.NS", "MGL.NS", "MOTHERSON.NS",
    "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS",
    "NCC.NS", "NHPC.NS", "NMDC.NS", "OIL.NS",
    "PAGEIND.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", "PIDILITIND.NS",
    "PIIND.NS", "PNB.NS", "POLICYBZR.NS", "POLYCAB.NS", "POWERINDIA.NS",
    "PRESTIGE.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RECLTD.NS", "SKFINDIA.NS",
    "SAIL.NS", "SIEMENS.NS", "SJVN.NS", "SRF.NS",
    "SRTRANSFIN.NS", "STARHEALTH.NS", "SUNDARMFIN.NS", "SUNTV.NS", "SYNGENE.NS",
    "TATACHEM.NS", "TATAELXSI.NS", "TATAMOTORS.NS", "TATAPOWER.NS",
    "TORNTPHARM.NS", "TORNTPOWER.NS", "TVSMOTOR.NS",
    "UPL.NS", "VEDL.NS", "VOLTAS.NS", "ZOMATO.NS", "ZYDUSLIFE.NS",
]


def used_symbols() -> set[str]:
    out: set[str] = set()
    out |= {r["symbol"] for r in json.load(open("data/historical/manifest.json"))}
    out |= set(json.load(open("data/holdout/universe.json"))["selected"])
    out |= {r["symbol"] for r in json.load(open("data/holdout_2/manifest.json"))}
    out |= set(json.load(open("data/holdout_3/universe.json"))["selected"])
    return out


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
    used = used_symbols()
    overlap = sorted(set(POOL4) & used)
    pool = [s for s in POOL4 if s not in used]
    assert len(pool) >= N_SELECT, (
        f"pool after overlap exclusion ({len(pool)}) < N_SELECT ({N_SELECT})")
    snapshot_utc = datetime.now(timezone.utc).isoformat()
    print(f"pool={len(pool)}  overlap_excluded={len(overlap)} {overlap}")

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(market_cap, sym): sym for sym in pool}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            print(f"  {i:>3}/{len(pool)} {r['symbol']:16s} cap={r['market_cap_usd']!r} "
                  f"{('ERR:'+r['error'][:60]) if r['error'] else ''}", flush=True)

    resolvable = [r for r in rows if not r["error"]]
    if len(resolvable) < N_SELECT:
        print(f"ABORT: only {len(resolvable)} resolvable vs N_SELECT={N_SELECT}; "
              "no return-based substitution allowed")
        sys.exit(1)
    ranked = sorted(resolvable, key=lambda r: (-r["market_cap_usd"], r["symbol"]))
    selected = ranked[:N_SELECT]
    selected_syms = [r["symbol"] for r in selected]

    out = {
        "phase": "holdout4_strategy_confirmation",
        "snapshot_utc": snapshot_utc,
        "rule": (
            "top-40 by Yahoo fast_info['marketCap'] snapshot at selection instant; "
            "ties alphabetized; candidate pool predetermined (static tranche-4 NSE "
            "list) and disjoint from DEVELOPMENT + HOLDOUT + HOLDOUT_2 + HOLDOUT_3; "
            "NO price-history/return information used for selection; failures dropped "
            "without substitution"
        ),
        "n_select": N_SELECT,
        "n_pool": len(pool),
        "overlap_excluded": overlap,
        "resolved": len(resolvable),
        "failures": [r["symbol"] for r in rows if r["error"]],
        "failure_reasons": rows,
        "selected": selected_syms,
        "selected_with_caps": selected,
        "used_corpora": {
            "development": sorted({r["symbol"] for r in json.load(open("data/historical/manifest.json"))}),
            "holdout": json.load(open("data/holdout/universe.json"))["selected"],
            "holdout_2": sorted({r["symbol"] for r in json.load(open("data/holdout_2/manifest.json"))}),
            "holdout_3": json.load(open("data/holdout_3/universe.json"))["selected"],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}: selected {len(selected_syms)} symbols")


if __name__ == "__main__":
    main()