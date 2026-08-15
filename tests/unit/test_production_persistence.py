"""Tests for persistence layer — PersistenceStore, ProductionStore, NamespaceHelper."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from packages.production.persistence import PersistenceStore, ProductionStore, NamespaceHelper


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


class TestPersistenceStore:
    def test_put_and_get(self, store):
        store.put("test_ns", "key1", {"hello": "world"})
        val = store.get("test_ns", "key1")
        assert val == {"hello": "world"}

    def test_get_missing_key(self, store):
        val = store.get("test_ns", "does_not_exist")
        assert val is None

    def test_get_missing_namespace(self, store):
        val = store.get("no_such_ns", "key1")
        assert val is None

    def test_put_overwrite(self, store):
        store.put("test_ns", "key1", {"v": 1})
        store.put("test_ns", "key1", {"v": 2})
        val = store.get("test_ns", "key1")
        assert val == {"v": 2}

    def test_put_serializes_complex_types(self, store):
        store.put("test_ns", "complex", {"decimal_val": 1.5, "list": [1, 2, 3], "nested": {"a": 1}})
        val = store.get("test_ns", "complex")
        assert val == {"decimal_val": 1.5, "list": [1, 2, 3], "nested": {"a": 1}}

    def test_delete(self, store):
        store.put("test_ns", "key1", {"v": 1})
        store.delete("test_ns", "key1")
        val = store.get("test_ns", "key1")
        assert val is None

    def test_delete_missing_does_not_raise(self, store):
        store.delete("test_ns", "does_not_exist")

    def test_list_keys(self, store):
        store.put("test_ns", "b_key", {})
        store.put("test_ns", "a_key", {})
        keys = store.list_keys("test_ns")
        assert keys == ["a_key", "b_key"]

    def test_list_keys_empty(self, store):
        assert store.list_keys("empty_ns") == []

    def test_list_namespace(self, store):
        store.put("test_ns", "k1", {"data": 1})
        store.put("test_ns", "k2", {"data": 2})
        rows = store.list_namespace("test_ns")
        assert len(rows) == 2
        keys = [r["key"] for r in rows]
        vals = [r["value"] for r in rows]
        assert set(keys) == {"k1", "k2"}
        assert {"data": 1} in vals
        assert {"data": 2} in vals
        for r in rows:
            assert "updated_at" in r

    def test_list_namespace_empty(self, store):
        assert store.list_namespace("empty_ns") == []

    def test_count_none(self, store):
        assert store.count() == 0

    def test_count_namespace(self, store):
        store.put("ns1", "a", {})
        store.put("ns1", "b", {})
        store.put("ns2", "c", {})
        assert store.count("ns1") == 2
        assert store.count("ns2") == 1
        assert store.count() == 3

    def test_list_namespaces(self, store):
        store.put("alpha", "a", {})
        store.put("beta", "b", {})
        nss = store.list_namespaces()
        assert "alpha" in nss
        assert "beta" in nss

    def test_list_namespaces_when_empty(self, store):
        assert store.list_namespaces() == []

    def test_get_updated_at(self, store):
        store.put("test_ns", "k1", {})
        ts = store.get_updated_at("test_ns", "k1")
        assert ts is not None
        assert "T" in ts

    def test_get_updated_at_missing(self, store):
        assert store.get_updated_at("test_ns", "no_key") is None

    def test_put_batch(self, store):
        items = {"k1": {"val": 1}, "k2": {"val": 2}}
        count = store.put_batch("batch_ns", items)
        assert count == 2
        assert store.get("batch_ns", "k1") == {"val": 1}
        assert store.get("batch_ns", "k2") == {"val": 2}

    def test_put_batch_empty(self, store):
        assert store.put_batch("batch_ns", {}) == 0

    def test_clear_namespace(self, store):
        store.put("ns1", "a", {})
        store.put("ns1", "b", {})
        store.put("ns2", "c", {})
        assert store.clear_namespace("ns1") == 2
        assert store.count("ns1") == 0
        assert store.count("ns2") == 1

    def test_clear_namespace_empty(self, store):
        assert store.clear_namespace("empty_ns") == 0

    def test_close_twice_does_not_raise(self, store):
        store.close()
        store.close()

    def test_put_special_chars_in_key(self, store):
        store.put("ns", "key/with/slashes", {"data": 1})
        assert store.get("ns", "key/with/slashes") == {"data": 1}

    def test_put_none_value(self, store):
        store.put("ns", "none_val", None)
        assert store.get("ns", "none_val") is None

    def test_isolation_between_namespaces(self, store):
        store.put("ns_a", "x", {"belongs_to": "a"})
        store.put("ns_b", "x", {"belongs_to": "b"})
        assert store.get("ns_a", "x") == {"belongs_to": "a"}
        assert store.get("ns_b", "x") == {"belongs_to": "b"}


class TestProductionStore:
    def test_all_namespaces_have_helpers(self, prod):
        for ns in ProductionStore.NAMESPACES:
            if not hasattr(prod, ns):
                continue
            helper = getattr(prod, ns)
            assert isinstance(helper, NamespaceHelper)
            assert helper._namespace == ns

    def test_round_trip_via_helper(self, prod):
        prod.experiments.put("exp1", {"name": "test"})
        assert prod.experiments.get("exp1") == {"name": "test"}
        assert prod.experiments.keys() == ["exp1"]

    def test_list_via_helper(self, prod):
        prod.strategies.put("s1", {"name": "strat_a"})
        prod.strategies.put("s2", {"name": "strat_b"})
        rows = prod.strategies.list()
        assert len(rows) == 2

    def test_count_via_helper(self, prod):
        prod.alerts.put("a1", {"msg": "hello"})
        assert prod.alerts.count() == 1

    def test_delete_via_helper(self, prod):
        prod.trades.put("t1", {"qty": 10})
        prod.trades.delete("t1")
        assert prod.trades.get("t1") is None

    def test_put_batch_via_helper(self, prod):
        items = {"o1": {"order": 1}, "o2": {"order": 2}}
        assert prod.orders.put_batch(items) == 2
        assert prod.orders.count() == 2


class TestNamespaceHelper:
    def test_put_and_get(self, store):
        ns = NamespaceHelper(store, "custom")
        ns.put("k", {"val": 42})
        assert ns.get("k") == {"val": 42}

    def test_get_missing(self, store):
        ns = NamespaceHelper(store, "custom")
        assert ns.get("missing") is None

    def test_delete(self, store):
        ns = NamespaceHelper(store, "custom")
        ns.put("k", {})
        ns.delete("k")
        assert ns.get("k") is None

    def test_list_empty(self, store):
        ns = NamespaceHelper(store, "custom")
        assert ns.list() == []

    def test_list_with_entries(self, store):
        ns = NamespaceHelper(store, "custom")
        ns.put("a", {"n": 1})
        ns.put("b", {"n": 2})
        assert len(ns.list()) == 2

    def test_keys(self, store):
        ns = NamespaceHelper(store, "custom")
        ns.put("b", {})
        ns.put("a", {})
        assert ns.keys() == ["a", "b"]

    def test_count(self, store):
        ns = NamespaceHelper(store, "custom")
        assert ns.count() == 0
        ns.put("x", {})
        assert ns.count() == 1

    def test_put_batch(self, store):
        ns = NamespaceHelper(store, "custom")
        assert ns.put_batch({"k1": 1, "k2": 2}) == 2
        assert ns.count() == 2
