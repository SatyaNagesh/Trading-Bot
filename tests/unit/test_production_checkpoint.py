"""Tests for Checkpointer — create, restore, list, latest, summary."""

import os
import tempfile

import pytest

from packages.production.persistence import PersistenceStore, ProductionStore
from packages.production.checkpoint import Checkpointer, Checkpoint


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
def prod(store):
    return ProductionStore(store)


@pytest.fixture
def checkpointer(store):
    return Checkpointer(store)


class TestCheckpointer:
    def test_create_checkpoint_returns_checkpoint(self, checkpointer, store):
        store.put("trades", "t1", {"id": 1})
        ckpt = checkpointer.create_checkpoint()
        assert isinstance(ckpt, Checkpoint)
        assert ckpt.id.startswith("ckpt-")
        assert ckpt.entry_count >= 1
        assert ckpt.size_bytes > 0
        assert "trades" in ckpt.namespaces

    def test_create_checkpoint_empty_store(self, checkpointer):
        ckpt = checkpointer.create_checkpoint()
        assert ckpt.entry_count == 0
        assert ckpt.size_bytes > 0

    def test_create_checkpoint_excludes_ephemeral(self, checkpointer, store):
        store.put("alerts", "a1", {"m": 1})
        store.put("trades", "t1", {"id": 1})
        ckpt = checkpointer.create_checkpoint()
        assert "alerts" not in ckpt.namespaces
        assert "checkpoints" not in ckpt.namespaces

    def test_create_checkpoint_limits_entries_per_ns(self, checkpointer, store):
        for i in range(100):
            store.put("trades", f"t{i}", {"i": i})
        ckpt = checkpointer.create_checkpoint()
        assert ckpt.entry_count == 100

    def test_create_checkpoint_custom_namespaces(self, checkpointer, store):
        store.put("strategies", "s1", {"n": "a"})
        store.put("trades", "t1", {"id": 1})
        ckpt = checkpointer.create_checkpoint(namespaces=["strategies"])
        assert ckpt.namespaces == ["strategies"]
        assert ckpt.entry_count == 1

    def test_create_checkpoint_increments_counter(self, checkpointer):
        c1 = checkpointer.create_checkpoint()
        c2 = checkpointer.create_checkpoint()
        assert c2.id.startswith("ckpt-2-")
        assert c1.id != c2.id

    def test_restore_checkpoint(self, checkpointer, store):
        store.put("strategies", "s1", {"name": "strat_a"})
        ckpt = checkpointer.create_checkpoint()
        store.delete("strategies", "s1")
        assert store.get("strategies", "s1") is None
        result = checkpointer.restore_checkpoint(ckpt.id)
        assert result["checkpoint_id"] == ckpt.id
        assert "strategies" in result["restored"]
        assert store.get("strategies", "s1") == {"name": "strat_a"}

    def test_restore_checkpoint_invalid_raises(self, checkpointer):
        with pytest.raises(KeyError, match="not found"):
            checkpointer.restore_checkpoint("nonexistent")

    def test_latest_checkpoint_none(self, checkpointer):
        assert checkpointer.latest_checkpoint() is None

    def test_latest_checkpoint_returns_most_recent(self, checkpointer):
        checkpointer.create_checkpoint()
        c2 = checkpointer.create_checkpoint()
        latest = checkpointer.latest_checkpoint()
        assert latest["key"] == c2.id

    def test_list_checkpoints(self, checkpointer):
        checkpointer.create_checkpoint()
        checkpointer.create_checkpoint()
        lst = checkpointer.list_checkpoints()
        assert len(lst) == 2

    def test_list_checkpoints_limit(self, checkpointer):
        for _ in range(10):
            checkpointer.create_checkpoint()
        lst = checkpointer.list_checkpoints(limit=3)
        assert len(lst) == 3

    def test_summary_empty(self, checkpointer):
        s = checkpointer.summary()
        assert s["total_checkpoints"] == 0
        assert s["latest"] is None
        assert s["total_size_bytes"] == 0

    def test_summary_with_checkpoints(self, checkpointer):
        checkpointer.create_checkpoint()
        checkpointer.create_checkpoint()
        s = checkpointer.summary()
        assert s["total_checkpoints"] == 2
        assert s["latest"] is not None
        assert s["total_size_bytes"] > 0
