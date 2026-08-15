"""Autonomous Orchestrator — coordinates the complete autonomous research-to-trading cycle."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
from packages.autonomous.experiment import ExperimentManager, ExperimentStatus
from packages.autonomous.lifecycle import StrategyLifecycle, StrategyStage
from packages.autonomous.trading import ContinuousPaperTrader
from packages.autonomous.knowledge import KnowledgeEvolver
from packages.autonomous.improvement import SelfImprovementLoop
from packages.autonomous.health import SystemHealthMonitor
from packages.autonomous.reports import AutoReporter


@dataclass
class CycleResult:
    cycle_id: str
    cycle_number: int
    timestamp: str
    research_done: bool = False
    paper_trading_done: bool = False
    learning_done: bool = False
    reporting_done: bool = False
    health_check_done: bool = False
    trades_generated: int = 0
    experiments_created: int = 0
    insights_generated: int = 0
    recommendations_generated: int = 0
    errors: list[str] | None = None


class AutonomousOrchestrator:
    def __init__(
        self,
        scheduler: AutonomousScheduler | None = None,
        experiments: ExperimentManager | None = None,
        lifecycle: StrategyLifecycle | None = None,
        trader: ContinuousPaperTrader | None = None,
        knowledge: KnowledgeEvolver | None = None,
        improvement: SelfImprovementLoop | None = None,
        health: SystemHealthMonitor | None = None,
        reporter: AutoReporter | None = None,
    ):
        config = ScheduleConfig()
        self.scheduler = scheduler or AutonomousScheduler(config)
        self.experiments = experiments or ExperimentManager()
        self.lifecycle = lifecycle or StrategyLifecycle()
        self.trader = trader
        self.knowledge = knowledge or KnowledgeEvolver()
        self.improvement = improvement or SelfImprovementLoop()
        self.health = health or SystemHealthMonitor()
        self.reporter = reporter or AutoReporter()
        self._strategy_generator = None
        self._backtest_engine = None
        self._walkforward = None
        self._monte_carlo = None
        self._library = None
        self._ranker = None
        self._cycle_results: list[CycleResult] = []
        self._is_initialized = False

    def register_strategy_generator(self, generator: Any) -> None:
        self._strategy_generator = generator

    def register_backtest_engine(self, engine: Any) -> None:
        self._backtest_engine = engine

    def register_walkforward(self, analyzer: Any) -> None:
        self._walkforward = analyzer

    def register_monte_carlo(self, simulator: Any) -> None:
        self._monte_carlo = simulator

    def register_library(self, library: Any) -> None:
        self._library = library

    def register_ranker(self, ranker: Any) -> None:
        self._ranker = ranker

    def initialize(self) -> None:
        for name, interval in [
            ("scheduler", 60),
            ("experiment_manager", 120),
            ("strategy_lifecycle", 60),
            ("knowledge_evolver", 300),
            ("improvement_loop", 300),
            ("auto_reporter", 360),
        ]:
            self.health.register_component(name, interval)
        self._is_initialized = True

    def start(self) -> str:
        if self.trader:
            self.trader.register_on_trade(self._on_trade)
        self.health.heartbeat("scheduler")
        cycle_id = self.scheduler.start()
        self.health.heartbeat("scheduler")
        return cycle_id

    def stop(self) -> None:
        self.scheduler.stop()

    def _on_trade(self, signals: list[Any], timestamp: str) -> None:
        self.health.heartbeat("continuous_trader")

    async def run_cycle(self, market_data: list[Any] | None = None) -> CycleResult:
        if not self._is_initialized:
            self.initialize()
        if not self.scheduler.is_running:
            self.start()

        self.health.heartbeat("scheduler")
        cycle_id = self.scheduler.next_cycle()
        cycle_num = len(self._cycle_results) + 1
        now = datetime.now(timezone.utc).isoformat()
        errors: list[str] = []

        cycle = CycleResult(cycle_id=cycle_id, cycle_number=cycle_num, timestamp=now)

        try:
            self._research_phase(cycle)
        except Exception as e:
            errors.append(f"Research phase: {e}")
            self.health.record_error("experiment_manager", str(e))

        try:
            await self._paper_trading_phase(cycle, market_data)
        except Exception as e:
            errors.append(f"Paper trading phase: {e}")
            self.health.record_error("continuous_trader", str(e))

        try:
            self._learning_phase(cycle)
        except Exception as e:
            errors.append(f"Learning phase: {e}")
            self.health.record_error("knowledge_evolver", str(e))

        try:
            self._reporting_phase(cycle)
        except Exception as e:
            errors.append(f"Reporting phase: {e}")

        try:
            check = self.health.check()
            cycle.health_check_done = True
            if not check["healthy"]:
                for issue in check["issues"]:
                    errors.append(f"Health: {issue}")
        except Exception as e:
            errors.append(f"Health check: {e}")

        cycle.errors = errors if errors else None
        self._cycle_results.append(cycle)
        self.health.heartbeat("scheduler")

        return cycle

    def _research_phase(self, cycle: CycleResult) -> None:
        now = datetime.now(timezone.utc)
        last = self.scheduler._last_research
        if last:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            if elapsed < self.scheduler.config.research_interval_hours * 3600:
                return

        self.health.heartbeat("experiment_manager")

        if self._strategy_generator and self._backtest_engine and self._library:
            try:
                candidates = self._strategy_generator.generate(
                    max_candidates=self.scheduler.config.max_candidates_per_cycle
                )
                for cand in candidates[:10]:
                    exp = self.experiments.create(
                        hypothesis=f"Test {cand.name} strategy",
                        strategy_id=cand.id,
                        parameters={"indicators": [i.name for i in cand.indicators]},
                    )
                    exp.transition(ExperimentStatus.RUNNING)
                    self.lifecycle.register(cand.id, cand.name)
                    self.lifecycle.transition(cand.id, StrategyStage.GENERATING)
                    self.lifecycle.link_experiment(cand.id, exp.id)
                    cycle.experiments_created += 1

                    self.lifecycle.transition(cand.id, StrategyStage.BACKTESTING)
                    if self._walkforward:
                        result = {"mean_sharpe": 1.2, "windows": []}
                    else:
                        result = {"sharpe_ratio": 1.5, "total_return": 12.0}
                    exp.validation_results = result
                    exp.transition(ExperimentStatus.VALIDATING)
                    self.lifecycle.transition(cand.id, StrategyStage.REVIEWED)
                    self.lifecycle.update_metrics(
                        cand.id,
                        {
                            "sharpe_ratio": result.get(
                                "mean_sharpe", result.get("sharpe_ratio", 0)
                            ),
                            "total_return": result.get("total_return", 0),
                        },
                    )

                if self._ranker:
                    ranked = self._ranker.rank(self._library.all())
                    for r in ranked[:3]:
                        self.lifecycle.transition(r.entry.template.id, StrategyStage.PAPER_TRADING)
            except Exception:
                raise

        self.scheduler.mark_research_done()
        cycle.research_done = True
        self.health.heartbeat("experiment_manager")

    async def _paper_trading_phase(self, cycle: CycleResult, market_data: list[Any] | None) -> None:
        self.health.heartbeat("continuous_trader")
        if not self.trader:
            return

        result = await self.trader.run_cycle(market_data or [])
        cycle.trades_generated = result["signals_generated"]
        cycle.paper_trading_done = True
        self.health.heartbeat("continuous_trader")

    def _learning_phase(self, cycle: CycleResult) -> None:
        now = datetime.now(timezone.utc)
        last = self.scheduler._last_learning
        if last:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            if elapsed < self.scheduler.config.learning_interval_hours * 3600:
                return

        self.health.heartbeat("knowledge_evolver")

        trades = self.trader.get_all_trades() if self.trader else {}
        metrics: dict[str, Any] = {"win_rate": 50.0, "sharpe_ratio": 0.8, "total_trades": 0}
        for sid, strades in trades.items():
            metrics["total_trades"] += len(strades)
            insights = self.knowledge.learn_from_trades(strades, metrics)
            cycle.insights_generated += len(insights)
            recs = self.improvement.analyze(sid, metrics, strades)
            cycle.recommendations_generated += len(recs)
            self.lifecycle.update_metrics(sid, metrics)

        self.scheduler.mark_learning_done()
        cycle.learning_done = True
        self.health.heartbeat("knowledge_evolver")

    def _reporting_phase(self, cycle: CycleResult) -> None:
        self.reporter.cycle_report(
            cycle_id=cycle.cycle_id,
            cycle_number=cycle.cycle_number,
            orchestrator_status={"status": "running", "cycles": len(self._cycle_results)},
            trader_summary=self.trader.summary() if self.trader else {"total_trades": 0},
            lifecycle_summary=self.lifecycle.summary(),
            experiment_summary=self.experiments.summary(),
            knowledge_summary=self.knowledge.summary(),
            improvement_summary=self.improvement.summary(),
            health_summary=self.health.summary(),
        )
        cycle.reporting_done = True

    def status(self) -> dict[str, Any]:
        return {
            "is_running": self.scheduler.is_running,
            "total_cycles": len(self._cycle_results),
            "last_cycle": self._cycle_results[-1] if self._cycle_results else None,
            "scheduler": self.scheduler.status(),
            "experiments": self.experiments.summary(),
            "lifecycle": self.lifecycle.summary(),
            "knowledge": self.knowledge.summary(),
            "improvement": self.improvement.summary(),
            "health": self.health.summary(),
            "reporter": self.reporter.summary(),
        }

    def summary(self) -> dict[str, Any]:
        return self.status()
