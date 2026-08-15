"""Tests for RecoverySystem — save, load, recover, hooks, checkpoint detection."""

import os
import tempfile

import pytest

from packages.production.persistence import PersistenceStore
from packages.production.recovery import RecoverySystem, RecoveryResult


@pytest.fixture
def db_path():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def store(db_path):
    return PersistenceStore(db_path)


@pytest.fixture
def recovery(store):
    return RecoverySystem(store)


class TestRecoverySystem:
    def test_save_and_load_state(self, recovery):
        recovery.save_state("strategies", "s1", {"name": "strat_a"})
        val = recovery.load_state("strategies", "s1")
        assert val == {"name": "strat_a"}

    def test_load_missing_state(self, recovery):
        assert recovery.load_state("strategies", "no_such") is None

    def test_register_recovery_hook(self, recovery):
        called = []
        recovery.register_recovery_hook("strategies", lambda v: called.append(v))
        recovery.save_state("strategies", "s1", {"name": "test"})
        recovery.recover()
        assert called == [{"name": "test"}]

    def test_recover_with_no_data(self, recovery):
        result = recovery.recover()
        assert isinstance(result, RecoveryResult)
        assert result.success is True
        assert result.recovered_namespaces == []
        assert result.failed_namespaces == []
        assert result.errors == []

    def test_recover_stores_recovered_namespaces(self, recovery):
        recovery.save_state("strategies", "s1", {"n": 1})
        recovery.save_state("trades", "t1", {"n": 2})
        result = recovery.recover()
        assert "strategies" in result.recovered_namespaces
        assert "trades" in result.recovered_namespaces
        assert result.success is True

    def test_recover_hook_failure_does_not_block(self, recovery):
        recovery.register_recovery_hook("strategies", lambda v: 1 / 0)
        recovery.save_state("strategies", "s1", {"n": 1})
        result = recovery.recover()
        assert "strategies" in result.recovered_namespaces
        assert len(result.errors) == 1
        assert "hook:strategies" in result.errors[0]

    def test_multiple_hooks_per_namespace(self, recovery):
        order = []
        recovery.register_recovery_hook("strategies", lambda v: order.append("a"))
        recovery.register_recovery_hook("strategies", lambda v: order.append("b"))
        recovery.save_state("strategies", "s1", {"n": 1})
        recovery.recover()
        assert order == ["a", "b"]

    def test_hooks_only_called_for_matching_namespace(self, recovery):
        called = []
        recovery.register_recovery_hook("strategies", lambda v: called.append(1))
        recovery.save_state("trades", "t1", {"n": 1})
        recovery.recover()
        assert called == []

    def test_checkpoint_exists_returns_false(self, recovery):
        assert recovery.checkpoint_exists() is False

    def test_checkpoint_exists_returns_true(self, recovery, store):
        store.put("checkpoints", "ckpt-1", {"data": {}})
        assert recovery.checkpoint_exists() is True

    def test_last_checkpoint_none(self, recovery):
        assert recovery.last_checkpoint() is None

    def test_last_checkpoint_returns_latest(self, recovery, store):
        store.put("checkpoints", "ckpt-1", {})
        store.put("checkpoints", "ckpt-2", {})
        assert recovery.last_checkpoint() == "ckpt-2"

    def test_recovery_summary_after_recovery(self, recovery):
        recovery.save_state("strategies", "s1", {"n": 1})
        result = recovery.recover()
        summary = recovery.recovery_summary(result)
        assert summary["success"] is True
        assert summary["namespaces_recovered"] == 1
        assert summary["namespaces_failed"] == 0
        assert summary["total_errors"] == 0
        assert summary["has_checkpoint"] is False
        assert summary["last_checkpoint"] is None
        assert summary["total_entries"] > 0

    def test_recovery_summary_auto_recover(self, recovery):
        recovery.save_state("strategies", "s1", {"n": 1})
        summary = recovery.recovery_summary()
        assert summary["success"] is True
        assert summary["namespaces_recovered"] == 1

    def test_recover_namespace_failure_logged(self, recovery, store):
        recovery.save_state("strategies", "s1", {"n": 1})
        result = recovery.recover()
        assert result.success is True
        assert len(result.failed_namespaces) == 0
