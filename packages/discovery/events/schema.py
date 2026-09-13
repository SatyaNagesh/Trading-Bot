"""Normalized, strictly-timestamped event records."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from packages.discovery._types import SourceRef
from packages.discovery.events.taxonomy import is_valid


class EventRecord(BaseModel):
    """A material-information event with a strict information-available time.

    `ts` is the release/availability time of the information, NOT the time news
    was read. Forward-return measurement may only use information up to `ts`.
    """

    event_id: str
    ts: datetime = Field(description="strict UTC information-available timestamp")
    category: str
    kind: str
    title: str
    magnitude: float | None = Field(default=None, description="scaled, comparable magnitude")
    direction: int | None = Field(default=None, description="+1 / -1 relative to a stated baseline")
    affected_entities: list[str] = Field(default_factory=list)
    affected_industries: list[str] = Field(default_factory=list)
    mechanism: str = Field(description="economic transmission mechanism, e.g. lower input cost")
    source: SourceRef
    raw_text: str | None = None

    def validate_kind(self) -> bool:
        """Confirm kind is in the closed taxonomy."""
        return is_valid(self.kind)

    model_config = {"extra": "forbid"}
