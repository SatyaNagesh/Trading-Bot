"""Macro event marks and transmission pre-seeds.

A macro event is only useful when it can be chained (macro -> industries ->
companies) through entity_mapping, then confirmed by fundamentals.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from packages.discovery._types import SourceRef


class MacroEvent(BaseModel):
    """A macro/policy event with transmission pre-seed."""

    event_id: str
    ts: datetime = Field(description="strict UTC availability timestamp")
    kind: str = Field(description="macro or policy_geopolitics kind from the closed taxonomy")
    title: str
    magnitude: float | None = None
    direction: int | None = Field(default=None, description="+1 / -1 vs stated baseline")
    industries_affected: list[str] = Field(default_factory=list)
    transmission: str = Field(
        description="economic mechanism, e.g. cheaper inputs -> margin expansion")
    source: SourceRef

    model_config = {"extra": "forbid"}


class MacroSeries(BaseModel):
    """A numeric macro time series referenced by event marks."""

    name: str
    unit: str
    points: list[tuple[str, float]] = Field(default_factory=list)  # (yyyy-mm-dd, value)

    model_config = {"extra": "forbid"}


__all__ = ["MacroEvent", "MacroSeries"]
