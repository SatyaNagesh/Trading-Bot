"""Checkpointing — periodic snapshots of all component state."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.production.persistence import PersistenceStore, ProductionStore


@dataclass
class Checkpoint:
    id: str
    timestamp: str
    namespaces: list[str]
    entry_count: int
    size_bytes: int = 0


class Checkpointer:
    def __init__(self, store: PersistenceStore):
        self._store = store
        self._prod = ProductionStore(store)
        self._checkpoint_count = 0

    _EPHEMERAL_NS = frozenset({"checkpoints", "alerts", "plugins", "metrics"})
    _MAX_ENTRIES_PER_NS = 5000

    def create_checkpoint(self, namespaces: list[str] | None = None) -> Checkpoint:
        self._checkpoint_count += 1
        now = datetime.now(timezone.utc).isoformat()
        ckpt_id = f"ckpt-{self._checkpoint_count}-{now.replace(':', '-')}"

        snapshot: dict[str, dict[str, Any]] = {}
        total_entries = 0
        target_ns = [
            ns for ns in (namespaces or ProductionStore.NAMESPACES) if ns not in self._EPHEMERAL_NS
        ]

        for ns in target_ns:
            entries = self._store.list_namespace(ns)
            if entries:
                snapshot[ns] = {e["key"]: e["value"] for e in entries[: self._MAX_ENTRIES_PER_NS]}
                total_entries += len(snapshot[ns])

        import json

        serialized = json.dumps(snapshot, default=str)
        size = len(serialized.encode("utf-8"))

        self._prod.checkpoints.put(
            ckpt_id,
            {
                "id": ckpt_id,
                "timestamp": now,
                "namespaces": target_ns,
                "entry_count": total_entries,
                "size_bytes": size,
                "data": snapshot,
            },
        )

        return Checkpoint(
            id=ckpt_id,
            timestamp=now,
            namespaces=target_ns,
            entry_count=total_entries,
            size_bytes=size,
        )

    def restore_checkpoint(self, ckpt_id: str) -> dict[str, Any]:
        ckpt = self._prod.checkpoints.get(ckpt_id)
        if not ckpt:
            raise KeyError(f"Checkpoint {ckpt_id} not found")

        data = ckpt.get("data", {})
        restored = {}
        for ns, entries in data.items():
            count = self._store.put_batch(ns, entries)
            restored[ns] = count

        return {"checkpoint_id": ckpt_id, "restored": restored}

    def list_checkpoints(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._prod.checkpoints.list()[:limit]

    def latest_checkpoint(self) -> dict[str, Any] | None:
        all_c = self._prod.checkpoints.list()
        return all_c[0] if all_c else None

    def summary(self) -> dict[str, Any]:
        ckpts = self._prod.checkpoints.list()
        return {
            "total_checkpoints": len(ckpts),
            "latest": ckpts[0] if ckpts else None,
            "total_size_bytes": sum(c["value"]["size_bytes"] for c in ckpts) if ckpts else 0,
        }
