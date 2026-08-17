"""Integrated Pipeline — wires all QuantLab subsystems into one autonomous bot.

This module connects every existing module into a single end-to-end pipeline.
It adds NO new capabilities — only integration, wiring, and orchestration.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.production.config import ProductionConfig, load_config
from packages.production.persistence import PersistenceStore, ProductionStore
from packages.production.recovery import RecoverySystem
from packages.production.checkpoint import Checkpointer
from packages.production.observability import MetricCollector, OperationalDashboard

from packages.domain.models import (
    Bar,
    Signal,
    SignalDirection,
    Trade,
    MarketRegime,
    BacktestConfig,
)
from packages.broker.gateway import SimulatedBroker, BrokerConfig
from packages.oms.manager import OrderManager
from packages.execution.engine import ExecutionEngine
from packages.portfolio.engine import PortfolioEngine
from packages.risk.engine import RiskEngine
from packages.session.manager import SessionManager
from packages.journal.entry import TradeJournal
from packages.health.monitor import HealthMonitor
from packages.trading.loop import PaperTradingLoop

from packages.analytics.strategy_tracker import StrategyTracker
from packages.analytics.regime_observer import RegimeObserver
from packages.analytics.self_review import ReviewStore, TradeReview
from packages.analytics.degradation import DegradationDetector, StrategyHealth
from packages.analytics.research import ResearchAssistant
from packages.analytics.reports import ReportGenerator
from packages.analytics.observation import ObservationLoop, SimulationConfig

from packages.optimization.signal_optimizer import SignalOptimizer
from packages.optimization.allocation import StrategyAllocator
from packages.optimization.alerts import AlertEngine

from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
from packages.autonomous.experiment import ExperimentManager, ExperimentStatus
from packages.autonomous.lifecycle import StrategyLifecycle, StrategyStage
from packages.autonomous.trading import ContinuousPaperTrader
from packages.autonomous.knowledge import KnowledgeEvolver
from packages.autonomous.improvement import SelfImprovementLoop
from packages.autonomous.health import SystemHealthMonitor
from packages.autonomous.reports import AutoReporter
from packages.autonomous.orchestrator import AutonomousOrchestrator

from packages.strategies.generator import StrategyGenerator
from packages.backtesting.engine import BacktestEngine
from packages.candidates.library import StrategyLibrary
from packages.candidates.ranking import StrategyRanker
from packages.review import generate_review
from packages.strategies.runner import CandidateResult


@dataclass
class IntegrationConfig:
    config_path: str = "config.yaml"
    db_path: str = "data/quantlab.db"
    initial_capital: Decimal = Decimal("100000")
    max_candidates_per_cycle: int = 50
    max_evaluated_candidates: int = 10
    backtest_days: int = 30
    commission: float = 0.001
    slippage: float = 0.001
    min_sharpe_for_review: float = 0.3
    min_trades_for_review: int = 5
    sharpe_for_paper_test: float = 0.5
    sharpe_for_promotion: float = 1.0
    min_trades_for_promotion: int = 10
    checkpoint_interval: int = 10
    top_n_ranked: int = 5
    simulation_max_cycles: int = 5000
    simulation_iteration_limit: int = 200


@dataclass
class SimulationResult:
    duration_days: int
    cycles_completed: int
    total_trades: int
    final_equity: Decimal
    total_return_pct: float
    max_drawdown_pct: float
    strategies_generated: int
    strategies_promoted: int
    alerts_generated: int
    reports_generated: int
    errors: list[str] = field(default_factory=list)


class IntegratedBot:
    _ALERTS_MAX = 20000

    def __init__(self, config: IntegrationConfig | None = None):
        self.config = config or IntegrationConfig()
        self._running = False
        self._cycle_count = 0
        self._recovery_events = 0

        self._init_config()
        self._init_persistence()
        self._init_observability()
        self._init_trading()
        self._init_analytics()
        self._init_optimization()
        self._init_autonomous()
        self._wire_pipeline()

    def _init_config(self) -> None:
        cfg_path = Path(self.config.config_path)
        self.prod_config = load_config(str(cfg_path)) if cfg_path.exists() else ProductionConfig()

    def _init_persistence(self) -> None:
        self.store = PersistenceStore(self.config.db_path)
        self.prod = ProductionStore(self.store)
        self.recovery = RecoverySystem(self.store)
        self.checkpointer = Checkpointer(self.store)

    def _init_observability(self) -> None:
        self.metrics = MetricCollector()
        self.dashboard = OperationalDashboard()

    def _init_trading(self) -> None:
        broker_cfg = BrokerConfig(mode="paper")
        self.broker = SimulatedBroker(broker_cfg)
        self.oms = OrderManager()
        self.execution = ExecutionEngine(self.broker, self.oms)
        initial = Decimal(str(self.prod_config.paper_trading.initial_capital))
        self.portfolio = PortfolioEngine(initial_capital=initial)
        self.risk = RiskEngine()
        self.session = SessionManager()
        self.journal = TradeJournal()
        self.health_monitor = HealthMonitor()

        self.loop = PaperTradingLoop(
            broker=self.broker,
            initial_capital=initial,
            session_manager=self.session,
            portfolio=self.portfolio,
        )

    def _init_analytics(self) -> None:
        self.tracker = StrategyTracker()
        self.regime_observer = RegimeObserver()
        self.review_store = ReviewStore()
        self.degradation = DegradationDetector(tracker=self.tracker)
        self.research = ResearchAssistant(tracker=self.tracker, detector=self.degradation)
        self.report_gen = ReportGenerator(
            tracker=self.tracker,
            review_store=self.review_store,
            regime_observer=self.regime_observer,
            degradation_detector=self.degradation,
        )
        self.observation = ObservationLoop(
            tracker=self.tracker,
            review_store=self.review_store,
            regime_observer=self.regime_observer,
            detector=self.degradation,
            config=SimulationConfig(),
        )

    def _init_optimization(self) -> None:
        self.signal_optimizer = SignalOptimizer(
            strategy_tracker=self.tracker,
            regime_observer=self.regime_observer,
            degradation_detector=self.degradation,
        )
        self.allocator = StrategyAllocator(
            tracker=self.tracker,
            detector=self.degradation,
        )
        self.alert_engine = AlertEngine(
            tracker=self.tracker,
            detector=self.degradation,
            regime_observer=self.regime_observer,
        )

    def _init_autonomous(self) -> None:
        sched_config = ScheduleConfig(
            research_interval_hours=self.prod_config.schedule.research_interval_hours,
            paper_trading_interval_minutes=self.prod_config.schedule.paper_trading_interval_minutes,
            learning_interval_hours=self.prod_config.schedule.learning_interval_hours,
            reporting_interval_hours=self.prod_config.schedule.reporting_interval_hours,
            health_check_interval_minutes=self.prod_config.schedule.health_check_interval_minutes,
        )
        self.scheduler = AutonomousScheduler(sched_config)
        self.experiments = ExperimentManager()
        self.lifecycle = StrategyLifecycle()
        self.knowledge = KnowledgeEvolver()
        self.improvement = SelfImprovementLoop()
        self.health_auto = SystemHealthMonitor()

        self.trader = ContinuousPaperTrader(
            paper_loop=self.loop,
            signal_optimizer=self.signal_optimizer,
            allocator=self.allocator,
            observation=self.observation,
        )
        self.reporter = AutoReporter()
        self.strategy_gen = StrategyGenerator()
        self.library = StrategyLibrary()
        self.ranker = StrategyRanker()

        self.orchestrator = AutonomousOrchestrator(
            scheduler=self.scheduler,
            experiments=self.experiments,
            lifecycle=self.lifecycle,
            trader=self.trader,
            knowledge=self.knowledge,
            improvement=self.improvement,
            health=self.health_auto,
            reporter=self.reporter,
        )

    def _wire_pipeline(self) -> None:
        self.orchestrator.register_strategy_generator(self.strategy_gen)
        self.orchestrator.register_library(self.library)
        self.orchestrator.register_ranker(self.ranker)
        self.trader.register_on_trade(self._on_trade_hook)
        self._register_recovery_hooks()

    def _register_recovery_hooks(self) -> None:
        self.recovery.register_recovery_hook(
            "trades",
            lambda v: (
                self.journal.record_trade(
                    trade=v.get("entries", [{}])[0],
                    strategy_id=v.get("entries", [{}])[0].get("strategy_id", ""),
                )
                if v.get("entries")
                else None
            ),
        )
        self.recovery.register_recovery_hook(
            "portfolio",
            lambda v: (
                setattr(
                    self.portfolio, "portfolio", self.portfolio.portfolio.__class__.from_dict(v)
                )
                if hasattr(self.portfolio.portfolio.__class__, "from_dict")
                else None
            ),
        )
        self.recovery.register_recovery_hook(
            "orders",
            lambda v: (
                self.oms.create_order(
                    strategy_id=v.get("strategy_id", ""),
                    portfolio_id=v.get("portfolio_id", ""),
                    symbol=v.get("symbol", ""),
                    side=v.get("side"),
                    order_type=v.get("order_type"),
                    quantity=v.get("quantity", 0),
                    price=v.get("price"),
                )
                if v.get("symbol")
                else None
            ),
        )
        self.recovery.register_recovery_hook(
            "strategies",
            lambda v: (
                self.lifecycle.register(v.get("id", ""), v.get("name", "")) if v.get("id") else None
            ),
        )
        self.recovery.register_recovery_hook(
            "analytics", lambda v: setattr(self, "_analytics_restored", True) if v else None
        )
        self.recovery.register_recovery_hook(
            "alerts", lambda v: self.prod.alerts.put(v.get("id", str(id(v))), v) if v else None
        )
        self.recovery.register_recovery_hook("allocator", lambda v: None)
        self.recovery.register_recovery_hook(
            "degradation",
            lambda v: (
                self.degradation.evaluate(v.get("strategy_id")) if v.get("strategy_id") else None
            ),
        )
        self.recovery.register_recovery_hook(
            "scheduler", lambda v: self.scheduler.next_cycle() if v.get("restore") else None
        )
        self.recovery.register_recovery_hook("journal", lambda v: None)
        self.recovery.register_recovery_hook("checkpoints", lambda v: None)

    def _on_trade_hook(self, signals: list[Any], timestamp: str) -> None:
        self._run_analytics_chain()
        self._persist_state()

    def _run_analytics_chain(self) -> None:
        self.health_auto.heartbeat("analytics")

        known_ids = getattr(self, "_processed_entry_ids", set())
        all_entries = self.journal.get_entries()
        new_entries = [e for e in all_entries if id(e) not in known_ids]
        self._processed_entry_ids = set(id(e) for e in all_entries)

        for entry in new_entries:
            trade = Trade(
                strategy_id=entry.strategy_id,
                symbol=entry.symbol,
                side=entry.side,
                entry_price=entry.entry_price,
                exit_price=entry.exit_price or Decimal("0"),
                quantity=entry.quantity,
                entry_time=entry.entry_time,
                exit_time=entry.exit_time or datetime.now(timezone.utc),
                pnl=entry.pnl,
            )
            self.tracker.record_trade(trade)
            review = TradeReview(trade).generate()
            self.review_store.record(review)

            for sid in self.tracker.all_summaries() or {}:
                self.degradation.evaluate(sid)
                self.research.explain_performance(sid)

                degraded_by = self.degradation.get_health(sid)
                if degraded_by in (StrategyHealth.DEGRADED, StrategyHealth.RETIRED):
                    retirement = self.research.suggest_retirement(sid)
                    self.prod.alerts.put(f"retire_{sid}", retirement)
                    self.health_auto.record_error(
                        sid, f"degraded: {retirement.get('suggestion', '')}"
                    )

            self._compute_analytics()

        alerts = self.alert_engine.check_all()
        for a in alerts:
            a["id"] = a.get("id", str(id(a)))
            self.prod.alerts.put(a["id"], a)
            self.recovery.save_state("alerts", a["id"], a)

        insights = self.knowledge.learn_from_trades(
            self.journal.export(),
            {"win_rate": 50.0, "sharpe_ratio": 0.5},
        )
        for iid in insights:
            self.prod.strategies.put(f"insight_{iid}", {"id": iid})

        recs = self.improvement.analyze(
            "default",
            {"win_rate": 50.0, "sharpe_ratio": 0.5, "total_trades": len(all_entries)},
            self.journal.export(),
        )
        for r in recs:
            self.prod.alerts.put(f"rec_{r.get('id', str(id(r)))}", r)

        alerts = self.health_monitor.recent_alerts(limit=10)
        for a in alerts:
            self.prod.alerts.put(f"health_{a.get('timestamp', str(id(a)))}", a)

        self.store.prune_namespace("alerts", self._ALERTS_MAX)

        rec_result = self.recovery.recovery_summary()
        if not rec_result.get("success", True):
            self.prod.alerts.put(
                "recovery_failure",
                {
                    "severity": "critical",
                    "message": "Recovery system has failures",
                    "errors": rec_result.get("total_errors", 0),
                },
            )
            self.health_auto.record_error("recovery", "Recovery failures detected")

    def _compute_analytics(self) -> None:
        self.health_auto.heartbeat("analytics")

        all_entries = self.journal.get_entries()[:100]
        prices = [float(t.entry_price) for t in all_entries if t.entry_price]
        if prices:
            self.regime_observer.observe(prices, datetime.now(timezone.utc))

        by_strategy = self.tracker.all_summaries()
        if by_strategy:
            strategy_ids = list(by_strategy.keys())
            allocations = self.allocator.risk_parity(
                strategy_ids,
            )
            self.prod.alerts.put("allocations", allocations)

    def _persist_state(self) -> None:
        try:
            entries = self.journal.get_entries()[:500]
            self.prod.trades.put(
                "current",
                {
                    "count": len(entries),
                    "entries": [
                        {
                            "strategy_id": e.strategy_id,
                            "symbol": e.symbol,
                            "pnl": float(e.pnl),
                            "timestamp": e.timestamp.isoformat(),
                        }
                        for e in entries[-50:]
                    ],
                },
            )
            self.prod.portfolio.put("current", self.portfolio.to_dict())
            self.prod.analytics.put(
                "current",
                {
                    "tracker": self.tracker.all_summaries(),
                    "regime": self.regime_observer.regime_counts(),
                    "degradation": self.degradation.health_summary(),
                },
            )
            self.prod.alerts.put("counts", self.alert_engine.alert_count())
        except Exception:
            self._recovery_events += 1

    def _run_research(self, hist_bars: dict[str, list[Bar]] | None = None) -> int:
        if hist_bars is None:
            return 0

        candidates = self.strategy_gen.generate(max_candidates=self.config.max_candidates_per_cycle)
        promoted = 0
        symbols = list(hist_bars.keys())
        if not symbols:
            return 0

        bt_config = BacktestConfig(
            initial_capital=self.config.initial_capital,
            start_date=datetime.now(timezone.utc).date()
            - timedelta(days=self.config.backtest_days),
            end_date=datetime.now(timezone.utc).date(),
            commission=self.config.commission,
            slippage=self.config.slippage,
        )

        for cand in candidates[: self.config.max_evaluated_candidates]:
            engine = BacktestEngine(config=bt_config)

            def make_signal_fn(template):
                def signal_fn(bar: Bar, ctx) -> list[Signal]:
                    close_val = float(bar.close)
                    exit_meta = {
                        "take_profit_pct": template.exit.take_profit_pct,
                        "stop_loss_pct": template.exit.stop_loss_pct,
                    }
                    ind = template.indicators[0] if template.indicators else None
                    if ind and ind.factory in ("sma", "ema"):
                        threshold = ind.params.get("threshold", 0)
                        if close_val > threshold:
                            return [
                                Signal(
                                    strategy_id=template.id,
                                    symbol=bar.symbol,
                                    direction=SignalDirection.LONG,
                                    confidence=0.6,
                                    reason=[f"{ind.factory}_crossover"],
                                    timestamp=str(bar.timestamp),
                                    metadata=exit_meta,
                                )
                            ]
                    if close_val < 50:
                        return [
                            Signal(
                                strategy_id=template.id,
                                symbol=bar.symbol,
                                direction=SignalDirection.LONG,
                                confidence=0.5,
                                reason=["price_low"],
                                timestamp=str(bar.timestamp),
                                metadata=exit_meta,
                            )
                        ]
                    return []

                return signal_fn

            engine.strategy = make_signal_fn(cand)

            try:
                result = engine.run(hist_bars)
            except Exception:
                continue

            cand_result = CandidateResult(
                strategy_id=cand.id,
                strategy_name=cand.name,
                total_return=result.total_return,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown,
                win_rate=result.win_rate,
                profit_factor=result.profit_factor,
                total_trades=result.total_trades,
            )

            review = generate_review(cand, cand_result)
            self.library.add(
                cand, cand_result, review=review, composite_score=max(0, result.sharpe_ratio * 20)
            )

            self.lifecycle.register(cand.id, cand.name)
            self.lifecycle.transition(cand.id, StrategyStage.GENERATING)
            self.lifecycle.transition(cand.id, StrategyStage.BACKTESTING)

            exp = self.experiments.create(
                hypothesis=f"Test {cand.name}",
                strategy_id=cand.id,
                parameters={"indicators": [i.factory for i in cand.indicators]},
            )
            exp.transition(ExperimentStatus.RUNNING)
            self.lifecycle.link_experiment(cand.id, exp.id)

            if (
                abs(result.sharpe_ratio) < self.config.min_sharpe_for_review
                or result.total_trades < self.config.min_trades_for_review
            ):
                exp.transition(ExperimentStatus.REJECTED)
                continue

            self.lifecycle.transition(cand.id, StrategyStage.VALIDATING)
            exp.transition(ExperimentStatus.VALIDATING)
            exp.validation_results = {
                "sharpe_ratio": result.sharpe_ratio,
                "total_return": result.total_return,
                "total_trades": result.total_trades,
            }

            if result.sharpe_ratio > self.config.sharpe_for_paper_test:
                self.lifecycle.transition(cand.id, StrategyStage.REVIEWED)
                exp.transition(ExperimentStatus.PAPER_TESTING)
                self.lifecycle.update_metrics(
                    cand.id,
                    {
                        "sharpe_ratio": result.sharpe_ratio,
                        "total_return": result.total_return,
                        "total_trades": result.total_trades,
                    },
                )

            if (
                result.sharpe_ratio > self.config.sharpe_for_promotion
                and result.total_trades >= self.config.min_trades_for_promotion
            ):
                self.lifecycle.transition(cand.id, StrategyStage.PAPER_TRADING)
                exp.transition_along(ExperimentStatus.PROMOTED)
                promoted += 1
            else:
                exp.transition_along(ExperimentStatus.ARCHIVED)

        ranked = self.ranker.top_n(self.library.all(), self.config.top_n_ranked)
        for re in ranked:
            eid = re.entry.template.id
            self.prod.strategies.put(
                eid,
                {
                    "name": re.entry.template.name,
                    "score": re.entry.composite_score,
                    "sharpe": re.entry.result.sharpe_ratio,
                    "return": re.entry.result.total_return,
                },
            )

        return promoted

    def start(self) -> None:
        self._running = True
        self.orchestrator.start()
        last = self.checkpointer.latest_checkpoint()
        if last:
            r = self.recovery.recover()
            self._recovery_events = len(r.errors)
        self.metrics.gauge("bot_uptime_s", 0)
        self.dashboard.set("status", "running")

    def stop(self) -> None:
        self._running = False
        self.orchestrator.stop()
        self._persist_state()
        self.checkpointer.create_checkpoint()
        self.store.close()
        self.dashboard.set("status", "stopped")

    async def run_cycle(self, bars_data: dict[str, list[Bar]] | None = None) -> dict[str, Any]:
        if not self._running:
            self.start()
        self._cycle_count += 1
        start_ts = datetime.now(timezone.utc)

        errors: list[str] = []
        promoted, trade_count, alert_count = 0, 0, 0

        self.health_auto.heartbeat("scheduler")
        self.scheduler.next_cycle()

        self.health_auto.heartbeat("broker")
        self.health_auto.heartbeat("trading_loop")
        self.health_auto.heartbeat("persistence")
        self.health_auto.heartbeat("recovery")

        self.health_monitor.check_broker(connected=True)
        self.health_monitor.check_market_data(available=bars_data is not None)
        self.health_monitor.check_risk_engine(healthy=True)
        self.health_monitor.check_portfolio_integrity(
            verified=self.portfolio.verify_integrity().get("verified", True)
        )

        if bars_data:
            try:
                promoted = self._run_research(bars_data)
            except Exception as e:
                errors.append(f"research: {e}")

            bar_list = list(bars_data.values())[0] if bars_data else []
            for bar in bar_list:
                ctx = self._make_context(bar)
                signal_fn = self.signal_optimizer.wrap(
                    lambda b, ctx: [
                        Signal(
                            strategy_id="default",
                            symbol=b.symbol,
                            direction=SignalDirection.LONG
                            if float(b.close) % 2 == 0
                            else SignalDirection.SHORT,
                            confidence=0.5,
                            reason=["integrated"],
                            timestamp=str(b.timestamp),
                        )
                    ]
                )
                try:
                    signals = signal_fn(bar, ctx)
                except Exception as e:
                    errors.append(f"signal_gen: {e}")
                    continue
                for sig in signals:
                    try:
                        result = await self.loop.process_signal(sig, bar)
                        if result.get("action") in ("filled", "partial"):
                            trade_count += 1
                    except Exception as e:
                        errors.append(f"execution: {e}")
                        self.health_monitor.check_system_exception()

            self.health_monitor.check_execution_latency(latency_ms=0.0)

        try:
            self._run_analytics_chain()
        except Exception as e:
            errors.append(f"analytics: {e}")

        if trade_count > 0:
            try:
                alerts = self.alert_engine.check_all()
                alert_count = len(alerts)
                self.recovery.save_state("alerts", f"cycle_{self._cycle_count}", alerts)
                daily = self.report_gen.daily_report(trades=self._journal_to_trades())
                self.prod.reports.put(f"day_{self._cycle_count}", daily)
            except Exception as e:
                errors.append(f"reporting: {e}")

        try:
            auto_report = self.reporter.cycle_report(
                cycle_id=f"cycle_{self._cycle_count}",
                cycle_number=self._cycle_count,
                orchestrator_status={"status": "running", "cycles": self._cycle_count},
                trader_summary=self.trader.summary(),
                lifecycle_summary=self.lifecycle.summary(),
                experiment_summary=self.experiments.summary(),
                knowledge_summary=self.knowledge.summary(),
                improvement_summary=self.improvement.summary(),
                health_summary=self.health_auto.summary(),
            )
            self.prod.reports.put(f"auto_cycle_{self._cycle_count}", auto_report)
        except Exception as e:
            errors.append(f"auto_report: {e}")

        self._persist_state()

        if self._cycle_count % self.config.checkpoint_interval == 0:
            try:
                self.checkpointer.create_checkpoint()
            except Exception as e:
                errors.append(f"checkpoint: {e}")

        elapsed = (datetime.now(timezone.utc) - start_ts).total_seconds()
        self.metrics.increment("cycles_completed")
        self.metrics.timing("cycle_ms", int(elapsed * 1000))
        self.metrics.gauge("portfolio_value", float(self.portfolio.portfolio.equity))

        return {
            "cycle": self._cycle_count,
            "trades": trade_count,
            "promoted": promoted,
            "alerts": alert_count,
            "errors": errors,
            "elapsed": round(elapsed, 3),
        }

    def _journal_to_trades(self) -> list[Trade]:
        trades = []
        for e in self.journal.get_entries():
            trades.append(
                Trade(
                    strategy_id=e.strategy_id,
                    symbol=e.symbol,
                    side=e.side,
                    entry_price=e.entry_price,
                    exit_price=e.exit_price or Decimal("0"),
                    quantity=e.quantity,
                    entry_time=e.entry_time,
                    exit_time=e.exit_time or datetime.now(timezone.utc),
                    pnl=e.pnl,
                )
            )
        return trades

    def _make_context(self, bar: Bar) -> Any:
        from packages.domain.models import MarketContext

        return MarketContext(
            timestamp=bar.timestamp,
            regime=MarketRegime.RANGING,
            volatility=0.02,
            volume_ratio=1.0,
        )

    async def run_simulation(
        self, days: int, trades_per_day: int = 10, volatility: float = 0.02
    ) -> SimulationResult:
        self.start()
        cycles = min(days * 96, self.config.simulation_max_cycles)
        errors: list[str] = []
        total_trades, total_promoted, total_alerts = 0, 0, 0

        for _ in range(min(cycles, self.config.simulation_iteration_limit)):
            bar = Bar(
                symbol="SIM",
                timestamp=datetime.now(timezone.utc),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=10000,
                spread=Decimal("0.1"),
            )
            bars_data = {"SIM": [bar]}
            result = await self.run_cycle(bars_data)
            total_trades += result.get("trades", 0)
            total_promoted += result.get("promoted", 0)
            total_alerts += result.get("alerts", 0)
            errors.extend(result.get("errors", []))

        obs_results = self.observation.run_sync()
        for sid, sinfo in obs_results.get("strategy_regimes", {}).items():
            self.prod.analytics.put(f"obs_{sid}", sinfo)

        self._persist_state()
        self.checkpointer.create_checkpoint()

        pf = self.portfolio.to_dict()
        initial = float(self.config.initial_capital)
        final = float(pf.get("equity", initial))
        total_return = ((final - initial) / initial) * 100 if initial > 0 else 0

        return SimulationResult(
            duration_days=days,
            cycles_completed=self._cycle_count,
            total_trades=total_trades,
            final_equity=Decimal(str(final)),
            total_return_pct=round(total_return, 2),
            max_drawdown_pct=float(pf.get("drawdown", 0)),
            strategies_generated=self.config.max_candidates_per_cycle,
            strategies_promoted=total_promoted,
            alerts_generated=total_alerts,
            reports_generated=self._cycle_count,
            errors=errors,
        )

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "portfolio": self.portfolio.to_dict(),
            "journal": self.journal.summary(),
            "library": self.library.summary(),
            "lifecycle": self.lifecycle.summary(),
            "experiments": self.experiments.summary(),
            "tracker": self.tracker.all_summaries(),
            "degradation": self.degradation.health_summary(),
            "alerts": self.alert_engine.alert_count(),
            "recovery_events": self._recovery_events,
            "persistence": {
                "namespaces": self.store.list_namespaces(),
                "total_entries": self.store.count(),
                "checkpoints": self.checkpointer.summary(),
            },
        }
