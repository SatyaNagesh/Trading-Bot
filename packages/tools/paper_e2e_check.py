"""Controlled paper-trading E2E check + soak for QuantLab Trader.

Runs the real PaperTradingLoop against deterministic synthetic NSE-style bars
(no external data, no live exchange) and verifies the full
signal -> order -> risk -> fill -> portfolio -> journal path. Produces a JSON
report artifact under reports/.

This is a CONTROLLED verification. REAL NSE live-session behavior is NOT
verified in this run (see reports/QUANTLAB_TRADER_FINAL_AUDIT_2026-09.md).
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.broker.gateway import BrokerConfig, PaperBroker
from packages.domain.models import Bar, MarketContext, MarketRegime, Signal, SignalDirection
from packages.session.manager import MarketCalendar, SessionManager, SessionStatus
from packages.trading.loop import PaperTradingLoop

REPORT_PATH = Path("reports/paper_e2e_check_results.json")


class _OpenSession(SessionManager):
    """Controlled test session: market always 'open' so bars drive fills."""

    def is_open(self, dt=None):
        return True

    def check_session(self, dt=None):
        return SessionStatus.OPEN


def _synthetic_bars(symbol: str, days: int = 60, seed: int = 20260913) -> list[Bar]:
    rng = random.Random(seed ^ hash(symbol) & 0xFFFF)
    bars: list[Bar] = []
    price = 1000.0 + rng.uniform(-50, 50)
    start = date(2026, 7, 1)
    for i in range(days):
        drift = rng.uniform(-0.015, 0.018)
        price = max(10.0, price * (1 + drift))
        o = price * rng.uniform(0.995, 1.005)
        c = price * rng.uniform(0.995, 1.005)
        hi = max(o, c) * rng.uniform(1.0, 1.01)
        lo = min(o, c) * rng.uniform(0.99, 1.0)
        ts = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=ts,
                open=Decimal(str(round(o, 2))),
                high=Decimal(str(round(hi, 2))),
                low=Decimal(str(round(lo, 2))),
                close=Decimal(str(round(c, 2))),
                volume=int(rng.randint(10_000, 500_000)),
            )
        )
        start = start.fromordinal(start.toordinal() + 1)
    return bars


def _make_strategy(loop: PaperTradingLoop):
    """Deterministic LONG-entry / SHORT-exit cycle; looks up the live position."""

    def strategy_fn(bar: Bar, ctx: MarketContext) -> list[Signal]:
        pos = loop.portfolio.get_position(bar.symbol)
        if pos is None or pos.quantity <= 0:
            return [
                Signal(
                    strategy_id="e2e-reactive",
                    direction=SignalDirection.LONG,
                    confidence=0.6,
                    reason=["e2e-entry"],
                )
            ]
        return [
            Signal(
                strategy_id="e2e-reactive",
                direction=SignalDirection.SHORT,
                confidence=0.6,
                reason=["e2e-exit"],
            )
        ]

    return strategy_fn


async def _run() -> dict:
    symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
    loop = PaperTradingLoop(
        broker=PaperBroker(BrokerConfig(mode="paper")),
        session_manager=_OpenSession(),
    )
    loop.set_strategy(_make_strategy(loop))

    stats = {"processed": 0, "filled": 0, "rejected": 0, "skipped": 0, "errors": 0}
    t0 = time.monotonic()
    bars_by_symbol = {s: _synthetic_bars(s) for s in symbols}
    for symbol, bars in bars_by_symbol.items():
        loop._running = True
        for bar in bars:
            loop.portfolio.update_market_price(bar.symbol, bar.close)
            loop.health.check_data_freshness(0.0)
            ctx = MarketContext(
                timestamp=bar.timestamp, regime=MarketRegime.RANGING, volatility=0.01
            )
            for sig in loop._strategy_fn(bar, ctx):
                stats["processed"] += 1
                res = await loop.process_signal(sig, bar)
                action = res.get("action", "?")
                if action in ("filled", "partial"):
                    stats["filled"] += 1
                elif action == "rejected":
                    stats["rejected"] += 1
                elif action == "skipped":
                    stats["skipped"] += 1
                elif action == "failed":
                    stats["errors"] += 1
        loop._running = False

    elapsed = round(time.monotonic() - t0, 3)
    integrity = loop.portfolio.verify_integrity()
    pf = loop.portfolio.to_dict()
    report = {
        "mode": "CONTROLLED_PAPER_E2E",
        "generated": datetime.now(timezone.utc).isoformat(),
        "broker": "PaperBroker",
        "symbols": symbols,
        "bars_per_symbol": len(bars_by_symbol[symbols[0]]),
        "total_bars": sum(len(b) for b in bars_by_symbol.values()),
        "elapsed_sec": elapsed,
        "stats": stats,
        "portfolio": {
            "cash": pf.get("cash"),
            "equity": pf.get("equity"),
            "realized_pnl": pf.get("realized_pnl"),
            "unrealized_pnl": pf.get("unrealized_pnl"),
            "open_positions": pf.get("open_positions"),
            "closed_trades": pf.get("closed_trades"),
            "integrity_verified": integrity.get("verified"),
            "nav_diff": integrity.get("difference"),
        },
        "journal_entries": loop.journal.total_entries(),
        "health_healthy": loop.health.all_healthy(),
        "risk_summary": loop.risk.summary(),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    return report


async def _soak(cycles: int = 2000) -> dict:
    """Soak loop: bounded, deterministic, exercises ordering without external IO."""
    loop = PaperTradingLoop(
        broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession()
    )
    loop.set_strategy(_make_strategy(loop))
    bar = _synthetic_bars("SOAK.NS", days=1)[0]
    t0 = time.monotonic()
    for i in range(cycles):
        loop._running = True
        shifted = bar.model_copy()
        shifted.timestamp = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
        loop.portfolio.update_market_price(shifted.symbol, shifted.close)
        loop.health.check_data_freshness(0.0)
        for sig in loop._strategy_fn(shifted, MarketContext(timestamp=shifted.timestamp)):
            await loop.process_signal(sig, shifted)
    loop._running = False
    elapsed = round(time.monotonic() - t0, 3)
    return {
        "mode": "SOAK",
        "cycles": cycles,
        "elapsed_sec": elapsed,
        "integrity_verified": loop.portfolio.verify_integrity().get("verified"),
        "open_positions": loop.portfolio.to_dict().get("open_positions"),
        "journal_entries": loop.journal.total_entries(),
        "order_counts": loop.oms.order_count(),
    }


async def main() -> None:
    e2e = await _run()
    soak = await _soak()
    print(json.dumps({"e2e": e2e, "soak": soak}, indent=2))
    ok = e2e["stats"]["filled"] > 0 and e2e["portfolio"]["integrity_verified"] and soak["integrity_verified"]
    print(f"\nPAPER E2E OK: {bool(ok)} (report -> {REPORT_PATH})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())