"""Tests for IntegratedBot start/stop lifecycle and edge cases."""

import os
import tempfile

import pytest

from packages.integration.pipeline import IntegratedBot, IntegrationConfig


@pytest.fixture
def db_path():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestIntegratedBotLifecycle:
    def test_create_with_defaults(self):
        bot = IntegratedBot()
        assert bot._running is False
        assert bot._cycle_count == 0

    def test_create_with_config(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        assert bot.config.db_path == db_path

    def test_start_stop(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.start()
        assert bot._running is True
        bot.stop()
        assert bot._running is False

    def test_stop_without_start(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.stop()

    def test_start_twice(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.start()
        bot.start()
        bot.stop()

    def test_restore_state_after_start_stop(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.start()
        bot.checkpointer.create_checkpoint()
        bot.stop()

        bot2 = IntegratedBot(config=cfg)
        bot2.start()
        latest = bot2.checkpointer.latest_checkpoint()
        assert latest is not None
        bot2.stop()

    def test_recovery_after_checkpoint(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.store.put("trades", "t1", {"id": 1})
        bot.checkpointer.create_checkpoint()
        bot.stop()

        bot2 = IntegratedBot(config=cfg)
        bot2.start()
        assert bot2.store.get("trades", "t1") == {"id": 1}
        bot2.stop()

    def test_persist_state_does_not_raise(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot._persist_state()

    def test_orchestrator_start_stop(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.orchestrator.start()
        bot.orchestrator.stop()

    def test_multiple_start_stop_cycles(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        for _ in range(5):
            bot.start()
            bot.stop()

    def test_concurrent_checkpoint_safety(self, db_path):
        import threading
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        results = []

        def create_ckpt():
            try:
                ckpt = bot.checkpointer.create_checkpoint()
                results.append(("ok", ckpt.id))
            except Exception as e:
                results.append(("error", str(e)))

        threads = [threading.Thread(target=create_ckpt) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        errors = [r for r in results if r[0] == "error"]
        assert len(errors) == 0, f"Checkpoint errors: {errors}"

    def test_dashboard_status_tracking(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.dashboard.set("status", "initialized")
        bot.start()
        bot.stop()
        bot.dashboard.set("status", "stopped")

    def test_health_metrics_during_lifecycle(self, db_path):
        cfg = IntegrationConfig(db_path=db_path)
        bot = IntegratedBot(config=cfg)
        bot.metrics.gauge("test_metric", 42)
        bot.start()
        bot.stop()
