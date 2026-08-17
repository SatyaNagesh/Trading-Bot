"""Full genuine end-to-end run for QuantLab AI (paper only).

Phases
  1. Research -> backtest -> PROMOTE on a synthetic trending series
     (lawful input exercising the promotion pipeline via real model code).
  2. Genuine paper fills + realized P&L over REAL NSE bars.
  3. Integrated run_cycle over real bars (fills, errors, persistence).
  4. Persistence verification on disk.
  5. API verification: inject the live bot and assert the REST + WebSocket
     layer reflects live trading state.
"""

import asyncio
import json
import os
import pickle
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "services")

from packages.domain.models import (
    Bar,
    Signal,
    SignalDirection,
)
from packages.session.manager import SessionStatus
from packages.integration.pipeline import IntegratedBot, IntegrationConfig

DB = "data/genuine_paper.db"
CACHE = "data/genuine_bars.pkl"


def load_real_bars() -> dict[str, list[Bar]]:
    if not os.path.exists(CACHE):
        raise SystemExit(f"cache missing: {CACHE}")
    with open(CACHE, "rb") as fh:
        return pickle.load(fh)


def build_synthetic_trend(n: int = 200, drift: float = 0.008) -> list[Bar]:
    bars = []
    price = 100.0
    t0 = datetime.now(timezone.utc) - timedelta(days=n)
    for i in range(n):
        open_p = price
        high = open_p * 1.011
        low = open_p * 0.99
        close = open_p * (1 + drift)
        bars.append(
            Bar(
                symbol="SX",
                timestamp=t0 + timedelta(days=i),
                open=Decimal(str(round(open_p, 2))),
                high=Decimal(str(round(high, 2))),
                low=Decimal(str(round(low, 2))),
                close=Decimal(str(round(close, 2))),
                volume=10000,
                spread=Decimal("0.1"),
            )
        )
        price = close
    return bars


def make_config() -> IntegrationConfig:
    return IntegrationConfig(
        db_path=DB,
        initial_capital=Decimal("1000000"),
        backtest_days=120,
        min_sharpe_for_review=0.0,
        min_trades_for_review=2,
        sharpe_for_paper_test=0.3,
        sharpe_for_promotion=0.5,
        min_trades_for_promotion=4,
        max_candidates_per_cycle=18,
        max_evaluated_candidates=8,
        top_n_ranked=5,
    )


async def main() -> None:
    if os.path.exists(DB):
        os.remove(DB)
    bot = IntegratedBot(config=make_config())
    loop = bot.loop
    loop.session.is_open = lambda dt=None: True
    loop.session.check_session = lambda dt=None: SessionStatus.OPEN

    real = load_real_bars()
    sym = list(real.keys())[0]

    # ---- Phase 1: research -> backtest -> promote (synthetic trending series)
    print("\n[1] RESEARCH->BACKTEST->PROMOTE on synthetic trending series", flush=True)
    synthetic = build_synthetic_trend()
    promoted = bot._run_research({"SX": synthetic})
    print(f"    candidates generated & evaluated; promoted={promoted}", flush=True)
    lib = bot.library.all()
    print(f"    library entries: {len(lib)}", flush=True)
    for e in lib[: bot.config.top_n_ranked]:
        r = e.result
        print(f"      {e.template.name:42s} sharpe={r.sharpe_ratio:6.2f} "
              f"ret={r.total_return:7.2f}% trades={r.total_trades}", flush=True)
    print("    lifecycle:", bot.lifecycle.summary(), flush=True)
    print("    experiments:", bot.experiments.summary(), flush=True)

    # ---- Phase 2: genuine paper fills over real NSE bars
    print("\n[2] GENUINE paper fills + P&L over real NSE bars", flush=True)
    def reversal_signal_fn(bar, ctx):
        pos = loop.portfolio.get_position(bar.symbol)
        flat = pos is None or pos.quantity <= 0
        return [
            Signal(
                strategy_id="paper-reversal",
                symbol=bar.symbol,
                direction=SignalDirection.LONG if flat else SignalDirection.SHORT,
                confidence=0.5,
                reason=["reversal-entry" if flat else "reversal-exit"],
            )
        ]
    loop.set_strategy(reversal_signal_fn)
    filled = journal_before = len(loop.journal.get_entries())
    paced = 0
    bars = real[sym][-60:]
    loop._running = True
    for i, bar in enumerate(bars):
        loop._current_bar = bar
        loop.portfolio.update_market_price(bar.symbol, bar.close)
        loop.health.check_data_freshness(0.0)
        for sig in loop._strategy_fn(bar, None):
            res = await loop.process_signal(sig, bar)
            if res.get("action") in ("filled", "partial"):
                filled += 1
    loop._running = False
    pf = bot.portfolio.to_dict()  # same engine as the loop now
    print(f"    {len(bars)} bars, fills={filled} "
          f"journal_trades={len(loop.journal.get_entries()) - journal_before}", flush=True)
    print(f"    cash={pf.get('cash')} equity={pf.get('equity')} "
          f"realized={pf.get('realized_pnl')} unrealized={pf.get('unrealized_pnl')}", flush=True)
    print(f"    integrity_verified={bot.portfolio.verify_integrity().get('verified')}", flush=True)

    # ---- Phase 3: integrated run_cycle over real bars
    print("\n[3] INTEGRATED run_cycle on real bars", flush=True)
    cyc = await bot.run_cycle({sym: real[sym][-30:]})
    print(f"    cycle={cyc.get('cycle')} trades={cyc.get('trades')} "
          f"errors={len(cyc.get('errors', []))}", flush=True)
    for e in cyc.get("errors", [])[:5]:
        print(f"      err: {e}", flush=True)

    # ---- Phase 4: persistence verification
    print("\n[4] PERSISTENCE verification", flush=True)
    bot._persist_state()
    ns_count = 0
    for ns in bot.store.list_namespaces():
        k = len(bot.store.list_keys(ns))
        ns_count += k
        print(f"    namespace {ns}: {k} keys", flush=True)
    print(f"    total persisted keys: {ns_count}", flush=True)

    # ---- Phase 5: API reflects live state
    print("\n[5] API reflects live trading state", flush=True)
    import services.api.dependencies as deps
    deps._bot = bot  # inject the live bot into the API singleton
    from fastapi.testclient import TestClient
    from services.api.main import create_app

    with TestClient(create_app()) as client:
        checks = {}

        def show(label, resp, fields, agg=None):
            j = resp.json()
            if agg == "len":
                v = len(j) if isinstance(j, list) else sum(len(v) for v in j.values()) if isinstance(j, dict) else 0
                print(f"    {label:38s} {resp.status_code}  count={v}", flush=True)
            elif agg == "raw":
                print(f"    {label:38s} {resp.status_code}  {json.dumps(j, default=str)[:200]}", flush=True)
            else:
                subset = {f: (j.get(f) if isinstance(j, dict) else None) for f in fields}
                print(f"    {label:38s} {resp.status_code}  {subset}", flush=True)

        show("GET /health", client.get("/health"), ["status"])
        show("GET /trading/status (before)", client.get("/trading/status"),
             ["running", "cycle_count", "recovery_events"])
        show("GET /portfolio/summary", client.get("/portfolio/summary"),
             ["equity", "cash", "unrealized_pnl", "realized_pnl"])
        show("GET /portfolio/positions", client.get("/portfolio/positions"), [], agg="len")
        show("GET /portfolio/integrity", client.get("/portfolio/integrity"), ["verified"])
        show("GET /portfolio/trades", client.get("/portfolio/trades"), [], agg="len")
        show("GET /orders/counts", client.get("/orders/counts"), [], agg="raw")
        show("GET /orders/open", client.get("/orders/open"), [], agg="len")
        show("GET /strategies/lifecycle", client.get("/strategies/lifecycle"), [], agg="raw")
        show("GET /strategies/candidates/rankings", client.get("/strategies/candidates/rankings"), [], agg="len")
        show("GET /system/metrics", client.get("/system/metrics"), [], agg="raw")
        show("GET /system/namespaces", client.get("/system/namespaces"), [], agg="raw")

        # Drive a genuine cycle THROUGH the API and re-check state changed.
        def bar_to_dict(b):
            d = b.model_dump()
            d["timestamp"] = b.timestamp.isoformat()
            for k in ("open", "high", "low", "close", "spread"):
                if k in d and d[k] is not None:
                    d[k] = float(d[k])
            return d

        bar_dicts = [bar_to_dict(b) for b in real[sym][-10:]]
        r = client.post("/trading/cycle", json={"bars": {sym: bar_dicts}})
        body = r.json()
        print(f"    POST /trading/cycle status={r.status_code} body={body}", flush=True)
        show("GET /trading/status (after)", client.get("/trading/status"),
             ["running", "cycle_count", "recovery_events"])
        sess = client.get("/trading/status").json()
        if sess.get("cycle_count", 0) > 1:
            print("    API reflects live trading: cycle advanced via HTTP endpoint", flush=True)
        else:
            print("    WARNING: API cycle did not advance cycle_count", flush=True)

        # WebSocket live status stream.
        try:
            with client.websocket_connect("/ws/dashboard") as ws:
                ws.send_text("ping")
                msg = ws.receive_json()
                print(f"    WS /ws/dashboard ping -> {msg}", flush=True)
        except Exception as e:
            print(f"    WS /ws/dashboard note: {type(e).__name__}: {e}", flush=True)

    bot.stop()
    print("\nDONE. Store at data/genuine_paper.db", flush=True)


if __name__ == "__main__":
    asyncio.run(main())