"""Plugin Architecture — pluggable components with registration and discovery."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


class PluginBase(ABC):
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def version(self) -> str: ...
    def on_load(self) -> None: ...
    def on_unload(self) -> None: ...


class IndicatorPlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def compute(self, data: list[float], **params: Any) -> list[float]:
        raise NotImplementedError

    def parameters(self) -> list[dict[str, Any]]:
        return []


class StrategyPlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def generate_signals(self, data: Any, context: Any) -> list[Any]:
        raise NotImplementedError

    def entry_rules(self) -> list[dict[str, Any]]:
        return []

    def exit_rules(self) -> list[dict[str, Any]]:
        return []


class BrokerPlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def place_order(self, order: Any) -> Any:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    def get_positions(self) -> list[Any]:
        raise NotImplementedError

    def get_account(self) -> dict[str, Any]:
        raise NotImplementedError


class DataProviderPlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def fetch_bars(self, symbol: str, start: str, end: str) -> list[Any]:
        raise NotImplementedError

    def available_symbols(self) -> list[str]:
        return []


class RiskRulePlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def check(self, portfolio: Any, order: Any) -> tuple[bool, str]:
        raise NotImplementedError


@dataclass
class PluginMetadata:
    name: str
    version: str
    plugin_type: str
    instance: PluginBase
    loaded_at: str = ""
    enabled: bool = True


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, PluginMetadata] = {}
        self._hooks: dict[str, list[Callable]] = {
            "on_plugin_load": [],
            "on_plugin_unload": [],
        }
        self._categories: dict[str, list[str]] = {
            "indicator": [],
            "strategy": [],
            "broker": [],
            "data_provider": [],
            "risk_rule": [],
        }

    def register(self, plugin: PluginBase) -> str:
        ptype = self._detect_type(plugin)
        pid = f"{ptype}:{plugin.name()}"
        if pid in self._plugins:
            raise ValueError(f"Plugin already registered: {pid}")
        from datetime import datetime, timezone

        meta = PluginMetadata(
            name=plugin.name(),
            version=plugin.version(),
            plugin_type=ptype,
            instance=plugin,
            loaded_at=datetime.now(timezone.utc).isoformat(),
        )
        self._plugins[pid] = meta
        self._categories.setdefault(ptype, []).append(pid)
        try:
            plugin.on_load()
        except Exception:
            pass
        for fn in self._hooks["on_plugin_load"]:
            try:
                fn(pid, meta)
            except Exception:
                pass
        return pid

    def unregister(self, plugin_id: str) -> None:
        meta = self._plugins.pop(plugin_id, None)
        if meta is None:
            raise KeyError(f"Plugin not found: {plugin_id}")
        cat = self._categories.get(meta.plugin_type, [])
        if plugin_id in cat:
            cat.remove(plugin_id)
        try:
            meta.instance.on_unload()
        except Exception:
            pass
        for fn in self._hooks["on_plugin_unload"]:
            try:
                fn(plugin_id, meta)
            except Exception:
                pass

    def get(self, plugin_id: str) -> PluginBase | None:
        meta = self._plugins.get(plugin_id)
        return meta.instance if meta else None

    def list_by_type(self, plugin_type: str) -> list[PluginMetadata]:
        pids = self._categories.get(plugin_type, [])
        return [self._plugins[pid] for pid in pids if pid in self._plugins]

    def list_all(self) -> list[PluginMetadata]:
        return list(self._plugins.values())

    def count(self) -> dict[str, int]:
        return {cat: len(pids) for cat, pids in self._categories.items()}

    def register_hook(self, event: str, fn: Callable) -> None:
        if event in self._hooks:
            self._hooks[event].append(fn)

    def _detect_type(self, plugin: PluginBase) -> str:
        if isinstance(plugin, IndicatorPlugin):
            return "indicator"
        if isinstance(plugin, StrategyPlugin):
            return "strategy"
        if isinstance(plugin, BrokerPlugin):
            return "broker"
        if isinstance(plugin, DataProviderPlugin):
            return "data_provider"
        if isinstance(plugin, RiskRulePlugin):
            return "risk_rule"
        return "unknown"
