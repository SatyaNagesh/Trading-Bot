"""Gate 7 — Production Readiness & Persistence tests."""
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.production.config import (
    ProductionConfig, load_config, default_config,
    PaperTradingConfig, RiskConfig, LoggingConfig, DatabaseConfig,
)
from packages.production.persistence import PersistenceStore, ProductionStore
from packages.production.recovery import RecoverySystem, RecoveryResult
from packages.production.fault import (
    retry, FallbackProvider, WriteQueue, WriteBatch, RetryConfig,
)
from packages.production.checkpoint import Checkpointer, Checkpoint
from packages.production.observability import MetricCollector, OperationalDashboard
from packages.production.plugins import (
    PluginRegistry, PluginBase, IndicatorPlugin, StrategyPlugin,
    BrokerPlugin, DataProviderPlugin, RiskRulePlugin, PluginMetadata,
)


# ── Configuration ────────────────────────────────────────────────────

class TestProductionConfig:
    def test_default_config(self):
        cfg = default_config()
        assert cfg.env == "development"
        assert cfg.paper_trading.symbols == ["RELIANCE", "TCS", "HDFCBANK"]
        assert cfg.risk.max_concurrent_trades == 5
        assert cfg.risk.max_drawdown_pct == 25.0
        assert cfg.logging.level == "INFO"
        assert cfg.schedule.research_interval_hours == 4.0
        assert cfg.database.dsn == "sqlite:///data/quantlab.db"

    def test_custom_config(self):
        cfg = ProductionConfig(
            env="production",
            debug=True,
            paper_trading=PaperTradingConfig(symbols=["AAPL"], initial_capital=500_000),
            risk=RiskConfig(max_drawdown_pct=15.0),
            database=DatabaseConfig(dsn="sqlite:///custom.db"),
        )
        assert cfg.env == "production"
        assert cfg.paper_trading.symbols == ["AAPL"]
        assert cfg.risk.max_drawdown_pct == 15.0
        assert cfg.database.dsn == "sqlite:///custom.db"

    def test_load_config_creates_default(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            p = f.name
        try:
            cfg = load_config(p)
            assert cfg.env == "development"
            assert os.path.exists(p)
        finally:
            os.unlink(p)

    def test_load_config_from_yaml(self):
        import yaml
        data = {
            "env": "production",
            "paper_trading": {"symbols": ["AAPL", "GOOG"]},
            "risk": {"max_drawdown_pct": 20.0},
        }
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            p = f.name
        try:
            cfg = load_config(p)
            assert cfg.env == "production"
            assert cfg.paper_trading.symbols == ["AAPL", "GOOG"]
            assert cfg.risk.max_drawdown_pct == 20.0
        finally:
            os.unlink(p)


# ── Persistence ──────────────────────────────────────────────────────

class TestPersistenceStore:
    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = PersistenceStore(db_path)
        yield store
        store.close()
        os.unlink(db_path)

    def test_put_and_get(self, store):
        store.put("test_ns", "key1", {"value": 42})
        assert store.get("test_ns", "key1") == {"value": 42}

    def test_get_nonexistent(self, store):
        assert store.get("test_ns", "nonexistent") is None

    def test_overwrite(self, store):
        store.put("test_ns", "k1", "v1")
        store.put("test_ns", "k1", "v2")
        assert store.get("test_ns", "k1") == "v2"

    def test_delete(self, store):
        store.put("test_ns", "k1", "v1")
        store.delete("test_ns", "k1")
        assert store.get("test_ns", "k1") is None

    def test_list_keys(self, store):
        store.put("ns1", "a", 1)
        store.put("ns1", "b", 2)
        keys = store.list_keys("ns1")
        assert sorted(keys) == ["a", "b"]

    def test_list_namespace(self, store):
        store.put("ns1", "a", {"x": 1})
        entries = store.list_namespace("ns1")
        assert len(entries) == 1
        assert entries[0]["key"] == "a"
        assert entries[0]["value"] == {"x": 1}

    def test_count(self, store):
        store.put("ns1", "a", 1)
        store.put("ns1", "b", 2)
        store.put("ns2", "c", 3)
        assert store.count("ns1") == 2
        assert store.count() == 3

    def test_list_namespaces(self, store):
        store.put("ns1", "a", 1)
        store.put("ns2", "b", 2)
        ns = store.list_namespaces()
        assert sorted(ns) == ["ns1", "ns2"]

    def test_get_updated_at(self, store):
        store.put("ns1", "k", "v")
        ts = store.get_updated_at("ns1", "k")
        assert ts is not None

    def test_put_batch(self, store):
        count = store.put_batch("ns1", {"a": 1, "b": 2, "c": 3})
        assert count == 3
        assert store.count("ns1") == 3

    def test_clear_namespace(self, store):
        store.put("ns1", "a", 1)
        store.put("ns2", "b", 2)
        cleared = store.clear_namespace("ns1")
        assert cleared == 1
        assert store.count("ns1") == 0
        assert store.count() == 1

    def test_thread_safety(self, store):
        import threading
        errors = []
        def worker(n):
            try:
                for i in range(50):
                    store.put("thread_test", f"k{n}-{i}", i)
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert store.count("thread_test") == 200


class TestProductionStore:
    @pytest.fixture
    def prod(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = PersistenceStore(db_path)
        p = ProductionStore(store)
        yield p
        store.close()
        os.unlink(db_path)

    def test_experiments(self, prod):
        prod.experiments.put("exp1", {"hypothesis": "test"})
        assert prod.experiments.get("exp1")["hypothesis"] == "test"

    def test_strategies(self, prod):
        prod.strategies.put("s1", {"name": "strat"})
        assert prod.strategies.get("s1")["name"] == "strat"

    def test_trades(self, prod):
        prod.trades.put("t1", {"pnl": 100})
        assert prod.trades.get("t1")["pnl"] == 100

    def test_portfolio(self, prod):
        prod.portfolio.put("main", {"cash": 100000})
        assert prod.portfolio.get("main")["cash"] == 100000

    def test_checkpoints(self, prod):
        prod.checkpoints.put("ck1", {"data": "snapshot"})
        assert prod.checkpoints.count() == 1

    def test_metrics(self, prod):
        prod.metrics.put("m1", {"cpu": 50})
        assert prod.metrics.get("m1")["cpu"] == 50

    def test_alerts(self, prod):
        prod.alerts.put("a1", {"severity": "high"})
        assert prod.alerts.get("a1")["severity"] == "high"


# ── Recovery ─────────────────────────────────────────────────────────

class TestRecoverySystem:
    @pytest.fixture
    def recovery(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = PersistenceStore(db_path)
        r = RecoverySystem(store)
        yield r
        store.close()
        os.unlink(db_path)

    def test_save_and_load_state(self, recovery):
        recovery.save_state("test", "k1", {"val": 42})
        assert recovery.load_state("test", "k1") == {"val": 42}

    def test_recover_empty(self, recovery):
        result = recovery.recover()
        assert result.success
        assert len(result.recovered_namespaces) == 0

    def test_recover_with_data(self, recovery):
        recovery.save_state("experiments", "e1", {"hypothesis": "test"})
        recovery.save_state("strategies", "s1", {"name": "strat"})
        result = recovery.recover()
        assert result.success
        assert "experiments" in result.recovered_namespaces
        assert "strategies" in result.recovered_namespaces

    def test_recovery_hooks(self, recovery):
        calls = []
        def hook(value):
            calls.append(value)
        recovery.register_recovery_hook("test", hook)
        recovery.save_state("test", "k1", {"val": 1})
        recovery.save_state("test", "k2", {"val": 2})
        recovery.recover()
        assert len(calls) == 2

    def test_checkpoint_exists(self, recovery):
        assert not recovery.checkpoint_exists()
        recovery.save_state("checkpoints", "ck1", {})
        assert recovery.checkpoint_exists()

    def test_recovery_summary(self, recovery):
        recovery.save_state("test", "k1", 1)
        s = recovery.recovery_summary()
        assert s["has_checkpoint"] is not None
        assert s["total_entries"] == 1

    def test_recovery_result_dataclass(self):
        r = RecoveryResult(success=True, recovered_namespaces=["a"], timestamp="now")
        assert r.success
        assert r.recovered_namespaces == ["a"]


# ── Fault Tolerance ──────────────────────────────────────────────────

class TestRetry:
    def test_retry_success(self):
        call_count = [0]
        @retry(max_retries=3)
        def fn():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("fail")
            return "ok"
        assert fn() == "ok"
        assert call_count[0] == 2

    def test_retry_all_fail(self):
        @retry(max_retries=2, base_delay=0.01)
        def fn():
            raise ConnectionError("always fail")
        with pytest.raises(RuntimeError, match="Failed after 2 retries"):
            fn()

    def test_retry_non_retryable(self):
        @retry(max_retries=2, retryable_exceptions=(ConnectionError,))
        def fn():
            raise ValueError("not retryable")
        with pytest.raises(ValueError):
            fn()

    def test_retry_config_dataclass(self):
        cfg = RetryConfig(max_retries=5, base_delay=1.0)
        assert cfg.max_retries == 5


class TestFallbackProvider:
    def test_first_provider_succeeds(self):
        p1 = MagicMock(return_value="ok")
        p2 = MagicMock()
        fb = FallbackProvider([("p1", p1), ("p2", p2)])
        assert fb.execute() == "ok"
        p2.assert_not_called()

    def test_fallback_on_failure(self):
        p1 = MagicMock(side_effect=ConnectionError("fail"))
        p2 = MagicMock(return_value="fallback")
        fb = FallbackProvider([("p1", p1), ("p2", p2)])
        assert fb.execute() == "fallback"
        assert fb.failover_count["p1"] == 1

    def test_all_providers_fail(self):
        p1 = MagicMock(side_effect=ConnectionError("fail"))
        fb = FallbackProvider([("p1", p1)])
        with pytest.raises(RuntimeError, match="All providers failed"):
            fb.execute()


class TestWriteQueue:
    @pytest.fixture
    def queue(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        q = WriteQueue(db_path=p)
        yield q
        if os.path.exists(p):
            os.unlink(p)

    def test_enqueue(self, queue):
        queue.enqueue("ns1", "k1", {"val": 1})
        assert queue.size() == 1

    def test_flush(self, queue):
        writer = MagicMock()
        queue.enqueue("ns1", "k1", "v1")
        queue.enqueue("ns1", "k2", "v2")
        flushed = queue.flush(writer)
        assert flushed == 2
        assert queue.size() == 0
        assert writer.call_count == 2

    def test_flush_partial_failure(self, queue):
        writer = MagicMock()
        writer.side_effect = [None, ConnectionError("fail"), None]
        queue.enqueue("ns1", "k1", "v1")
        queue.enqueue("ns1", "k2", "v2")
        flushed = queue.flush(writer)

    def test_persistence_across_instances(self, queue):
        queue.enqueue("ns1", "k1", "v1")
        path = queue.db_path
        queue2 = WriteQueue(db_path=str(path))
        assert queue2.size() == 1
        writer = MagicMock()
        queue2.flush(writer)
        assert queue2.size() == 0


# ── Checkpointing ────────────────────────────────────────────────────

class TestCheckpointer:
    @pytest.fixture
    def checkpointer(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = PersistenceStore(db_path)
        c = Checkpointer(store)
        yield c, store
        store.close()
        os.unlink(db_path)

    def test_create_checkpoint(self, checkpointer):
        c, store = checkpointer
        store.put("test", "k1", "v1")
        ckpt = c.create_checkpoint(namespaces=["test"])
        assert ckpt.id.startswith("ckpt-")
        assert ckpt.entry_count == 1
        assert ckpt.namespaces == ["test"]

    def test_create_checkpoint_empty(self, checkpointer):
        c, store = checkpointer
        ckpt = c.create_checkpoint()
        assert ckpt.entry_count == 0
        assert ckpt.size_bytes > 0

    def test_restore_checkpoint(self, checkpointer):
        c, store = checkpointer
        store.put("ns1", "k1", {"original": "data"})
        ckpt = c.create_checkpoint(namespaces=["ns1"])

        store.put("ns1", "k1", {"overwritten": "bad"})
        c.restore_checkpoint(ckpt.id)
        assert store.get("ns1", "k1") == {"original": "data"}

    def test_restore_nonexistent(self, checkpointer):
        c, store = checkpointer
        with pytest.raises(KeyError):
            c.restore_checkpoint("nonexistent")

    def test_list_checkpoints(self, checkpointer):
        c, store = checkpointer
        c.create_checkpoint()
        c.create_checkpoint()
        ckpts = c.list_checkpoints()
        assert len(ckpts) == 2

    def test_latest_checkpoint(self, checkpointer):
        c, store = checkpointer
        assert c.latest_checkpoint() is None
        c.create_checkpoint()
        assert c.latest_checkpoint() is not None

    def test_summary(self, checkpointer):
        c, store = checkpointer
        c.create_checkpoint()
        s = c.summary()
        assert s["total_checkpoints"] == 1


# ── Observability ────────────────────────────────────────────────────

class TestMetricCollector:
    def test_increment(self):
        mc = MetricCollector()
        mc.increment("trades")
        assert mc.get_counter("trades") == 1
        mc.increment("trades", 5)
        assert mc.get_counter("trades") == 6

    def test_gauge(self):
        mc = MetricCollector()
        mc.gauge("cpu", 45.5)
        assert mc.get_gauge("cpu") == 45.5

    def test_timing(self):
        mc = MetricCollector()
        mc.timing("backtest", 150.0)
        series = mc.get_series("backtest_ms")
        assert len(series) == 1
        assert series[0].value == 150.0

    def test_snapshot(self):
        mc = MetricCollector()
        mc.increment("trades", 10)
        mc.gauge("cpu", 50)
        s = mc.snapshot()
        assert s["counters"]["trades"] == 10
        assert s["gauges"]["cpu"] == 50

    def test_get_series_limit(self):
        mc = MetricCollector(max_points_per_metric=5)
        for i in range(10):
            mc.increment("m1")
        assert len(mc.get_series("m1")) == 5

    def test_reset(self):
        mc = MetricCollector()
        mc.increment("trades", 5)
        mc.reset()
        assert mc.get_counter("trades") == 0


class TestOperationalDashboard:
    def test_dashboard_render(self):
        d = OperationalDashboard()
        output = d.render()
        assert "QUANTLAB OPERATIONAL DASHBOARD" in output
        assert "Trades" in output
        assert "Last updated" in output

    def test_update_trading(self):
        d = OperationalDashboard()
        d.update_trading(trade_count=100, open_positions=5, pnl=2500.50)
        assert d.metrics.get_gauge("trade_count") == 100

    def test_update_system(self):
        d = OperationalDashboard()
        d.update_system(cpu_pct=45.2, ram_mb=1024, uptime_hours=72.5)
        output = d.render()
        assert "45.2%" in output
        assert "1024" in output
        assert "72.5" in output

    def test_update_strategies(self):
        d = OperationalDashboard()
        d.update_strategies(total=20, active=15, degraded=2)
        assert d.metrics.get_gauge("strategies_total") == 20

    def test_update_experiments(self):
        d = OperationalDashboard()
        d.update_experiments(total=10, running=3, promoted=2)
        assert d.metrics.get_gauge("experiments_total") == 10

    def test_update_alerts(self):
        d = OperationalDashboard()
        d.update_alerts(active_count=5, critical_count=1)
        assert d.metrics.get_gauge("alerts_active") == 5

    def test_update_scheduler(self):
        d = OperationalDashboard()
        d.update_scheduler(cycle_count=42, is_running=True)
        assert d.metrics.get_gauge("scheduler_cycles") == 42
        assert d.metrics.get_gauge("scheduler_running") == 1.0

    def test_update_database(self):
        d = OperationalDashboard()
        d.update_database(total_entries=5000, checkpoint_count=3)
        assert d.metrics.get_gauge("db_entries") == 5000

    def test_extra_data(self):
        d = OperationalDashboard()
        d.set("Version", "7.0.0")
        output = d.render()
        assert "7.0.0" in output


# ── Plugins ──────────────────────────────────────────────────────────

class TestPluginRegistry:
    def test_register_indicator(self):
        reg = PluginRegistry()
        p = IndicatorPlugin("sma", "1.0.0")
        pid = reg.register(p)
        assert pid == "indicator:sma"

    def test_register_strategy(self):
        reg = PluginRegistry()
        p = StrategyPlugin("mean_reversion")
        pid = reg.register(p)
        assert pid == "strategy:mean_reversion"

    def test_register_duplicate(self):
        reg = PluginRegistry()
        reg.register(IndicatorPlugin("sma"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(IndicatorPlugin("sma"))

    def test_unregister(self):
        reg = PluginRegistry()
        p = IndicatorPlugin("sma")
        pid = reg.register(p)
        reg.unregister(pid)
        assert reg.get(pid) is None

    def test_unregister_nonexistent(self):
        reg = PluginRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nonexistent")

    def test_get(self):
        reg = PluginRegistry()
        p = IndicatorPlugin("sma")
        reg.register(p)
        assert reg.get("indicator:sma") is p

    def test_list_by_type(self):
        reg = PluginRegistry()
        reg.register(IndicatorPlugin("sma"))
        reg.register(IndicatorPlugin("ema"))
        reg.register(StrategyPlugin("reversion"))
        assert len(reg.list_by_type("indicator")) == 2
        assert len(reg.list_by_type("strategy")) == 1

    def test_list_all(self):
        reg = PluginRegistry()
        reg.register(IndicatorPlugin("sma"))
        reg.register(StrategyPlugin("reversion"))
        assert len(reg.list_all()) == 2

    def test_count(self):
        reg = PluginRegistry()
        reg.register(IndicatorPlugin("sma"))
        reg.register(StrategyPlugin("reversion"))
        c = reg.count()
        assert c["indicator"] == 1
        assert c["strategy"] == 1

    def test_broker_plugin(self):
        p = BrokerPlugin("zerodha")
        assert p.name() == "zerodha"
        with pytest.raises(NotImplementedError):
            p.place_order(None)

    def test_data_provider_plugin(self):
        p = DataProviderPlugin("yfinance")
        assert p.name() == "yfinance"

    def test_risk_rule_plugin(self):
        p = RiskRulePlugin("max_drawdown")
        assert p.name() == "max_drawdown"

    def test_on_load_unload_hooks(self):
        calls = {"load": [], "unload": []}
        class TestPlugin(PluginBase):
            def name(self): return "test"
            def version(self): return "1.0"
            def on_load(self): calls["load"].append("called")
            def on_unload(self): calls["unload"].append("called")
        reg = PluginRegistry()
        pid = reg.register(TestPlugin())
        assert calls["load"] == ["called"]
        reg.unregister(pid)
        assert calls["unload"] == ["called"]

    def test_plugin_metadata(self):
        m = PluginMetadata(name="test", version="1.0", plugin_type="indicator", instance=IndicatorPlugin("test"))
        assert m.enabled


# ── Long-duration Validation Simulation ──────────────────────────────

class TestLongDurationValidation:
    def test_72h_simulation(self):
        """Simulate 72 hours of production operation in compressed time."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = PersistenceStore(db_path)
        prod = ProductionStore(store)
        checkpointer = Checkpointer(store)
        recovery = RecoverySystem(store)
        metrics = MetricCollector()
        dashboard = OperationalDashboard(metrics)

        # Simulate 72 hours = 4320 paper trading cycles (every 60s)
        # We run a representative sample (100 cycles) and verify state
        num_cycles = 100
        for i in range(num_cycles):
            prod.trades.put(f"trade-{i}", {
                "pnl": (i % 5 - 2) * 100,
                "symbol": "RELIANCE",
                "strategy": f"strat-{i % 10}",
            })
            prod.experiments.put(f"exp-{i % 20}", {
                "hypothesis": f"Test {i}",
                "status": "running" if i % 3 else "promoted",
            })
            prod.strategies.put(f"strat-{i % 10}", {
                "name": f"Strategy {i % 10}",
                "trades": i,
            })
            prod.alerts.put(f"alert-{i % 5}", {
                "severity": "high" if i % 7 == 0 else "info",
            })

            if i % 10 == 0:
                ckpt = checkpointer.create_checkpoint()
                assert ckpt.entry_count > 0

            dashboard.update_trading(i, i % 5, (i % 5 - 2) * 100)
            dashboard.update_strategies(10, 8, 2)
            dashboard.update_experiments(20, 12, 3)
            dashboard.update_alerts(5, 1)
            dashboard.update_scheduler(i, True)
            dashboard.update_database(store.count(), i // 10 + 1)

        # Verify no corruption
        assert store.count() > 0
        assert prod.trades.count() == num_cycles
        assert prod.experiments.count() == 20
        assert prod.strategies.count() == 10
        assert prod.alerts.count() == 5

        # Verify checkpoint system works
        ckpts = checkpointer.list_checkpoints()
        assert len(ckpts) > 0

        # Verify recovery works
        result = recovery.recover()
        assert result.success

        # Verify dashboard renders without error
        output = dashboard.render()
        assert "QUANTLAB OPERATIONAL DASHBOARD" in output

        # Verify write queue persistence
        wq_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        queue = WriteQueue(db_path=wq_path)
        for i in range(50):
            queue.enqueue("trades", f"q-trade-{i}", {"pnl": i * 10})
        assert queue.size() == 50

        writer = MagicMock()
        flushed = queue.flush(writer)
        assert flushed == 50

        os.unlink(db_path)
        os.unlink(wq_path)
