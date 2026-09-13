"""holdout_5 universe selection: pre-registered, return-independent, Phase 12.

Same protocol as holdout_4 (top-40 by market cap) but for COMP3 STRATEGY V2
(diversified D1 + D2 confirmation).

  1. Candidate pool POOL5 = predetermined NSE large/mid-cap tickers below,
     statically listed and disjoint from every previously-used corpus
     (DEVELOPMENT + HOLDOUT + HOLDOUT_2 + HOLDOUT_3 + HOLDOUT_4).
  2. Used set USED is recomputed at runtime; unexpected overlap is excluded
     and logged BEFORE ranking (no return info involved).
  3. Rank candidates by Yahoo fast_info['marketCap'] snapshot at selection
     instant (NO price-history returns used).
  4. Select the top N by market cap (ties alphabetized). Symbols that fail to
     resolve are dropped and logged - NO return-based substitution.
  5. Selected universe written to data/holdout_5/universe.json BEFORE any
     download; any later fetch/evaluation may ONLY use this set.

Selection only; does not download price history.

Usage: python -m packages.research.select_holdout5_universe
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
OUT = Path("data/holdout_5/universe.json")

# Static tranche-5 candidate pool: NSE large/mid-cap names NOT in
# DEVELOPMENT/HOLDOUT/HOLDOUT_2/HOLDOUT_3/HOLDOUT_4. Runtime guard re-checks;
# unexpected overlap excluded+logged (no substitution).
POOL5 = [
    "APARINDS.NS", "ASTRAL.NS", "BAJAJELEC.NS", "BANDHANBNK.NS", "BIRLACORPN.NS",
    "BRIGADE.NS", "CENTRALBK.NS", "CESC.NS", "CRAFTSMAN.NS", "CREDITACC.NS",
    "CUB.NS", "CYIENT.NS", "DELHIVERY.NS", "DEVYANI.NS", "EIDPARRY.NS",
    "ENGINERSIN.NS", "FINEORG.NS", "FSL.NS", "GILLETTE.NS", "GMRINFRA.NS",
    "GODREJAGRO.NS", "GRAPHITE.NS", "HATSUN.NS", "HOMEFIRST.NS", "INFIBEAM.NS",
    "IOB.NS", "IRB.NS", "ISEC.NS", "JAMNAAUTO.NS", "KANSAINER.NS",
    "KARURVYSYA.NS", "KPITTECH.NS", "LAURUSLABS.NS", "LATENTVIEW.NS", "LTF.NS",
    "MCDOWELL-N.NS", "NATCOPHARM.NS", "NBCC.NS", "NIACL.NS", "NLCINDIA.NS",
    "PRAJIND.NS", "RAILTEL.NS", "RALLIS.NS", "RVNL.NS", "SKIPPER.NS",
    "SOUTHBANK.NS", "SUZLON.NS", "TEJASNET.NS", "TITAGARH.NS",
    "TRIDENT.NS", "UCOBANK.NS", "VGUARD.NS", "VINATIORGA.NS", "WELSPUNLIV.NS",
    "ZENSARTECH.NS", "ASTERDM.NS", "RELAXO.NS", "RAYMOND.NS", "MEDPLUS.NS",
    "SWSOLAR.NS", "EMIL.NS", "GENSOL.NS",
]


def used_symbols() -> set[str]:
    out: set[str] = set()
    out |= {r["symbol"] for r in json.load(open("data/historical/manifest.json"))}
    out |= set(json.load(open("data/holdout/universe.json"))["selected"])
    out |= {r["symbol"] for r in json.load(open("data/holdout_2/manifest.json"))}
    out |= set(json.load(open("data/holdout_3/universe.json"))["selected"])
    out |= set(json.load(open("data/holdout_4/universe.json"))["selected"])
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
    overlap = sorted(set(POOL5) & used)
    pool = [s for s in POOL5 if s not in used]
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
        "phase": "holdout5_comp3_v2_confirmation",
        "snapshot_utc": snapshot_utc,
        "rule": (
            "top-40 by Yahoo fast_info['marketCap'] snapshot at selection instant; "
            "ties alphabetized; candidate pool predetermined (static tranche-5 NSE "
            "list) and disjoint from DEVELOPMENT + HOLDOUT + HOLDOUT_2 + HOLDOUT_3 "
            "+ HOLDOUT_4; NO price-history/return information used for selection; "
            "failures dropped without substitution"
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
            "holdout_1": sorted(json.load(open("data/holdout/universe.json"))["selected"]),
            "holdout_2": sorted({r["symbol"] for r in json.load(open("data/holdout_2/manifest.json"))}),
            "holdout_3": sorted(json.load(open("data/holdout_3/universe.json"))["selected"]),
            "holdout_4": sorted(json.load(open("data/holdout_4/universe.json"))["selected"]),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"selected {len(selected_syms)} -> {OUT}")


if __name__ == "__main__":
    main()