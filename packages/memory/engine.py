"""Memory Engine — episodic, semantic, and working memory tiers."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np

from packages.core.logging import get_logger

logger = get_logger("memory_engine")

MemoryValue = str | dict[str, Any] | list[Any] | float | int | np.ndarray


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: str(uuid4()))
    key: str = ""
    value: MemoryValue = ""
    namespace: str = "default"
    tier: str = "working"
    embedding: np.ndarray | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    tags: list[str] = field(default_factory=list)


class MemoryEngine:
    """Three-tier memory: working (fast, small), episodic (recent sessions), semantic (learned patterns)."""

    def __init__(self):
        self.working: dict[str, MemoryEntry] = {}
        self.episodic: dict[str, MemoryEntry] = {}
        self.semantic: dict[str, MemoryEntry] = {}
        self._index: dict[str, str] = {}

    def store(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        tier: str = "working",
        tags: list[str] | None = None,
    ) -> str:
        entry = MemoryEntry(
            key=key,
            value=value,
            namespace=namespace,
            tier=tier,
            tags=tags or [],
        )
        target = self._get_tier(tier)
        target[entry.id] = entry
        self._index[f"{namespace}:{key}"] = entry.id
        logger.debug("memory_stored", tier=tier, key=key)
        return entry.id

    def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        entry_id = self._index.get(f"{namespace}:{key}")
        if not entry_id:
            return None
        for tier in [self.working, self.episodic, self.semantic]:
            if entry_id in tier:
                entry = tier[entry_id]
                entry.access_count += 1
                return entry.value
        return None

    def recall(self, tier: str = "working", limit: int = 10) -> list[MemoryEntry]:
        target = self._get_tier(tier)
        entries = sorted(
            target.values(),
            key=lambda e: (e.access_count, e.created_at),
            reverse=True,
        )
        return entries[:limit]

    def consolidate(self) -> int:
        moved = 0
        for entry_id, entry in list(self.working.items()):
            if entry.access_count >= 3 and entry.created_at < datetime.now(timezone.utc):
                self.episodic[entry_id] = entry
                del self.working[entry_id]
                entry.tier = "episodic"
                moved += 1
        for entry_id, entry in list(self.episodic.items()):
            if entry.access_count >= 10:
                self.semantic[entry_id] = entry
                del self.episodic[entry_id]
                entry.tier = "semantic"
                moved += 1
        logger.info("memory_consolidated", moved=moved)
        return moved

    def forget(self, tier: str = "working", max_age_hours: int = 24) -> int:
        target = self._get_tier(tier)
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_hours * 3600
        removed = 0
        for entry_id, entry in list(target.items()):
            if entry.created_at.timestamp() < cutoff:
                del target[entry_id]
                for k, v in list(self._index.items()):
                    if v == entry_id:
                        del self._index[k]
                removed += 1
        logger.info("memory_forgot", tier=tier, removed=removed)
        return removed

    def _get_tier(self, tier: str) -> dict[str, MemoryEntry]:
        if tier == "working":
            return self.working
        elif tier == "episodic":
            return self.episodic
        elif tier == "semantic":
            return self.semantic
        raise ValueError(f"Unknown tier: {tier}")

    def stats(self) -> dict[str, int]:
        return {
            "working": len(self.working),
            "episodic": len(self.episodic),
            "semantic": len(self.semantic),
            "total": len(self.working) + len(self.episodic) + len(self.semantic),
        }
