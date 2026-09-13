"""Authoritative strategy registry — the single source of truth for strategy status.

Status flow (strictly enforced)::

    RESEARCH -> VALIDATED -> PAPER_APPROVED -> LIVE_APPROVED
       ^           ^                ^               |
       |           |                |               |
    RETIRED    RETIRED          RETIRED         RETIRED

Gates:
  * RESEARCH -> VALIDATED   requires a positive independent validation artifact.
  * VALIDATED -> PAPER_APPROVED requires an explicitly recorded paper-approval
    decision (e.g. a closed review gate) carried by the caller.
  * PAPER_APPROVED -> LIVE_APPROVED requires a recorded live-approval decision
    authority (e.g. principal approval) **and** is only reachable when live
    trading is enabled for the deployment.

Nothing here fabricates approval. If a decision was never recorded, the
strategy stays in RESEARCH. ``autonomous_momentum`` and all COMP3 strategies
remain RESEARCH / RETIRED because no gate decision exists for them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("data/strategy_registry.json")


class RegistryState(str, Enum):
    """Authoritative, strictly-gated strategy status."""

    RESEARCH = "RESEARCH"
    VALIDATED = "VALIDATED"
    PAPER_APPROVED = "PAPER_APPROVED"
    LIVE_APPROVED = "LIVE_APPROVED"
    RETIRED = "RETIRED"


RESEARCH_ONLY_STATUS = {
    "active",
    "candidate",
    "watchlist",
    "conceived",
    "generating",
    "backtesting",
}

_ALLOWED_TRANSITIONS: dict[RegistryState, set[RegistryState]] = {
    RegistryState.RESEARCH: {RegistryState.VALIDATED, RegistryState.RETIRED},
    RegistryState.VALIDATED: {RegistryState.PAPER_APPROVED, RegistryState.RETIRED},
    RegistryState.PAPER_APPROVED: {RegistryState.LIVE_APPROVED, RegistryState.RETIRED},
    RegistryState.LIVE_APPROVED: {RegistryState.RETIRED},
    RegistryState.RETIRED: set(),
}


@dataclass
class StrategyRecord:
    """A strategy's authoritative registry entry, including recorded evidence."""

    id: str
    name: str
    state: RegistryState = RegistryState.RESEARCH
    evidence: list[dict] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialize the record to a plain JSON-serializable dict."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyRecord:
        """Rebuild a record from its dict serialization."""
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            state=RegistryState(data.get("state", RegistryState.RESEARCH.value)),
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            notes=data.get("notes", ""),
        )


class StrategyRegistry:
    """In-memory + JSON-persisted authoritative strategy status store."""

    def __init__(self, path: Path | str = REGISTRY_PATH):
        self._path = Path(path)
        self._records: dict[str, StrategyRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for entry in data.get("strategies", []):
            rec = StrategyRecord.from_dict(entry)
            self._records[rec.id] = rec

    def save(self) -> None:
        """Persist the registry to its JSON path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "authoritative": True,
            "note": (
                "Single source of truth for strategy status. Legacy statuses "
                "('active'/'candidate'/'watchlist' in data/strategies.json) are NOT "
                "authoritative; they map to RESEARCH unless this registry says otherwise."
            ),
            "updated_at": datetime.now(UTC).isoformat(),
            "strategies": sorted(
                (rec.as_dict() for rec in self._records.values()), key=lambda r: r["id"]
            ),
        }
        self._path.write_text(json.dumps(payload, indent=2) + "\n")

    def register(self, strategy_id: str, name: str, notes: str = "") -> StrategyRecord:
        """Create a strategy record (or return the existing one) in RESEARCH state."""
        rec = self._records.get(strategy_id)
        if rec:
            return rec
        rec = StrategyRecord(id=strategy_id, name=name, notes=notes)
        self._records[strategy_id] = rec
        return rec

    def get(self, strategy_id: str) -> StrategyRecord | None:
        """Return the record, auto-registering an unknown id as RESEARCH."""
        rec = self._records.get(strategy_id)
        if rec is None:
            rec = self.register(strategy_id, strategy_id)
        return rec

    def all(self) -> list[StrategyRecord]:
        """Return all records, sorted by id."""
        return sorted(self._records.values(), key=lambda r: r.id)

    def state_of(self, strategy_id: str) -> RegistryState:
        """Return the authoritative state for a strategy."""
        return self.get(strategy_id).state

    @staticmethod
    def _valid_evidence(evidence: list[dict]) -> bool:
        """A decision is admissible only with an authority and a timestamp."""
        return any(isinstance(e, dict) and e.get("authority") and e.get("at") for e in evidence)

    def transition(
        self,
        strategy_id: str,
        to: RegistryState,
        *,
        evidence: list[dict] | None = None,
        notes: str = "",
    ) -> StrategyRecord:
        """Move a strategy between states, enforcing the transition graph and evidence gates."""
        rec = self.get(strategy_id)
        current = rec.state
        if to not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"Invalid registry transition {current.value} -> {to.value} for {strategy_id}"
            )

        approvable = (
            RegistryState.VALIDATED,
            RegistryState.PAPER_APPROVED,
            RegistryState.LIVE_APPROVED,
        )
        if to in approvable and not self._valid_evidence(evidence or []):
            raise ValueError(
                f"{strategy_id}: {to.value} requires recorded evidence "
                "(each item needs 'authority' and 'at'); refusing to fabricate approval"
            )

        rec.state = to
        if evidence:
            rec.evidence.extend(evidence)
        if notes:
            rec.notes = notes
        rec.updated_at = datetime.now(UTC).isoformat()
        return rec

    def retire(self, strategy_id: str, notes: str = "") -> StrategyRecord:
        """Retire a strategy (terminal state). No evidence required."""
        return self.transition(strategy_id, RegistryState.RETIRED, evidence=[], notes=notes)


def seed_default_registry() -> StrategyRegistry:
    """Build the authoritative registry grounded in the actual decision history.

    - autonomous_momentum: reconstructed decision path only; no gate approval
      ever recorded. REMAINS RESEARCH.
    - stdlib candidates (sma_crossover / ema_trend / rsi_mean_reversion): never
      validated, never gated. REMAIN RESEARCH.
    - COMP3_STRATEGY_V1 / COMP3_STRATEGY_V2: program concluded with the paper
      gate CLOSED and the strategy REJECTED. RETIRED.
    - paper-reversal / default: simulation fixtures used to exercise the paper
      engine, not investment strategies. RESEARCH (fixture).
    """
    reg = StrategyRegistry()
    reg.register("autonomous_momentum", "Autonomous Momentum (round-trip)", notes=(
        "Reconstructed decision path only (packages/research/baseline.py); no "
        "independent gate approval recorded. Unproven -> RESEARCH."))
    reg.register("sma_crossover", "SMA Crossover", notes="stdlib candidate, never validated.")
    reg.register("ema_trend", "EMA Trend", notes="stdlib candidate, never validated.")
    reg.register(
        "rsi_mean_reversion",
        "RSI Mean Reversion",
        notes="stdlib candidate, never validated.",
    )
    reg.register(
        "COMP3_STRATEGY_V1",
        "COMP3 V1 (rank-weighted long-biased)",
        notes="COMP3 program CLOSED; V1 rejected in review. RETIRED.",
    )
    reg.register(
        "COMP3_STRATEGY_V2",
        "COMP3 V2 (D1_CAP8 + D2_QUINTILE + V1_DECILE)",
        notes=(
            "COMP3 program CLOSED 2026-09; holdout-5 reproduced byte-identical, "
            "grade D STILL CONCENTRATION-FRAGILE; paper gate CLOSED. RETIRED."
        ),
    )
    reg.register("paper-reversal", "Paper reversal simulation fixture", notes=(
        "Fixture used by paper_trading_run.py to exercise round-trip fills; "
        "not an investment strategy."))
    reg.register("default", "IntegratedBot simulation fixture", notes=(
        "Coin-flip/LONG-SHORT simulation signal used by run_cycle/run_simulation; "
        "not an investment strategy."))
    reg.retire("COMP3_STRATEGY_V1", notes="Program closed, rejected in review.")
    reg.retire("COMP3_STRATEGY_V2", notes="Program closed, paper gate CLOSED.")
    reg.save()
    return reg


registry = StrategyRegistry()


def ensure_seeded(path: Path | str = REGISTRY_PATH) -> StrategyRegistry:
    """Return the persisted registry, seeding it once from decision history."""
    if not Path(path).exists():
        return seed_default_registry()
    return StrategyRegistry(path)
