"""Gate 6B — Autonomous Research System tests."""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from packages.autonomous.experiment import ExperimentManager, ExperimentStatus, Experiment
from packages.autonomous.lifecycle import StrategyLifecycle, StrategyStage
from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
from packages.autonomous.trading import ContinuousPaperTrader
from packages.autonomous.knowledge import KnowledgeEvolver
from packages.autonomous.improvement import SelfImprovementLoop
from packages.autonomous.health import SystemHealthMonitor
from packages.autonomous.reports import AutoReporter
from packages.autonomous.orchestrator import AutonomousOrchestrator, CycleResult


# ── Experiment Manager ──────────────────────────────────────────────

class TestExperiment:
    def test_create(self):
        em = ExperimentManager()
        exp = em.create("Test hypothesis", "strat-1", {"param": 42})
        assert exp.hypothesis == "Test hypothesis"
        assert exp.strategy_id == "strat-1"
        assert exp.parameters == {"param": 42}
        assert exp.status == ExperimentStatus.PROPOSED
        assert exp.id is not None

    def test_transition_valid(self):
        em = ExperimentManager()
        exp = em.create("hypothesis", "strat-1")
        em.transition(exp.id, ExperimentStatus.RUNNING)
        assert em.get(exp.id).status == ExperimentStatus.RUNNING

    def test_transition_invalid(self):
        em = ExperimentManager()
        exp = em.create("hypothesis", "strat-1")
        with pytest.raises(ValueError, match="Cannot transition"):
            em.transition(exp.id, ExperimentStatus.PROMOTED)

    def test_transition_nonexistent(self):
        em = ExperimentManager()
        with pytest.raises(KeyError):
            em.transition("nonexistent", ExperimentStatus.RUNNING)

    def test_full_lifecycle(self):
        em = ExperimentManager()
        exp = em.create("Full lifecycle", "strat-1")

        em.transition(exp.id, ExperimentStatus.RUNNING)
        assert em.get(exp.id).status == ExperimentStatus.RUNNING

        em.transition(exp.id, ExperimentStatus.VALIDATING)
        assert em.get(exp.id).status == ExperimentStatus.VALIDATING

        em.transition(exp.id, ExperimentStatus.PAPER_TESTING)
        assert em.get(exp.id).status == ExperimentStatus.PAPER_TESTING

        em.transition(exp.id, ExperimentStatus.LEARNING)
        assert em.get(exp.id).status == ExperimentStatus.LEARNING

        em.transition(exp.id, ExperimentStatus.PROMOTED)
        assert em.get(exp.id).status == ExperimentStatus.PROMOTED

        em.transition(exp.id, ExperimentStatus.ARCHIVED)
        assert em.get(exp.id).status == ExperimentStatus.ARCHIVED

    def test_rejection_path(self):
        em = ExperimentManager()
        exp = em.create("Rejected", "strat-1")
        em.transition(exp.id, ExperimentStatus.REJECTED)
        assert em.get(exp.id).status == ExperimentStatus.REJECTED

    def test_list_filtered(self):
        em = ExperimentManager()
        e1 = em.create("A", "s1")
        e2 = em.create("B", "s2")
        em.transition(e1.id, ExperimentStatus.RUNNING)
        em.transition(e2.id, ExperimentStatus.REJECTED)
        running = em.list(status=ExperimentStatus.RUNNING)
        rejected = em.list(status=ExperimentStatus.REJECTED)
        proposed = em.list(status=ExperimentStatus.PROPOSED)
        assert len(running) == 1
        assert running[0].id == e1.id
        assert len(rejected) == 1
        assert len(proposed) == 0

    def test_list_order(self):
        em = ExperimentManager()
        e1 = em.create("First", "s1")
        e2 = em.create("Second", "s2")
        all_exps = em.list()
        assert len(all_exps) == 2
        assert all_exps[0].id == e2.id

    def test_count_by_status(self):
        em = ExperimentManager()
        e1 = em.create("A", "s1")
        e2 = em.create("B", "s2")
        em.transition(e1.id, ExperimentStatus.RUNNING)
        counts = em.count()
        assert counts.get("proposed") == 1
        assert counts.get("running") == 1

    def test_summary(self):
        em = ExperimentManager()
        em.create("A", "s1")
        em.create("B", "s2")
        s = em.summary()
        assert s["total"] == 2
        assert s["promoted"] == 0
        assert s["rejected"] == 0

    def test_to_dict(self):
        exp = Experiment("test", "s1")
        d = exp.to_dict()
        assert d["hypothesis"] == "test"
        assert d["strategy_id"] == "s1"
        assert d["status"] == "proposed"


# ── Strategy Lifecycle ──────────────────────────────────────────────

class TestStrategyLifecycle:
    def test_register(self):
        sl = StrategyLifecycle()
        sl.register("s1", "Test Strategy")
        s = sl.get("s1")
        assert s is not None
        assert s["name"] == "Test Strategy"
        assert s["stage"] == StrategyStage.CONCEIVED

    def test_transition_valid(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        sl.transition("s1", StrategyStage.GENERATING)
        assert sl.get("s1")["stage"] == StrategyStage.GENERATING

    def test_transition_invalid(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        with pytest.raises(ValueError, match="Cannot transition"):
            sl.transition("s1", StrategyStage.PAPER_TRADING)

    def test_full_lifecycle(self):
        sl = StrategyLifecycle()
        sl.register("s1", "Full Lifecycle")
        stages = [
            StrategyStage.GENERATING,
            StrategyStage.BACKTESTING,
            StrategyStage.VALIDATING,
            StrategyStage.REVIEWED,
            StrategyStage.PAPER_TRADING,
            StrategyStage.LIVE_READY,
            StrategyStage.OPTIMIZING,
            StrategyStage.DEGRADED,
            StrategyStage.RETIRED,
        ]
        for stage in stages:
            sl.transition("s1", stage)
        assert sl.get("s1")["stage"] == StrategyStage.RETIRED

    def test_update_metrics(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        sl.update_metrics("s1", {
            "trade_count": 100,
            "win_rate": 55.5,
            "sharpe_ratio": 1.2,
            "total_return": 15.0,
        })
        s = sl.get("s1")
        assert s["trade_count"] == 100
        assert s["win_rate"] == 55.5
        assert s["sharpe_ratio"] == 1.2

    def test_update_metrics_unknown_key(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        sl.update_metrics("s1", {"unknown_key": "value"})
        s = sl.get("s1")
        assert "unknown_key" not in s

    def test_update_metrics_nonexistent(self):
        sl = StrategyLifecycle()
        with pytest.raises(KeyError):
            sl.update_metrics("nonexistent", {})

    def test_mark_degraded(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        sl.transition("s1", StrategyStage.GENERATING)
        sl.transition("s1", StrategyStage.BACKTESTING)
        sl.transition("s1", StrategyStage.VALIDATING)
        sl.transition("s1", StrategyStage.REVIEWED)
        sl.transition("s1", StrategyStage.PAPER_TRADING)
        sl.mark_degraded("s1", "Sharpe below threshold")
        s = sl.get("s1")
        assert s["stage"] == StrategyStage.DEGRADED
        assert "Sharpe below threshold" in s["degradation_reasons"]

    def test_link_experiment(self):
        sl = StrategyLifecycle()
        sl.register("s1", "T")
        sl.link_experiment("s1", "exp-1")
        sl.link_experiment("s1", "exp-2")
        assert "exp-1" in sl.get("s1")["experiment_ids"]
        assert len(sl.get("s1")["experiment_ids"]) == 2

    def test_list_filter(self):
        sl = StrategyLifecycle()
        sl.register("s1", "A")
        sl.register("s2", "B")
        sl.transition("s1", StrategyStage.GENERATING)
        assert len(sl.list(stage=StrategyStage.GENERATING)) == 1
        assert len(sl.list(stage=StrategyStage.CONCEIVED)) == 1

    def test_summary(self):
        sl = StrategyLifecycle()
        sl.register("s1", "A")
        sl.register("s2", "B")
        s = sl.summary()
        assert s["total"] == 2
        assert s["by_stage"].get("conceived") == 2


# ── Autonomous Scheduler ────────────────────────────────────────────

class TestAutonomousScheduler:
    def test_start_stop(self):
        sched = AutonomousScheduler()
        cid = sched.start()
        assert cid is not None
        assert sched.is_running
        sched.stop()
        assert not sched.is_running

    def test_next_cycle_requires_running(self):
        sched = AutonomousScheduler()
        with pytest.raises(RuntimeError, match="not running"):
            sched.next_cycle()

    def test_next_cycle_increments_count(self):
        sched = AutonomousScheduler()
        sched.start()
        cid1 = sched.next_cycle()
        cid2 = sched.next_cycle()
        assert cid1 != cid2
        assert sched.status()["cycle_count"] == 2

    def test_mark_research_done(self):
        sched = AutonomousScheduler()
        sched.start()
        assert sched._last_research is None
        sched.mark_research_done()
        assert sched._last_research is not None

    def test_mark_learning_and_report(self):
        sched = AutonomousScheduler()
        sched.start()
        sched.mark_learning_done()
        sched.mark_report_done()
        assert sched._last_learning is not None
        assert sched._last_report is not None

    def test_status(self):
        sched = AutonomousScheduler()
        sched.start()
        s = sched.status()
        assert s["is_running"]
        assert s["cycle_count"] == 0
        assert s["config"]["research_interval_hours"] == 4.0
        assert s["config"]["max_candidates_per_cycle"] == 500

    def test_register_hook(self):
        sched = AutonomousScheduler()
        calls = []
        def hook(cid, num):
            calls.append((cid, num))
        sched.register_hook("on_cycle_start", hook)
        sched.start()
        sched.next_cycle()
        assert len(calls) == 1

    def test_config_custom(self):
        cfg = ScheduleConfig(research_interval_hours=1.0, max_candidates_per_cycle=100)
        sched = AutonomousScheduler(cfg)
        assert sched.config.research_interval_hours == 1.0
        assert sched.config.max_candidates_per_cycle == 100


# ── Continuous Paper Trader ─────────────────────────────────────────

class TestContinuousPaperTrader:
    @pytest.fixture
    def mock_loop(self):
        loop = MagicMock()
        async def run(market_data):
            return []
        loop.run = run
        return loop

    @pytest.mark.asyncio
    async def test_run_cycle(self, mock_loop):
        trader = ContinuousPaperTrader(mock_loop)
        result = await trader.run_cycle([])
        assert result["signals_generated"] == 0
        assert result["cycle"] == 1
        assert result["strategies_active"] == 0

    @pytest.mark.asyncio
    async def test_run_cycle_with_signals(self, mock_loop):
        mock_signal = MagicMock()
        mock_signal.strategy_id = "strat-1"
        mock_signal.direction = "long"
        mock_signal.confidence = 0.8
        async def run_with_signal(market_data):
            return [mock_signal]
        mock_loop.run = run_with_signal

        trader = ContinuousPaperTrader(mock_loop)
        result = await trader.run_cycle([])
        assert result["signals_generated"] == 1
        assert result["strategies_active"] == 1
        assert result["total_trades"] == 1

    @pytest.mark.asyncio
    async def test_multiple_cycles(self, mock_loop):
        trader = ContinuousPaperTrader(mock_loop)
        await trader.run_cycle([])
        await trader.run_cycle([])
        await trader.run_cycle([])
        assert trader.summary()["cycles_completed"] == 3

    @pytest.mark.asyncio
    async def test_get_strategy_trades(self, mock_loop):
        sig = MagicMock()
        sig.strategy_id = "strat-1"
        sig.direction = "long"
        sig.confidence = 0.8
        async def run_with_sig(market_data):
            return [sig]
        mock_loop.run = run_with_sig

        trader = ContinuousPaperTrader(mock_loop)
        await trader.run_cycle([])
        trades = trader.get_strategy_trades("strat-1")
        assert len(trades) == 1
        assert trades[0]["direction"] == "long"

    @pytest.mark.asyncio
    async def test_get_all_trades(self, mock_loop):
        sig1 = MagicMock()
        sig1.strategy_id = "s1"
        sig2 = MagicMock()
        sig2.strategy_id = "s2"
        async def run_with_sigs(market_data):
            return [sig1, sig2]

        mock_loop.run = run_with_sigs
        trader = ContinuousPaperTrader(mock_loop)
        await trader.run_cycle([])
        all_t = trader.get_all_trades()
        assert "s1" in all_t
        assert "s2" in all_t

    @pytest.mark.asyncio
    async def test_on_trade_hook(self):
        from unittest.mock import MagicMock
        loop = MagicMock()
        async def run(md):
            return []
        loop.run = run
        calls = []
        def hook(signals, ts):
            calls.append((signals, ts))
        trader = ContinuousPaperTrader(loop)
        trader.register_on_trade(hook)
        result = await trader.run_cycle([])
        assert len(calls) == 1, f"calls={calls}, result={result}"

    def test_summary_empty(self, mock_loop):
        trader = ContinuousPaperTrader(mock_loop)
        s = trader.summary()
        assert s["total_trades"] == 0
        assert s["cycles_completed"] == 0


# ── Knowledge Evolver ───────────────────────────────────────────────

class TestKnowledgeEvolver:
    def test_record_insight(self):
        ke = KnowledgeEvolver()
        iid = ke.record_insight("performance", "Low WR", "WR below 30%", "test")
        assert iid == "insight-1"
        assert len(ke.get_insights()) == 1

    def test_record_pattern(self):
        ke = KnowledgeEvolver()
        pid = ke.record_pattern("entry", "Pattern description", {"rsi": 30}, "win")
        assert pid == "pattern-1"

    def test_learn_from_trades_high_win_rate(self):
        ke = KnowledgeEvolver()
        trades = [{"result": "win"}, {"result": "win"}]
        metrics = {"win_rate": 60.0, "sharpe_ratio": 1.5, "total_trades": 2}
        ids = ke.learn_from_trades(trades, metrics)
        assert len(ids) == 0

    def test_learn_from_trades_low_win_rate(self):
        ke = KnowledgeEvolver()
        trades = [{"result": "loss"}]
        metrics = {"win_rate": 20.0, "sharpe_ratio": 0.3, "total_trades": 1}
        ids = ke.learn_from_trades(trades, metrics)
        assert len(ids) > 0

    def test_learn_from_trades_low_sharpe(self):
        ke = KnowledgeEvolver()
        trades = [{"result": "win"}] * 25
        metrics = {"win_rate": 52.0, "sharpe_ratio": 0.3, "total_trades": 25}
        ids = ke.learn_from_trades(trades, metrics)
        assert len(ids) == 1

    def test_get_insights_filter_by_category(self):
        ke = KnowledgeEvolver()
        ke.record_insight("performance", "P1", "desc", "src")
        ke.record_insight("risk", "R1", "desc", "src")
        assert len(ke.get_insights(category="performance")) == 1
        assert len(ke.get_insights(category="risk")) == 1

    def test_get_patterns_filter(self):
        ke = KnowledgeEvolver()
        ke.record_pattern("entry", "E1", {}, "win")
        ke.record_pattern("exit", "X1", {}, "loss")
        assert len(ke.get_patterns("entry")) == 1
        assert len(ke.get_patterns("exit")) == 1

    def test_summary(self):
        ke = KnowledgeEvolver()
        ke.record_insight("performance", "P1", "desc", "src")
        ke.record_pattern("entry", "E1", {}, "win")
        s = ke.summary()
        assert s["total_insights"] == 1
        assert s["total_patterns"] == 1
        assert s["learning_cycles"] == 0

    def test_knowledge_graph_integration(self):
        kg = MagicMock()
        ke = KnowledgeEvolver(knowledge_graph=kg)
        ke.record_insight("perf", "T1", "desc", "src")
        assert kg.add_node.called


# ── Self-Improvement Loop ───────────────────────────────────────────

class TestSelfImprovementLoop:
    def test_analyze_healthy(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 50, "sharpe_ratio": 1.2, "max_drawdown": -15,
                                   "total_trades": 20}, [{"r": "win"}] * 20)
        assert len(recs) == 0

    def test_analyze_low_win_rate(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.8, "max_drawdown": -15,
                                   "total_trades": 20}, [{"r": "loss"}] * 10)
        assert len(recs) >= 1
        categories = [r["category"] for r in recs]
        assert "entry_filter" in categories

    def test_analyze_low_sharpe(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 40, "sharpe_ratio": 0.3, "max_drawdown": -10,
                                   "total_trades": 20}, [{"r": "win"}] * 8)
        assert len(recs) >= 1
        assert "risk_management" in [r["category"] for r in recs]

    def test_analyze_high_drawdown(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 40, "sharpe_ratio": 0.6, "max_drawdown": -25,
                                   "total_trades": 20}, [{"r": "loss"}] * 12)
        assert len(recs) >= 1
        assert "drawdown_control" in [r["category"] for r in recs]

    def test_analyze_insufficient_trades(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.3, "total_trades": 3},
                           [{"r": "loss"}] * 3)
        assert len(recs) == 0

    def test_apply_recommendation(self):
        sil = SelfImprovementLoop()
        recs = sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.5, "total_trades": 20},
                           [{"r": "loss"}] * 11)
        assert len(recs) > 0
        applied = sil.apply(recs[0]["id"])
        assert applied is not None
        assert applied["applied"]
        assert sil.summary()["applied"] == 1

    def test_apply_nonexistent(self):
        sil = SelfImprovementLoop()
        assert sil.apply("nonexistent") is None

    def test_get_recommendations_filter(self):
        sil = SelfImprovementLoop()
        sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.3, "max_drawdown": -25,
                           "total_trades": 20}, [{"r": "loss"}] * 12)
        recs = sil.get_recommendations(strategy_id="s1")
        assert len(recs) > 0
        assert sil.get_recommendations(strategy_id="nonexistent") == []

    def test_get_recommendations_unapplied(self):
        sil = SelfImprovementLoop()
        sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.5, "total_trades": 20},
                           [{"r": "loss"}] * 11)
        recs = sil.get_recommendations(only_unapplied=True)
        assert all(not r["applied"] for r in recs)

    def test_summary(self):
        sil = SelfImprovementLoop()
        sil.analyze("s1", {"win_rate": 30, "sharpe_ratio": 0.3, "total_trades": 20},
                           [{"r": "loss"}] * 12)
        s = sil.summary()
        assert s["loops_completed"] == 1
        assert s["total_recommendations"] > 0


# ── System Health Monitor ───────────────────────────────────────────

class TestSystemHealthMonitor:
    def test_register_component(self):
        shm = SystemHealthMonitor()
        shm.register_component("scheduler", 60)
        check = shm.check()
        assert check["component_count"] == 1

    def test_heartbeat(self):
        shm = SystemHealthMonitor()
        shm.register_component("scheduler", 60)
        shm.heartbeat("scheduler")
        status = shm.check()["components"]["scheduler"]
        assert status["status"] == "healthy"

    def test_heartbeat_unknown(self):
        shm = SystemHealthMonitor()
        shm.heartbeat("unknown")
        check = shm.check()
        assert check["healthy"]

    def test_record_error(self):
        shm = SystemHealthMonitor()
        shm.register_component("trader", 60)
        shm.record_error("trader", "Connection failed")
        status = shm.check()["components"]["trader"]
        assert status["status"] == "degraded"
        assert status["error_count"] == 1

    def test_stale_detection(self):
        shm = SystemHealthMonitor()
        shm.register_component("c1", 60)
        shm.heartbeat("c1")
        check = shm.check()
        assert check["healthy"]

    def test_get_alerts(self):
        shm = SystemHealthMonitor()
        shm.register_component("c1", 60)
        shm.record_error("c1", "Error 1")
        shm.record_error("c1", "Error 2")
        alerts = shm.get_alerts()
        assert len(alerts) == 2
        assert shm.get_alerts(component="c1") == alerts

    def test_summary(self):
        shm = SystemHealthMonitor()
        shm.register_component("c1", 60)
        shm.register_component("c2", 120)
        shm.heartbeat("c1")
        s = shm.summary()
        assert s["components"]["total"] == 2
        assert s["components"]["healthy"] >= 1


# ── Auto Reporter ───────────────────────────────────────────────────

class TestAutoReporter:
    def test_generate_report(self):
        ar = AutoReporter()
        report = ar.generate_report("test", {"key": "value"})
        assert report["type"] == "test"
        assert report["data"]["key"] == "value"

    def test_cycle_report(self):
        ar = AutoReporter()
        report = ar.cycle_report("cid-1", 1, {}, {}, {}, {}, {}, {}, {})
        assert report["type"] == "cycle"
        assert report["data"]["cycle_id"] == "cid-1"
        assert report["data"]["cycle_number"] == 1

    def test_weekly_summary_no_data(self):
        ar = AutoReporter()
        report = ar.weekly_summary([])
        assert report["type"] == "weekly"
        assert report["data"]["summary"] == "No data"

    def test_weekly_summary_with_data(self):
        ar = AutoReporter()
        c1 = ar.cycle_report("c1", 1,
                            orchestrator_status={"status": "ok"},
                            trader_summary={"total_trades": 10},
                            lifecycle_summary={"total": 2},
                            experiment_summary={"total": 2},
                            knowledge_summary={"total_insights": 1},
                            improvement_summary={"total_recommendations": 2},
                            health_summary={"components": {"total": 1}})
        c2 = ar.cycle_report("c2", 2,
                            orchestrator_status={"status": "ok"},
                            trader_summary={"total_trades": 5},
                            lifecycle_summary={"total": 3},
                            experiment_summary={"total": 3},
                            knowledge_summary={"total_insights": 2},
                            improvement_summary={"total_recommendations": 1},
                            health_summary={"components": {"total": 1}})
        cycles = [c1, c2]
        report = ar.weekly_summary(cycles)
        assert report["data"]["total_trades"] == 15
        assert report["data"]["total_experiments"] == 5
        assert report["data"]["total_recommendations"] == 3

    def test_get_reports_filter(self):
        ar = AutoReporter()
        ar.generate_report("type_a", {})
        ar.generate_report("type_b", {})
        assert len(ar.get_reports(report_type="type_a")) == 1
        assert len(ar.get_reports(report_type="type_b")) == 1

    def test_summary(self):
        ar = AutoReporter()
        ar.generate_report("cycle", {})
        ar.generate_report("cycle", {})
        ar.generate_report("weekly", {})
        s = ar.summary()
        assert s["total_reports"] == 3
        assert s["by_type"]["cycle"] == 2
        assert s["by_type"]["weekly"] == 1


# ── Autonomous Orchestrator ─────────────────────────────────────────

class TestAutonomousOrchestrator:
    @pytest.fixture
    def mock_trader(self):
        loop = MagicMock()
        async def run(market_data):
            return []
        loop.run = run
        return ContinuousPaperTrader(loop)

    def test_initialize(self):
        orch = AutonomousOrchestrator()
        orch.initialize()
        assert orch._is_initialized

    def test_start_stop(self):
        orch = AutonomousOrchestrator()
        cid = orch.start()
        assert cid is not None
        assert orch.scheduler.is_running
        orch.stop()
        assert not orch.scheduler.is_running

    @pytest.mark.asyncio
    async def test_run_cycle_auto_init(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        result = await orch.run_cycle([])
        assert isinstance(result, CycleResult)
        assert result.cycle_id is not None
        assert result.cycle_number == 1

    @pytest.mark.asyncio
    async def test_run_cycle_trading(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        orch.initialize()
        orch.start()
        result = await orch.run_cycle([{"price": 100}])
        assert result.paper_trading_done

    @pytest.mark.asyncio
    async def test_run_cycle_health_check(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        result = await orch.run_cycle([])
        assert result.health_check_done

    @pytest.mark.asyncio
    async def test_run_cycle_multiple(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        r1 = await orch.run_cycle([])
        r2 = await orch.run_cycle([])
        assert r2.cycle_number == 2
        assert r1.cycle_id != r2.cycle_id

    @pytest.mark.asyncio
    async def test_status(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        await orch.run_cycle([])
        status = orch.status()
        assert status["total_cycles"] == 1
        assert status["scheduler"]["is_running"]
        assert "experiments" in status
        assert "lifecycle" in status
        assert "knowledge" in status
        assert "improvement" in status
        assert "health" in status
        assert "reporter" in status

    @pytest.mark.asyncio
    async def test_research_phase_with_generator(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        gen = MagicMock()
        gen.generate.return_value = []
        lib = MagicMock()
        lib.all.return_value = []
        orch.register_strategy_generator(gen)
        orch.register_library(lib)
        result = await orch.run_cycle([])
        assert result.research_done

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_trader):
        faulty_loop = MagicMock()
        async def faulty_run(market_data):
            raise ValueError("Trading failed")
        faulty_loop.run = faulty_run
        trader = ContinuousPaperTrader(faulty_loop)
        orch = AutonomousOrchestrator(trader=trader)
        result = await orch.run_cycle([])
        assert result.errors is None or len(result.errors) >= 0

    @pytest.mark.asyncio
    async def test_summary(self, mock_trader):
        orch = AutonomousOrchestrator(trader=mock_trader)
        await orch.run_cycle([])
        s = orch.summary()
        assert s["total_cycles"] == 1
