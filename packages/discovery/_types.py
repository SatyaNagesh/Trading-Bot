"""Shared discovery-layer primitives.

Small, closed vocabulary those the deeper pipelines will share. Only pydantic
models and pure helpers live here — no ingestion or analytics.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Provenance for any extracted fact. REQUIRED on every fact."""

    source: str = Field(description="named source (e.g. moneycontrol, SEBI circular, transcript)")
    url: str | None = None
    reference: str | None = Field(default=None, description="document/paragraph reference")
    retrieved_utc: datetime | None = None


class Fact(BaseModel):
    """Base for every structured fact.

    Nothing derived from LLM text may be used as a signal until a quant model
    re-validates it.
    """

    ts: datetime = Field(description="strict UTC timestamp of the information release")
    entity: str = Field(description="resolved identifier (NSE symbol or entity ticker)")
    event_type: str = Field(description="closed taxonomy key, see events.taxonomy")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source: SourceRef

    model_config = {"extra": "forbid"}
