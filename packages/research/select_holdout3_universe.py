"""holdout_3 universe selection: pre-registered, return-independent.

Pre-registered rule (written to universe.json BEFORE any price-history download
or transform evaluation; the acquisition step runs only afterwards):

  1. Candidate pool POOL3 = predetermined NSE large/mid-cap tickers below,
     statically listed and NOT present in any previously-used corpus.
  2. Used set USED = union of
       - DEVELOPMENT  (data/historical/manifest.json symbols)
       - HOLDOUT      (data/holdout/universe.json selected)
       - HOLD_OUT_2   (data/holdout_2/manifest.json symbols)
     asserted disjoint from POOL3 at runtime (any unexpected overlap is
     excluded and logged BEFORE ranking - no return info involved).
  3. Rank candidates by Yahoo fast_info['marketCap'] snapshot at the selection
     instant. Ranking uses NO price-history returns.
  4. Select the top N by market cap (ties alphabetized). Symbols that fail to
     resolve (bad ticker / no marketCap) are dropped and logged - NO
     return-based substitution.
  5. Selected universe + rule + snapshot are written to universe.json. Any
     later price-history fetch / evaluation may ONLY use this set.

This module performs universe selection only. It does not download price history.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

# Static candidate pool: NSE large/mid caps NOT in DEVELOPMENT/HOLDOUT/HOLDOUT_2.
# The runtime guard below cross-checks against the actual used corpora; any
# overlap (unexpected) is excluded and logged before ranking.
POOL3 = [
    "3MINDIA.NS", "AARTIDRUGS.NS", "AARTIPHARM.NS", "AARTISURF.NS",
    "ALKYLAMINE.NS", "AMARAJABAT.NS", "ANURAS.NS", "ASAHIINDIA.NS",
    "ASTRAZEN.NS", "ATUL.NS", "AUBANK.NS", "AVANTIFEED.NS", "BALAMINES.NS",
    "BAYERCROP.NS", "BDL.NS", "BEML.NS", "BLSINTL.NS", "BOROLTD.NS",
    "BSOFT.NS", "CAMLINFINE.NS", "CASTROLIND.NS", "CENTURYPLY.NS", "CERA.NS",
    "CHEMPLASTS.NS", "CHENNPETRO.NS", "COCHINSHIP.NS", "COROMANDEL.NS",
    "CSBBANK.NS", "DATAPATNS.NS", "DEEPAKNTR.NS", "DELTACORP.NS", "EIDPARRY.NS",
    "EMCURE.NS", "ENDURANCE.NS", "ESCORTS.NS", "FINEORG.NS", "GESHIP.NS",
    "GMMPFAUDLR.NS", "GRANULES.NS", "GUFICBIO.NS", "HEG.NS", "HOMEFIRST.NS",
    "IIFL.NS", "INDHOTEL.NS", "INOXWIND.NS", "JBCHEPHARM.NS", "JKCEMENT.NS",
    "JINDALSAW.NS", "KANSAINER.NS", "KIMS.NS", "KPRMILL.NS", "KSB.NS",
    "LEMONTREE.NS", "MAHLIFE.NS", "MANAPPURAM.NS", "MAZDOCK.NS", "MCDOWELL-N.NS",
    "METROBRAND.NS", "MINDACORP.NS", "NEULANDLAB.NS", "NUVAMA.NS", "OFSS.NS",
    "PEL.NS", "POLYMED.NS", "RAJESHEXPO.NS", "RAYMOND.NS", "RBLBANK.NS",
    "RCF.NS", "REDINGTON.NS", "RITES.NS", "SANOFI.NS", "SCHAEFFLER.NS",
    "SONACOMS.NS", "SUMICHEM.NS", "SUPRAJIT.NS", "SUPREMEIND.NS", "TATACOMM.NS",
    "TEJASNET.NS", "TITAGARH.NS", "TTML.NS", "VARROC.NS", "VGUARD.NS",
    "VINATIORGA.NS", "WELCORP.NS", "ZENSARTECH.NS", "ZYDUSWELL.NS", "KAYNES.NS",
]

N_SELECT = 40
OUT = Path("data/holdout_3/universe.json")


def used_symbols() -> set[str]:
    out: set[str] = set()
    dev = json.load(open("data/historical/manifest.json"))
    out |= {r["symbol"] for r in dev}
    ho = json.load(open("data/holdout/universe.json"))
    out |= set(ho["selected"])
    ho2 = json.load(open("data/holdout_2/manifest.json"))
    out |= {r["symbol"] for r in ho2}
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
    overlap = sorted(set(POOL3) & used)
    pool = [s for s in POOL3 if s not in used]
    assert len(pool) >= N_SELECT, (
        f"pool after overlap exclusion ({len(pool)}) < N_SELECT ({N_SELECT})")
    snapshot_utc = datetime.now(timezone.utc).isoformat()
    print(f"pool={len(pool)}  overlap_excluded={len(overlap)} {overlap}")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(market_cap, sym): sym for sym in pool}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            print(f"  {i:>3}/{len(pool)} {r['symbol']:16s} "
                  f"cap={r['market_cap_usd']!r} "
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
        "snapshot_utc": snapshot_utc,
        "rule": (
            "top-40 by Yahoo fast_info['marketCap'] snapshot at selection instant; "
            "ties alphabetized; candidate pool predetermined (static tranche-3 NSE "
            "list) and disjoint from DEVELOPMENT + HOLDOUT + HOLDOUT_2; NO "
            "price-history/return information used for selection; failures dropped "
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
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}: selected {len(selected_syms)} symbols")


if __name__ == "__main__":
    main()