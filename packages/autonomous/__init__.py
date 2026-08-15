"""Gate 6B — Autonomous Research System.

Orchestrates the complete lifecycle: research → build → validate → trade → observe → learn → optimize.
"""

from packages.autonomous.experiment import ExperimentManager, ExperimentStatus, Experiment
from packages.autonomous.lifecycle import StrategyLifecycle, StrategyStage
from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
from packages.autonomous.orchestrator import AutonomousOrchestrator, CycleResult
from packages.autonomous.trading import ContinuousPaperTrader
from packages.autonomous.knowledge import KnowledgeEvolver
from packages.autonomous.improvement import SelfImprovementLoop
from packages.autonomous.health import SystemHealthMonitor
from packages.autonomous.reports import AutoReporter

__all__ = [
    "ExperimentManager",
    "ExperimentStatus",
    "Experiment",
    "StrategyLifecycle",
    "StrategyStage",
    "AutonomousScheduler",
    "ScheduleConfig",
    "AutonomousOrchestrator",
    "CycleResult",
    "ContinuousPaperTrader",
    "KnowledgeEvolver",
    "SelfImprovementLoop",
    "SystemHealthMonitor",
    "AutoReporter",
]
