"""Gate 7 — Production Readiness & Persistence.

Production-hardens the entire bot: persistence, config, logging, recovery,
fault tolerance, checkpointing, observability, and plugin architecture.
"""

from packages.production.config import ProductionConfig, load_config, default_config
from packages.production.persistence import PersistenceStore, ProductionStore
from packages.production.recovery import RecoverySystem, RecoveryResult
from packages.production.fault import (
    retry,
    FallbackProvider,
    WriteQueue,
    WriteBatch,
)
from packages.production.checkpoint import Checkpointer, Checkpoint
from packages.production.observability import OperationalDashboard, MetricCollector
from packages.production.plugins import (
    PluginRegistry,
    PluginBase,
    IndicatorPlugin,
    StrategyPlugin,
    BrokerPlugin,
    DataProviderPlugin,
    RiskRulePlugin,
)

__all__ = [
    "ProductionConfig",
    "load_config",
    "default_config",
    "PersistenceStore",
    "ProductionStore",
    "RecoverySystem",
    "RecoveryResult",
    "retry",
    "FallbackProvider",
    "WriteQueue",
    "WriteBatch",
    "Checkpointer",
    "Checkpoint",
    "OperationalDashboard",
    "MetricCollector",
    "PluginRegistry",
    "PluginBase",
    "IndicatorPlugin",
    "StrategyPlugin",
    "BrokerPlugin",
    "DataProviderPlugin",
    "RiskRulePlugin",
]
