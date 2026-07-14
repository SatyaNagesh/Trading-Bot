"""Plugin system — interface, sandbox, registry, and examples."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("plugin_system")


class Plugin(ABC):
    name: str = ""
    version: str = "1.0.0"
    description: str = ""

    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        ...

    async def cleanup(self) -> None:
        pass


class PluginSandbox:
    def __init__(self, allowed_modules: list[str] | None = None):
        self.allowed = allowed_modules or [
            "numpy", "pandas", "math", "json", "datetime",
            "packages.domain.models", "packages.indicators.api",
        ]

    def validate(self, plugin: Plugin) -> bool:
        if not plugin.name or not plugin.version:
            logger.warning("plugin_missing_metadata", name=plugin.name)
            return False
        return True


@dataclass
class PluginManifest:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: str = "indicator"
    enabled: bool = True


class PluginRegistry:
    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self.manifests: dict[str, PluginManifest] = {}

    def register(self, manifest: PluginManifest, plugin: Plugin) -> str:
        self.plugins[manifest.id] = plugin
        self.manifests[manifest.id] = manifest
        logger.info("plugin_registered", name=manifest.name, id=manifest.id)
        return manifest.id

    def get(self, plugin_id: str) -> Plugin | None:
        return self.plugins.get(plugin_id)

    def list_available(self) -> list[dict]:
        return [
            {"id": mid, "name": m.name, "version": m.version, "type": m.plugin_type, "enabled": m.enabled}
            for mid, m in self.manifests.items()
        ]


class CustomIndicatorPlugin(Plugin):
    def __init__(self):
        self.name = "custom_momentum"
        self.version = "1.0.0"
        self.description = "Custom momentum indicator plugin"

    async def initialize(self) -> None:
        pass

    async def execute(self, context: dict) -> dict:
        closes = context.get("closes", [])
        period = context.get("period", 14)
        if len(closes) < period:
            return {"value": 0}
        recent = closes[-period:]
        momentum = (recent[-1] - recent[0]) / recent[0]
        return {"value": momentum, "name": self.name}


class CustomBrokerPlugin(Plugin):
    def __init__(self):
        self.name = "custom_broker"
        self.version = "1.0.0"
        self.description = "Custom broker adapter plugin"

    async def initialize(self) -> None:
        pass

    async def execute(self, context: dict) -> dict:
        return {"broker": "custom", "status": "simulated"}


registry = PluginRegistry()
sandbox = PluginSandbox()

_reg_plugin = CustomIndicatorPlugin()
if sandbox.validate(_reg_plugin):
    registry.register(
        PluginManifest(name=_reg_plugin.name, version=_reg_plugin.version, description=_reg_plugin.description, plugin_type="indicator", author="system"),
        _reg_plugin,
    )
