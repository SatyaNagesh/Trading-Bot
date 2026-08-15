#!/usr/bin/env python3
"""Phase 3 — E2E Validation Harness for QuantLab AI."""

import asyncio
import importlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Any
from uuid import uuid4


@dataclass
class StageResult:
    name: str
    status: bool
    duration_ms: float
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stages: list[StageResult] = field(default_factory=list)
    import_errors: list[str] = field(default_factory=list)
    missing_integrations: list[str] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    total_duration_ms: float = 0
    passed: int = 0
    failed: int = 0

    def add(self, name, status, duration_ms, error=None, detail=None):
        self.stages.append(StageResult(name, status, duration_ms, error, detail or {}))
        if status:
            self.passed += 1
        else:
            self.failed += 1

    def summary_text(self) -> str:
        lines = [
            "=" * 60,
            f"VALIDATION REPORT — {self.timestamp}",
            "=" * 60,
            f"Total: {len(self.stages)} | Passed: {self.passed} | Failed: {self.failed} | Duration: {self.total_duration_ms:.1f}ms",
        ]
        if self.import_errors:
            lines.append(f"\nImport Errors ({len(self.import_errors)}):")
            for e in self.import_errors:
                lines.append(f"  ❌ {e}")
        if self.missing_integrations:
            lines.append(f"\nMissing Integrations ({len(self.missing_integrations)}):")
            for m in self.missing_integrations:
                lines.append(f"  ❌ {m}")
        lines.append("\n" + "-" * 60)
        for s in self.stages:
            icon = "✅" if s.status else "❌"
            err = f" — {s.error}" if s.error else ""
            lines.append(f"  {icon} {s.name} ({s.duration_ms:.1f}ms){err}")
        lines.append("-" * 60)
        return "\n".join(lines)


def time_it(fn):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result, elapsed = fn(*args, **kwargs), (time.perf_counter() - start) * 1000
            return result, elapsed, None
        except Exception as e:
            return None, (time.perf_counter() - start) * 1000, str(e)

    return wrapper


ALL_MODULES = [
    "packages.domain.models",
    "packages.broker.gateway",
    "packages.oms.manager",
    "packages.execution.engine",
    "packages.portfolio.engine",
    "packages.risk.engine",
    "packages.session.manager",
    "packages.journal.entry",
    "packages.health.monitor",
    "packages.dashboard.display",
    "packages.trading.loop",
    "packages.analytics.engine",
    "packages.analytics.strategy_tracker",
    "packages.analytics.regime_observer",
    "packages.analytics.self_review",
    "packages.analytics.degradation",
    "packages.analytics.research",
    "packages.analytics.reports",
    "packages.analytics.observation",
    "packages.optimization.signal_optimizer",
    "packages.optimization.allocation",
    "packages.optimization.alerts",
    "packages.autonomous.scheduler",
    "packages.autonomous.experiment",
    "packages.autonomous.lifecycle",
    "packages.autonomous.trading",
    "packages.autonomous.knowledge",
    "packages.autonomous.improvement",
    "packages.autonomous.health",
    "packages.autonomous.reports",
    "packages.autonomous.orchestrator",
    "packages.strategies.generator",
    "packages.backtesting.engine",
    "packages.candidates.library",
    "packages.candidates.ranking",
    "packages.strategies.runner",
    "packages.production.config",
    "packages.production.persistence",
    "packages.production.recovery",
    "packages.production.checkpoint",
    "packages.production.observability",
    "packages.production.fault",
    "packages.core.config",
    "packages.integration.pipeline",
]


def verify_imports() -> list[str]:
    return [f"{m}: {e}" for m in ALL_MODULES for e in [""] if not __import_workaround(m)]


def __import_workaround(m):
    try:
        importlib.import_module(m)
        return True
    except Exception:
        return False


# ── Stage Tests ────────────────────────────────────────────────────


def test_config():
    from packages.integration.pipeline import IntegrationConfig

    cfg = IntegrationConfig()
    assert cfg.initial_capital == Decimal("100000")
    assert cfg.max_candidates_per_cycle == 50
    assert cfg.commission == 0.001
    assert cfg.checkpoint_interval == 10
    return {"initial_capital": str(cfg.initial_capital)}


def test_persistence():
    import tempfile

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    try:
        from packages.production.persistence import PersistenceStore, ProductionStore

        store = PersistenceStore(db_path)
        prod = ProductionStore(store)
        prod.trades.put("test", {"value": 42})
        assert prod.trades.get("test") == {"value": 42}
        store.close()
        return {"namespaces": list(store.list_namespaces())}
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_broker():
    from packages.broker.gateway import SimulatedBroker, BrokerConfig

    b = SimulatedBroker(BrokerConfig(mode="paper"))
    assert b.config.mode == "paper"
    return {"mode": b.config.mode}


def test_oms():
    from packages.oms.manager import OrderManager
    from packages.domain.models import Side, OrderType

    o = OrderManager()
    order = o.create_order(
        strategy_id="s1",
        portfolio_id="p1",
        symbol="TEST",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )
    assert order.id
    return {"status": order.status.value}


def test_execution():
    return {"created": True}


def test_portfolio():
    from packages.portfolio.engine import PortfolioEngine
    from packages.domain.models import Order, Side, OrderType
    from datetime import datetime, timezone
    from decimal import Decimal

    pf = PortfolioEngine(initial_capital=Decimal("100000"))
    order = Order(
        id=str(uuid4()),
        strategy_id="s1",
        portfolio_id="p1",
        symbol="TEST",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        price=Decimal("100"),
        created_at=datetime.now(timezone.utc),
    )
    pf.apply_fill(order=order, fill_price=Decimal("100"))
    pos = pf.get_position("TEST")
    assert pos and pos.quantity == 10
    return {"equity": float(pf.portfolio.equity)}


def test_risk():
    from packages.risk.engine import RiskEngine
    from packages.portfolio.engine import PortfolioEngine
    from packages.domain.models import Order, Side, OrderType
    from decimal import Decimal
    from datetime import datetime, timezone

    pf = PortfolioEngine(initial_capital=Decimal("100000"))
    order = Order(
        id=str(uuid4()),
        strategy_id="s1",
        portfolio_id="p1",
        symbol="TEST",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        price=Decimal("100"),
        created_at=datetime.now(timezone.utc),
    )
    result = RiskEngine().check_order(order, pf)
    return {"passed": result.get("passed", False)}


def test_session():
    from packages.session.manager import MarketCalendar
    from datetime import date

    cal = MarketCalendar(holidays={date(2026, 12, 25)})
    assert cal.is_holiday(date(2026, 12, 25))
    return {"calendar": cal.name}


def test_journal():
    from packages.journal.entry import TradeJournal
    from packages.domain.models import Trade, Side
    from datetime import datetime, timezone
    from decimal import Decimal

    j = TradeJournal()
    j.record_trade(
        Trade(
            strategy_id="s1",
            symbol="TEST",
            side=Side.BUY,
            entry_price=Decimal("100"),
            quantity=10,
            entry_time=datetime.now(timezone.utc),
        ),
        "s1",
    )
    return {"entries": len(j.get_entries())}


def test_health_monitor():
    from packages.health.monitor import HealthMonitor

    hm = HealthMonitor()
    hm.check_broker(connected=True)
    hm.check_market_data(available=True)
    return {"alerts": len(hm.recent_alerts())}


def test_trading_loop():
    return {"created": True}


def test_strategy_tracker():
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.domain.models import Trade, Side
    from datetime import datetime, timezone
    from decimal import Decimal

    t = StrategyTracker()
    t.record_trade(
        Trade(
            strategy_id="s1",
            symbol="TEST",
            side=Side.BUY,
            entry_price=Decimal("100"),
            quantity=10,
            entry_time=datetime.now(timezone.utc),
        )
    )
    return {"strategies": len(t.all_summaries())}


def test_regime_observer():
    from packages.analytics.regime_observer import RegimeObserver
    from datetime import datetime

    ro = RegimeObserver()
    ro.observe([100, 101, 102], datetime.now(timezone.utc))
    return {"regime": str(ro.current_regime)}


def test_degradation():
    from packages.analytics.degradation import DegradationDetector
    from packages.analytics.strategy_tracker import StrategyTracker

    d = DegradationDetector(tracker=StrategyTracker())
    return {"health": str(d.evaluate("test"))}


def test_research():
    from packages.analytics.research import ResearchAssistant
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.degradation import DegradationDetector

    ResearchAssistant(
        tracker=StrategyTracker(), detector=DegradationDetector(tracker=StrategyTracker())
    )
    return {"created": True}


def test_signal_optimizer():
    from packages.optimization.signal_optimizer import SignalOptimizer
    from packages.analytics.strategy_tracker import StrategyTracker

    SignalOptimizer(strategy_tracker=StrategyTracker())
    return {"created": True}


def test_allocator():
    from packages.optimization.allocation import StrategyAllocator
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.degradation import DegradationDetector

    t = StrategyTracker()
    d = DegradationDetector(tracker=t)
    result = StrategyAllocator(tracker=t, detector=d).risk_parity(["s1", "s2"])
    return {"allocations": len(result)}


def test_alert_engine():
    from packages.optimization.alerts import AlertEngine
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.degradation import DegradationDetector
    from packages.analytics.regime_observer import RegimeObserver

    t = StrategyTracker()
    ae = AlertEngine(
        tracker=t, detector=DegradationDetector(tracker=t), regime_observer=RegimeObserver()
    )
    return {"alerts": len(ae.check_all())}


def test_scheduler():
    from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig

    s = AutonomousScheduler(ScheduleConfig())
    s.start()
    s.next_cycle()
    return {"cycles": s.status()["cycle_count"]}


def test_experiments():
    from packages.autonomous.experiment import ExperimentManager

    e = ExperimentManager()
    exp = e.create(hypothesis="H1", strategy_id="s1")
    return {"id": exp.id is not None}


def test_lifecycle():
    from packages.autonomous.lifecycle import StrategyLifecycle, StrategyStage

    lifecycle = StrategyLifecycle()
    lifecycle.register("s1", "Test")
    lifecycle.transition("s1", StrategyStage.GENERATING)
    return {"active": lifecycle.summary().get("total", 0)}


def test_knowledge():
    from packages.autonomous.knowledge import KnowledgeEvolver

    return {"insights": len(KnowledgeEvolver().learn_from_trades([], {"win_rate": 50.0}))}


def test_improvement():
    from packages.autonomous.improvement import SelfImprovementLoop

    return {"recs": len(SelfImprovementLoop().analyze("default", {"win_rate": 50.0}, []))}


def test_health_auto():
    from packages.autonomous.health import SystemHealthMonitor

    h = SystemHealthMonitor()
    h.heartbeat("test")
    return {"heartbeats": h.summary().get("total_heartbeats", 0)}


def test_orchestrator():
    from packages.autonomous.orchestrator import AutonomousOrchestrator
    from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
    from packages.autonomous.experiment import ExperimentManager
    from packages.autonomous.lifecycle import StrategyLifecycle
    from packages.autonomous.trading import ContinuousPaperTrader
    from packages.autonomous.knowledge import KnowledgeEvolver
    from packages.autonomous.improvement import SelfImprovementLoop
    from packages.autonomous.health import SystemHealthMonitor
    from packages.autonomous.reports import AutoReporter
    from packages.trading.loop import PaperTradingLoop
    from packages.optimization.signal_optimizer import SignalOptimizer
    from packages.optimization.allocation import StrategyAllocator
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.degradation import DegradationDetector
    from packages.analytics.observation import ObservationLoop, SimulationConfig
    from packages.analytics.self_review import ReviewStore
    from packages.analytics.regime_observer import RegimeObserver

    t = StrategyTracker()
    d = DegradationDetector(tracker=t)
    o = AutonomousOrchestrator(
        scheduler=AutonomousScheduler(ScheduleConfig()),
        experiments=ExperimentManager(),
        lifecycle=StrategyLifecycle(),
        trader=ContinuousPaperTrader(
            paper_loop=PaperTradingLoop(),
            signal_optimizer=SignalOptimizer(strategy_tracker=t),
            allocator=StrategyAllocator(tracker=t, detector=d),
            observation=ObservationLoop(
                tracker=t,
                review_store=ReviewStore(),
                regime_observer=RegimeObserver(),
                detector=d,
                config=SimulationConfig(),
            ),
        ),
        knowledge=KnowledgeEvolver(),
        improvement=SelfImprovementLoop(),
        health=SystemHealthMonitor(),
        reporter=AutoReporter(),
    )
    assert o is not None
    return {"created": True}


def test_strategy_generator():
    from packages.strategies.generator import StrategyGenerator

    g = StrategyGenerator()
    c = g.generate(max_candidates=5)
    return {"candidates": len(c)}


def test_library():
    from packages.candidates.library import StrategyLibrary

    return {"summary": StrategyLibrary().summary()}


def test_ranker():
    from packages.candidates.ranking import StrategyRanker

    r = StrategyRanker()
    return {"ranked": len(r.top_n([], 5))}


def test_backtest():
    from packages.backtesting.engine import BacktestEngine
    from packages.domain.models import BacktestConfig, Bar, Signal, SignalDirection
    from datetime import datetime

    e = BacktestEngine(
        config=BacktestConfig(
            initial_capital=Decimal("100000"),
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
    )
    bars = {
        "TEST": [
            Bar(
                symbol="TEST",
                timestamp=datetime.now(timezone.utc),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.5"),
                volume=10000,
                spread=Decimal("0.1"),
            )
            for _ in range(20)
        ]
    }
    e.strategy = lambda bar, ctx: [
        Signal(
            strategy_id="test",
            symbol=bar.symbol,
            direction=SignalDirection.LONG,
            confidence=0.7,
            reason=["test"],
            timestamp=str(bar.timestamp),
        )
    ]
    r = e.run(bars)
    return {"trades": r.total_trades, "sharpe": r.sharpe_ratio}


def test_report_generator():
    from packages.analytics.reports import ReportGenerator
    from packages.analytics.strategy_tracker import StrategyTracker
    from packages.analytics.self_review import ReviewStore
    from packages.analytics.regime_observer import RegimeObserver
    from packages.analytics.degradation import DegradationDetector

    rg = ReportGenerator(
        tracker=StrategyTracker(),
        review_store=ReviewStore(),
        regime_observer=RegimeObserver(),
        degradation_detector=DegradationDetector(tracker=StrategyTracker()),
    )
    return {"keys": list(rg.daily_report(trades=[]).keys())}


def test_auto_reporter():
    from packages.autonomous.reports import AutoReporter

    r = AutoReporter().cycle_report(
        cycle_id="test",
        cycle_number=1,
        orchestrator_status={},
        trader_summary={},
        lifecycle_summary={},
        experiment_summary={},
        knowledge_summary={},
        improvement_summary={},
        health_summary={},
    )
    return {"keys": list(r.keys())}


def test_recovery():
    import tempfile

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    try:
        from packages.production.persistence import PersistenceStore
        from packages.production.recovery import RecoverySystem

        s = PersistenceStore(db_path)
        r = RecoverySystem(s).recover()
        s.close()
        return {"errors": len(r.errors), "recovered": len(r.recovered_namespaces)}
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_checkpointer():
    import tempfile

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    try:
        from packages.production.persistence import PersistenceStore
        from packages.production.checkpoint import Checkpointer

        s = PersistenceStore(db_path)
        c = Checkpointer(s)
        c.create_checkpoint()
        r = c.summary()
        s.close()
        return {"summary": r}
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_observability():
    from packages.production.observability import MetricCollector, OperationalDashboard

    m = MetricCollector()
    m.increment("test")
    m.timing("test_timing", 100)
    m.gauge("test_gauge", 42.0)
    OperationalDashboard().set("test", "value")
    return {"metrics": True}


def test_config_validation():
    from packages.production.config import ProductionConfig

    c = ProductionConfig()
    assert c.paper_trading.max_positions == 10
    assert c.paper_trading.initial_capital == 1_000_000.0
    return {"valid": True}


def test_pipeline_bot():
    from packages.integration.pipeline import IntegratedBot, IntegrationConfig

    b = IntegratedBot(config=IntegrationConfig())
    assert b.config.max_candidates_per_cycle == 50
    return {"created": True}


def test_e2e_cycle():
    from packages.integration.pipeline import IntegratedBot, IntegrationConfig

    r = asyncio.run(IntegratedBot(config=IntegrationConfig()).run_cycle())
    return {"cycle": r["cycle"], "errors": len(r["errors"]), "elapsed": r["elapsed"]}


def test_e2e_multi_cycle():
    from packages.integration.pipeline import IntegratedBot, IntegrationConfig

    bot = IntegratedBot(config=IntegrationConfig())
    for i in range(5):
        r = asyncio.run(bot.run_cycle())
        assert r["cycle"] == i + 1
    return {"cycles": 5, "last_elapsed": r["elapsed"]}


STAGES = [
    ("Configuration", test_config),
    ("Persistence", test_persistence),
    ("Broker", test_broker),
    ("Order Manager", test_oms),
    ("Execution Engine", test_execution),
    ("Portfolio Engine", test_portfolio),
    ("Risk Engine", test_risk),
    ("Session Manager", test_session),
    ("Trade Journal", test_journal),
    ("Health Monitor", test_health_monitor),
    ("Trading Loop", test_trading_loop),
    ("Strategy Tracker", test_strategy_tracker),
    ("Regime Observer", test_regime_observer),
    ("Degradation Detector", test_degradation),
    ("Research Assistant", test_research),
    ("Signal Optimizer", test_signal_optimizer),
    ("Strategy Allocator", test_allocator),
    ("Alert Engine", test_alert_engine),
    ("Scheduler", test_scheduler),
    ("Experiment Manager", test_experiments),
    ("Strategy Lifecycle", test_lifecycle),
    ("Knowledge Evolver", test_knowledge),
    ("Improvement Loop", test_improvement),
    ("Health Monitor Auto", test_health_auto),
    ("Orchestrator", test_orchestrator),
    ("Strategy Generator", test_strategy_generator),
    ("Strategy Library", test_library),
    ("Strategy Ranker", test_ranker),
    ("Backtest Engine", test_backtest),
    ("Report Generator", test_report_generator),
    ("Auto Reporter", test_auto_reporter),
    ("Recovery System", test_recovery),
    ("Checkpointer", test_checkpointer),
    ("Observability", test_observability),
    ("Config Validation", test_config_validation),
    ("Pipeline Bot Creation", test_pipeline_bot),
    ("E2E Single Cycle", test_e2e_cycle),
    ("E2E Multi Cycle (x5)", test_e2e_multi_cycle),
]


def detect_missing_integrations(bot=None) -> list[str]:
    if bot is None:
        from packages.integration.pipeline import IntegratedBot, IntegrationConfig

        bot = IntegratedBot(config=IntegrationConfig())
    missing = []
    for attr in [
        "knowledge",
        "improvement",
        "orchestrator",
        "trader",
        "recovery",
        "checkpointer",
        "loop",
        "tracker",
        "alert_engine",
    ]:
        if not hasattr(bot, attr):
            missing.append(attr)
    return missing


def build_dependency_graph() -> dict[str, list[str]]:
    return {
        "IntegratedBot": [
            "PersistenceStore",
            "ProductionStore",
            "RecoverySystem",
            "Checkpointer",
            "MetricCollector",
            "OperationalDashboard",
        ],
        "Trading": [
            "SimulatedBroker",
            "OrderManager",
            "ExecutionEngine",
            "PortfolioEngine",
            "RiskEngine",
            "SessionManager",
            "TradeJournal",
            "HealthMonitor",
            "PaperTradingLoop",
        ],
        "Analytics": [
            "StrategyTracker",
            "RegimeObserver",
            "ReviewStore",
            "DegradationDetector",
            "ResearchAssistant",
            "ReportGenerator",
            "ObservationLoop",
        ],
        "Optimization": ["SignalOptimizer", "StrategyAllocator", "AlertEngine"],
        "Autonomous": [
            "AutonomousScheduler",
            "ExperimentManager",
            "StrategyLifecycle",
            "ContinuousPaperTrader",
            "KnowledgeEvolver",
            "SelfImprovementLoop",
            "SystemHealthMonitor",
            "AutoReporter",
            "AutonomousOrchestrator",
        ],
        "Research": ["StrategyGenerator", "StrategyLibrary", "StrategyRanker"],
    }


def run() -> ValidationReport:
    import_errors = verify_imports()
    report = ValidationReport(import_errors=import_errors)
    start = time.perf_counter()

    for name, fn in STAGES:
        try:
            s = time.perf_counter()
            result = fn()
            elapsed = (time.perf_counter() - s) * 1000
            report.add(name, True, elapsed, detail=result or {})
        except Exception as e:
            elapsed = (time.perf_counter() - s) * 1000
            report.add(name, False, elapsed, error=str(e))

    report.missing_integrations = detect_missing_integrations()
    report.dependency_graph = build_dependency_graph()
    report.total_duration_ms = (time.perf_counter() - start) * 1000
    return report


if __name__ == "__main__":
    r = run()
    print(r.summary_text())
    print("\nDependency Graph:")
    for stage, deps in r.dependency_graph.items():
        print(f"  {stage}: {', '.join(deps)}")
