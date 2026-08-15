"""Persistence Layer — SQLite-backed store for all component state.

Uses stdlib sqlite3 with JSON blobs for flexibility.
Each component namespace gets its own table with key-value storage.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_MAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS store (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);
CREATE INDEX IF NOT EXISTS idx_store_namespace ON store(namespace);
"""


class PersistenceStore:
    """Thread-safe SQLite key-value store with namespacing."""

    def __init__(self, db_path: str = "data/quantlab.db"):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(_MAIN_SCHEMA)
        conn.commit()

    def put(self, namespace: str, key: str, value: Any) -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        serialized = json.dumps(value, default=str)
        conn.execute(
            "INSERT OR REPLACE INTO store (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (namespace, key, serialized, now),
        )
        conn.commit()

    def get(self, namespace: str, key: str) -> Any | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM store WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def delete(self, namespace: str, key: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM store WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        conn.commit()

    def list_keys(self, namespace: str) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT key FROM store WHERE namespace = ? ORDER BY key",
            (namespace,),
        ).fetchall()
        return [r["key"] for r in rows]

    def list_namespace(self, namespace: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT key, value, updated_at FROM store WHERE namespace = ? ORDER BY updated_at DESC",
            (namespace,),
        ).fetchall()
        return [
            {"key": r["key"], "value": json.loads(r["value"]), "updated_at": r["updated_at"]}
            for r in rows
        ]

    def count(self, namespace: str | None = None) -> int:
        conn = self._get_conn()
        if namespace:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM store WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM store").fetchone()
        return row["cnt"] if row else 0

    def list_namespaces(self) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT DISTINCT namespace FROM store ORDER BY namespace").fetchall()
        return [r["namespace"] for r in rows]

    def get_updated_at(self, namespace: str, key: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT updated_at FROM store WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
        return row["updated_at"] if row else None

    def put_batch(self, namespace: str, items: dict[str, Any]) -> int:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for key, value in items.items():
            conn.execute(
                "INSERT OR REPLACE INTO store (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
                (namespace, key, json.dumps(value, default=str), now),
            )
            count += 1
        conn.commit()
        return count

    def clear_namespace(self, namespace: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM store WHERE namespace = ?", (namespace,))
        conn.commit()
        return cursor.rowcount

    def prune_namespace(self, namespace: str, keep: int) -> int:
        """Keep only the `keep` most-recent rows (by updated_at) in a namespace.

        Bounded retention guard for high-volume namespaces (e.g. alerts) so they
        cannot silently grow to millions of rows and stall recovery/checkpointing.
        """
        if keep < 0:
            return 0
        conn = self._get_conn()
        stale = conn.execute(
            """
            SELECT key FROM store
            WHERE namespace = ?
              AND key NOT IN (
                SELECT key FROM store WHERE namespace = ?
                ORDER BY updated_at DESC LIMIT ?
              )
            """,
            (namespace, namespace, keep),
        ).fetchall()
        if not stale:
            return 0
        cursor = conn.executemany(
            "DELETE FROM store WHERE namespace = ? AND key = ?",
            [(namespace, r["key"]) for r in stale],
        )
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# ── Predefined namespaces ──────────────────────────────────────────


class ProductionStore:
    NAMESPACES = [
        "experiments",
        "strategies",
        "lifecycle",
        "trades",
        "orders",
        "portfolio",
        "positions",
        "analytics",
        "reports",
        "knowledge",
        "alerts",
        "scheduler",
        "observations",
        "config",
        "checkpoints",
        "plugins",
        "metrics",
    ]

    def __init__(self, store: PersistenceStore):
        self._store = store

    @property
    def experiments(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "experiments")

    @property
    def strategies(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "strategies")

    @property
    def lifecycle(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "lifecycle")

    @property
    def trades(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "trades")

    @property
    def orders(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "orders")

    @property
    def portfolio(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "portfolio")

    @property
    def positions(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "positions")

    @property
    def analytics(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "analytics")

    @property
    def reports(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "reports")

    @property
    def knowledge(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "knowledge")

    @property
    def alerts(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "alerts")

    @property
    def scheduler(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "scheduler")

    @property
    def observations(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "observations")

    @property
    def checkpoints(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "checkpoints")

    @property
    def metrics(self) -> "NamespaceHelper":
        return NamespaceHelper(self._store, "metrics")


class NamespaceHelper:
    def __init__(self, store: PersistenceStore, namespace: str):
        self._store = store
        self._namespace = namespace

    def put(self, key: str, value: Any) -> None:
        self._store.put(self._namespace, key, value)

    def get(self, key: str) -> Any | None:
        return self._store.get(self._namespace, key)

    def delete(self, key: str) -> None:
        self._store.delete(self._namespace, key)

    def list(self) -> list[dict[str, Any]]:
        return self._store.list_namespace(self._namespace)

    def keys(self) -> list[str]:
        return self._store.list_keys(self._namespace)

    def count(self) -> int:
        return self._store.count(self._namespace)

    def put_batch(self, items: dict[str, Any]) -> int:
        return self._store.put_batch(self._namespace, items)
