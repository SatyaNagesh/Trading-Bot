"""Recovery System — crash-safe restart with automatic state recovery."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from packages.production.persistence import PersistenceStore, ProductionStore


@dataclass
class RecoveryResult:
    success: bool
    recovered_namespaces: list[str] = field(default_factory=list)
    failed_namespaces: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = ""


class RecoverySystem:
    """Crash-safe restart — re-applies stored state via registered hooks.

    Iteration is bounded: high-volume/ephemeral namespaces (e.g. alerts) and the
    self-referential checkpoints namespace are capped so a bloated store cannot
    stall recovery the way an unbounded 4.7M-row alerts table did.
    """

    _EPHEMERAL_NS = frozenset({"checkpoints", "plugins", "metrics"})
    _MAX_ENTRIES_PER_NS = 5000

    def __init__(self, store: PersistenceStore):
        self._store = store
        self._prod = ProductionStore(store)
        self._recovery_hooks: dict[str, list[Callable[[Any], None]]] = {}

    def register_recovery_hook(self, namespace: str, fn: Callable[[Any], None]) -> None:
        self._recovery_hooks.setdefault(namespace, []).append(fn)

    def save_state(self, namespace: str, key: str, state: Any) -> None:
        self._store.put(namespace, key, state)

    def load_state(self, namespace: str, key: str) -> Any | None:
        return self._store.get(namespace, key)

    def recover(self) -> RecoveryResult:
        now = datetime.now(timezone.utc).isoformat()
        result = RecoveryResult(success=True, timestamp=now)
        namespaces = self._store.list_namespaces()

        for ns in namespaces:
            if ns in self._EPHEMERAL_NS:
                continue
            try:
                entries = self._store.list_namespace(ns)[: self._MAX_ENTRIES_PER_NS]
                hooks = self._recovery_hooks.get(ns, [])
                for entry in entries:
                    for hook in hooks:
                        try:
                            hook(entry["value"])
                        except Exception as e:
                            result.errors.append(f"hook:{ns}/{entry['key']}: {e}")

                if entries:
                    result.recovered_namespaces.append(ns)
            except Exception as e:
                result.failed_namespaces.append(ns)
                result.errors.append(f"recover:{ns}: {e}")

        result.success = len(result.failed_namespaces) == 0
        return result

    def checkpoint_exists(self) -> bool:
        return self._store.count("checkpoints") > 0

    def last_checkpoint(self) -> str | None:
        keys = self._store.list_keys("checkpoints")
        if keys:
            return sorted(keys)[-1]
        return None

    def recovery_summary(self, result: RecoveryResult | None = None) -> dict[str, Any]:
        r = result or self.recover()
        return {
            "success": r.success,
            "namespaces_recovered": len(r.recovered_namespaces),
            "namespaces_failed": len(r.failed_namespaces),
            "total_errors": len(r.errors),
            "has_checkpoint": self.checkpoint_exists(),
            "last_checkpoint": self.last_checkpoint(),
            "total_entries": self._store.count(),
        }
