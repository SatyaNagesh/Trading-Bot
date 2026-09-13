"""End-to-end paper trading loop — the full signal -> order -> risk -> fill ->
portfolio -> journal path must behave correctly with a controlled session."""

from datetime import UTC, datetime
from decimal import Decimal

from packages.domain.models import Bar, Signal, SignalDirection
from packages.session.manager import SessionManager, SessionStatus
from packages.trading.loop import PaperTradingLoop


def _bar(close: float = 100.0, ts=None) -> Bar:
    return Bar(
        symbol="TEST",
        timestamp=ts or datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=10_000,
    )


class _OpenSession(SessionManager):
    def is_open(self, dt=None):
        return True

    def check_session(self, dt=None):
        return SessionStatus.OPEN


def _long_signal() -> Signal:
    return Signal(
        strategy_id="test-strategy",
        direction=SignalDirection.LONG,
        confidence=0.7,
        reason=["test"],
    )


class TestPaperTradingLoop:
    async def test_full_paper_round_trip(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        loop.set_strategy(lambda bar, ctx: [_long_signal()])

        long_sig = _long_signal()
        res = await loop.process_signal(long_sig, _bar())
        assert res["action"] == "filled"
        pos = loop.portfolio.get_position("TEST")
        assert pos is not None and pos.quantity > 0
        # Journal entries are produced on round-trip close (exit), not entry.
        assert loop.journal.total_entries() == 0

        close_sig = Signal(
            strategy_id="test-strategy",
            direction=SignalDirection.SHORT,
            confidence=0.7,
            reason=["test-exit"],
        )
        entry_qty = pos.quantity
        res = await loop.process_signal(close_sig, _bar(close=110.0))
        assert res["action"] == "filled"
        after = loop.portfolio.get_position("TEST")
        assert after is not None and after.quantity < entry_qty
        assert loop.journal.total_entries() == 1
        assert loop.portfolio.verify_integrity()["verified"] is True

    async def test_session_closed_skips(self):
        loop = PaperTradingLoop(session_manager=SessionManager())
        loop.set_strategy(lambda bar, ctx: [_long_signal()])
        # 06:00 UTC Sunday = 11:30 IST Sunday -> closed anyway (weekend)
        res = await loop.process_signal(_long_signal(), _bar(ts=datetime(2026, 7, 19, 6, 0)))
        assert res["action"] == "skipped"

    async def test_health_failure_skips(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        loop.health.check_broker(connected=False)
        res = await loop.process_signal(_long_signal(), _bar())
        assert res["action"] == "skipped"

    async def test_kill_switch_rejects(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        loop.risk.emergency_stop("test")
        res = await loop.process_signal(_long_signal(), _bar())
        assert res["action"] == "rejected"

    async def test_neutral_signal_nop(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        res = await loop.process_signal(
            Signal(strategy_id="x", direction=SignalDirection.NEUTRAL), _bar()
        )
        assert res["action"] == "none"

    async def test_run_processes_bars(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        loop.set_strategy(lambda bar, ctx: [_long_signal()])
        bars = [
            _bar(close=100.0 + i * 0.5, ts=datetime(2026, 7, 15, 10, i, tzinfo=UTC))
            for i in range(5)
        ]
        loop._running = True
        stats = await loop.run(bars, symbol="TEST")
        assert stats["processed"] >= 1
        assert stats["filled"] >= 1

    def test_compute_quantity_two_percent_of_cash(self):
        loop = PaperTradingLoop()
        qty = loop._compute_quantity(None, _bar(close=100.0))
        # 2% of 1,000,000 = 20,000 / 100 = 200 shares
        assert qty == 200
        assert qty >= 1

    def test_emergency_stop(self):
        loop = PaperTradingLoop()
        loop.emergency_stop("test")
        assert loop.risk.summary()["kill_switch_active"] is True
        assert loop.status()["running"] is False

    def test_status_snapshot(self):
        loop = PaperTradingLoop(session_manager=_OpenSession())
        s = loop.status()
        for key in ("running", "portfolio", "risk", "session", "health", "journal", "orders"):
            assert key in s
