#!/usr/bin/env python3
"""Performance benchmark suite for all major QuantLab subsystems."""

import asyncio
import os
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Any, Callable
from uuid import uuid4


# ── Dataclasses ─────────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    ops_per_sec: float
    memory_kb: float


@dataclass
class BenchmarkReport:
    results: list[BenchmarkResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)

    def summary(self) -> str:
        lines = [
            "=" * 72,
            "PERFORMANCE BENCHMARK REPORT",
            "=" * 72,
            f"{'Benchmark':<40} {'Workload':<10} {'Time(ms)':<12} {'Ops/s':<12} {'Mem(KB)':<10}",
            "-" * 72,
        ]
        for r in self.results:
            wl = self._workload_label(r.name, r.iterations)
            lines.append(
                f"{r.name:<40} {wl:<10} {r.avg_time_ms:<12.2f} {r.ops_per_sec:<12.1f} {r.memory_kb:<10.1f}"
            )
        lines.append("-" * 72)
        lines.append("")
        lines.append("RECOMMENDATIONS:")
        for rec in self.recommendations:
            lines.append(f"  * {rec}")
        lines.append("=" * 72)
        return "\n".join(lines)

    @staticmethod
    def _workload_label(name: str, iterations: int) -> str:
        if "strategy_generation" in name or "signal_optimization" in name:
            return {10: "small", 50: "medium", 200: "large"}.get(iterations, str(iterations))
        if "10" in str(iterations) or iterations == 10:
            return "small"
        if "100" in str(iterations):
            return "small"
        return {
            500: "medium",
            2000: "large",
            1000: "medium",
            5000: "large",
            20: "medium",
            200: "large",
            5: "small",
        }.get(iterations, str(iterations))


# ── Benchmark Helpers ───────────────────────────────────────────────


def measure(name: str, iterations: int, fn: Callable, *args, **kwargs) -> BenchmarkResult:
    tracemalloc.start()
    start = time.perf_counter()
    fn(*args, **kwargs)
    total = (time.perf_counter() - start) * 1000
    _snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = _snap.statistics("lineno")
    mem_kb = sum(s.size for s in stats) / 1024 if stats else 0
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_ms=total,
        avg_time_ms=total,
        ops_per_sec=(iterations / total * 1000) if total > 0 else 0,
        memory_kb=mem_kb,
    )


_SAMPLE_BAR = None
_TRADE_LIST: list = []


def _make_bar(symbol: str = "TEST", close: Decimal | None = None) -> Any:
    from packages.domain.models import Bar

    return Bar(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=close or Decimal("100"),
        volume=10000,
    )


def _make_bars(count: int, symbol: str = "TEST") -> list:
    from packages.domain.models import Bar

    base = Decimal("100")
    return [
        Bar(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            open=base,
            high=base + Decimal("1"),
            low=base - Decimal("1"),
            close=base + Decimal(str(i % 10 - 5)),
            volume=10000,
        )
        for i in range(count)
    ]


def _make_bars_dict(count: int, symbol: str = "TEST") -> dict[str, list]:
    return {symbol: _make_bars(count, symbol)}


def _make_signal(strategy_id: str = "bench", bar: Any = None) -> Any:
    from packages.domain.models import Signal, SignalDirection

    return Signal(
        strategy_id=strategy_id,
        symbol=(bar.symbol if bar else "TEST"),
        direction=SignalDirection.LONG,
        confidence=0.7,
        reason=["benchmark"],
        timestamp=str(datetime.now(timezone.utc)),
    )


# ── 1. Strategy Generation ──────────────────────────────────────────


def _bench_strategy_generation(count: int) -> BenchmarkResult:
    from packages.strategies.generator import StrategyGenerator

    gen = StrategyGenerator()
    m = measure("strategy_generation", count, gen.generate, max_candidates=count)
    return m


# ── 2. Backtest Engine ──────────────────────────────────────────────


def _bench_backtest(bars: int) -> BenchmarkResult:
    from packages.backtesting.engine import BacktestEngine
    from packages.domain.models import BacktestConfig, Signal, SignalDirection
    from datetime import timedelta

    cfg = BacktestConfig(
        initial_capital=Decimal("100000"),
        start_date=date.today() - timedelta(days=bars),
        end_date=date.today(),
    )
    engine = BacktestEngine(config=cfg)
    engine.strategy = lambda bar, ctx: (
        [
            Signal(
                strategy_id="bench",
                symbol=bar.symbol,
                direction=SignalDirection.LONG,
                confidence=0.6,
                reason=["bench"],
                timestamp=str(bar.timestamp),
            ),
        ]
        if int(bar.close) % 3 == 0
        else []
    )
    return measure("backtest_engine", bars, engine.run, _make_bars_dict(bars))


# ── 3. Validation Pipeline ──────────────────────────────────────────


def _bench_validation() -> BenchmarkResult:
    from packages.tools.validate import run

    report = run()
    name = "validation_pipeline"
    return BenchmarkResult(
        name=name,
        iterations=report.total_duration_ms,
        total_time_ms=report.total_duration_ms,
        avg_time_ms=report.total_duration_ms,
        ops_per_sec=1 / (report.total_duration_ms / 1000) if report.total_duration_ms > 0 else 0,
        memory_kb=0,
    )


# ── 4. Signal Optimization ──────────────────────────────────────────


def _bench_signal_optimization(count: int) -> BenchmarkResult:
    from packages.optimization.signal_optimizer import SignalOptimizer
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.domain.models import Signal, SignalDirection, MarketContext, MarketRegime

    so = SignalOptimizer(strategy_tracker=StrategyTracker())
    ctx = MarketContext(
        timestamp=datetime.now(timezone.utc),
        regime=MarketRegime.RANGING,
        volatility=0.02,
        volume_ratio=1.0,
    )
    signals = [
        Signal(
            strategy_id=f"s{i}",
            symbol="TEST",
            direction=SignalDirection.LONG,
            confidence=0.5 + (i % 5) * 0.1,
            reason=["bench"],
            timestamp=str(datetime.now(timezone.utc)),
        )
        for i in range(count)
    ]
    return measure("signal_optimization", count, so.optimize, signals, ctx)


# ── 5. Trading Cycle ────────────────────────────────────────────────


def _bench_trading_cycle() -> BenchmarkResult:
    from packages.integration.pipeline import IntegratedBot, IntegrationConfig
    import tempfile

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    try:
        cfg = IntegrationConfig(
            db_path=db_path, max_candidates_per_cycle=10, max_evaluated_candidates=3
        )
        bot = IntegratedBot(config=cfg)
        bot._running = True
        bars_data = _make_bars_dict(20)
        tracemalloc.start()
        start = time.perf_counter()
        result = asyncio.run(bot.run_cycle(bars_data))
        total = (time.perf_counter() - start) * 1000
        _snap = tracemalloc.take_snapshot()
        tracemalloc.stop()
        stats = _snap.statistics("lineno")
        mem_kb = sum(s.size for s in stats) / 1024 if stats else 0
        bot.stop()
        iterations = result.get("cycle", 1)
        return BenchmarkResult(
            name="trading_cycle",
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total,
            ops_per_sec=1000 / total if total > 0 else 0,
            memory_kb=mem_kb,
        )
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ── 6. Persistence ──────────────────────────────────────────────────


def _bench_persistence(count: int) -> BenchmarkResult:
    from packages.production.persistence import PersistenceStore

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    try:
        store = PersistenceStore(db_path)
        tracemalloc.start()
        start = time.perf_counter()
        for i in range(count):
            store.put("bench", f"k{i}", {"value": i, "data": "x" * 64})
        for i in range(count):
            store.get("bench", f"k{i}")
        total = (time.perf_counter() - start) * 1000
        _snap = tracemalloc.take_snapshot()
        tracemalloc.stop()
        store.close()
        stats = _snap.statistics("lineno")
        mem_kb = sum(s.size for s in stats) / 1024 if stats else 0
        ops = count * 2
        return BenchmarkResult(
            name="persistence",
            iterations=count,
            total_time_ms=total,
            avg_time_ms=total / ops if ops else 0,
            ops_per_sec=ops / total * 1000 if total > 0 else 0,
            memory_kb=mem_kb,
        )
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ── 7. Portfolio Reconciliation ─────────────────────────────────────


def _bench_portfolio(count: int) -> BenchmarkResult:
    from packages.portfolio.engine import PortfolioEngine
    from packages.domain.models import Order, Side, OrderType
    from datetime import datetime, timezone
    from decimal import Decimal

    pf = PortfolioEngine(initial_capital=Decimal("10000000"))
    tracemalloc.start()
    start = time.perf_counter()
    for i in range(count):
        side = Side.BUY if i % 2 == 0 else Side.SELL
        if side == Side.SELL and not pf.get_position("TEST"):
            pf.apply_fill(
                Order(
                    id=str(uuid4()),
                    strategy_id="bench",
                    portfolio_id="p1",
                    symbol="TEST",
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=100,
                    price=Decimal("100"),
                    created_at=datetime.now(timezone.utc),
                ),
                fill_price=Decimal("100"),
            )
        order = Order(
            id=str(uuid4()),
            strategy_id="bench",
            portfolio_id="p1",
            symbol="TEST",
            side=side,
            order_type=OrderType.MARKET,
            quantity=10,
            price=Decimal("100"),
            created_at=datetime.now(timezone.utc),
        )
        pf.apply_fill(order, fill_price=Decimal("100") + Decimal(str(i % 5 - 2)))
    total = (time.perf_counter() - start) * 1000
    _snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = _snap.statistics("lineno")
    mem_kb = sum(s.size for s in stats) / 1024 if stats else 0
    return BenchmarkResult(
        name="portfolio_reconciliation",
        iterations=count,
        total_time_ms=total,
        avg_time_ms=total / count if count else 0,
        ops_per_sec=count / total * 1000 if total > 0 else 0,
        memory_kb=mem_kb,
    )


# ── 8. Report Generation ────────────────────────────────────────────


def _bench_report_generation() -> BenchmarkResult:
    from packages.analytics.reports import ReportGenerator
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.self_review import ReviewStore
    from packages.analytics.regime_observer import RegimeObserver
    from packages.analytics.degradation import DegradationDetector
    from packages.domain.models import Trade, Side
    from decimal import Decimal

    tracker = StrategyTracker()
    rg = ReportGenerator(
        tracker=tracker,
        review_store=ReviewStore(),
        regime_observer=RegimeObserver(),
        degradation_detector=DegradationDetector(tracker=tracker),
    )
    trades = [
        Trade(
            strategy_id="s1",
            symbol="TEST",
            side=Side.BUY,
            entry_price=Decimal("100"),
            exit_price=Decimal(str(100 + i)),
            quantity=10,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=i),
            exit_time=datetime.now(timezone.utc),
            pnl=Decimal(str(i)),
        )
        for i in range(200)
    ]
    for t in trades:
        tracker.record_trade(t)

    tracemalloc.start()
    start = time.perf_counter()
    _daily = rg.daily_report(trades)
    _weekly = rg.weekly_report(trades)
    _monthly = rg.monthly_report(trades)
    total = (time.perf_counter() - start) * 1000
    _snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = _snap.statistics("lineno")
    mem_kb = sum(s.size for s in stats) / 1024 if stats else 0
    return BenchmarkResult(
        name="report_generation",
        iterations=3,
        total_time_ms=total,
        avg_time_ms=total / 3,
        ops_per_sec=3000 / total if total > 0 else 0,
        memory_kb=mem_kb,
    )


# ── Runner ──────────────────────────────────────────────────────────


def generate_recommendations(results: list[BenchmarkResult]) -> list[str]:
    recs = []
    for r in results:
        if "strategy_generation" in r.name and r.avg_time_ms > 500:
            recs.append(
                f"Strategy generation ({r.iterations}) avg {r.avg_time_ms:.0f}ms — consider parallelising candidate enumeration."
            )
        if "backtest_engine" in r.name and r.iterations == 2000 and r.avg_time_ms > 5000:
            recs.append(
                f"Backtest engine ({r.iterations} bars) avg {r.avg_time_ms:.0f}ms — vectorise bar processing loop."
            )
        if "persistence" in r.name and r.iterations == 5000 and r.avg_time_ms > 2000:
            recs.append(
                f"Persistence ({r.iterations} pairs) avg {r.avg_time_ms:.0f}ms — batch writes reduce transaction overhead."
            )
        if "portfolio_reconciliation" in r.name and r.iterations == 500 and r.avg_time_ms > 1000:
            recs.append(
                f"Portfolio reconciliation ({r.iterations} fills) avg {r.avg_time_ms:.0f}ms — position lookup is O(n), switch to dict."
            )
        if "trading_cycle" in r.name and r.avg_time_ms > 3000:
            recs.append(
                f"Trading cycle avg {r.avg_time_ms:.0f}ms — check I/O wait in persistence and broker simulation."
            )
        if "report_generation" in r.name and r.avg_time_ms > 200:
            recs.append(
                f"Report generation avg {r.avg_time_ms:.0f}ms — pre-aggregate PnL series to avoid per-trade loops."
            )
    if not recs:
        recs.append("All benchmarks within expected range — no immediate optimisation needed.")
    return recs


def benchmark_subsystem(
    name: str, workloads: list[int], bench_fn: Callable[[int], BenchmarkResult]
) -> list[BenchmarkResult]:
    return [bench_fn(w) for w in workloads]


def run_all() -> BenchmarkReport:
    report = BenchmarkReport()

    print("Benchmarking Strategy Generation...")
    for r in benchmark_subsystem("strategy_generation", [10, 50, 200], _bench_strategy_generation):
        report.add(r)
        print(
            f"  {r.name} ({r.iterations}): {r.avg_time_ms:.1f}ms, {r.ops_per_sec:.0f} ops/s, {r.memory_kb:.0f}KB"
        )

    print("Benchmarking Backtest Engine...")
    for r in benchmark_subsystem("backtest_engine", [100, 500, 2000], _bench_backtest):
        report.add(r)
        print(
            f"  {r.name} ({r.iterations} bars): {r.avg_time_ms:.1f}ms, {r.ops_per_sec:.0f} ops/s, {r.memory_kb:.0f}KB"
        )

    print("Benchmarking Validation Pipeline...")
    r = _bench_validation()
    report.add(r)
    print(f"  {r.name}: {r.avg_time_ms:.1f}ms")

    print("Benchmarking Signal Optimization...")
    for wl in [5, 20]:
        r = _bench_signal_optimization(wl)
        report.add(r)
        print(f"  signal_optimization ({wl}): {r.avg_time_ms:.1f}ms, {r.memory_kb:.0f}KB")

    print("Benchmarking Trading Cycle...")
    r = _bench_trading_cycle()
    report.add(r)
    print(f"  {r.name}: {r.avg_time_ms:.1f}ms, {r.memory_kb:.0f}KB")

    print("Benchmarking Persistence...")
    for wl in [100, 1000, 5000]:
        r = _bench_persistence(wl)
        report.add(r)
        print(
            f"  persistence ({wl} pairs): {r.avg_time_ms:.1f}ms, {r.ops_per_sec:.0f} ops/s, {r.memory_kb:.0f}KB"
        )

    print("Benchmarking Portfolio Reconciliation...")
    for wl in [100, 500]:
        r = _bench_portfolio(wl)
        report.add(r)
        print(
            f"  portfolio_reconciliation ({wl} fills): {r.avg_time_ms:.1f}ms, {r.memory_kb:.0f}KB"
        )

    print("Benchmarking Report Generation...")
    r = _bench_report_generation()
    report.add(r)
    print(f"  {r.name}: {r.avg_time_ms:.1f}ms, {r.memory_kb:.0f}KB")

    report.recommendations = generate_recommendations(report.results)
    return report


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 72)
    print("  QuantLab Performance Benchmark Suite")
    print("=" * 72)
    print()
    report = run_all()
    print()
    print(report.summary())
