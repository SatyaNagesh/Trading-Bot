"""News / filings / transcripts as provenance-kept facts.

Nothing here is a sentiment score meant for a trading signal. Facts carry
source + timestamp + entity + event type + confidence + evidence, and every
fact is re-validated by quant code before anything is measured.
"""
from __future__ import annotations

from pydantic import Field

from packages.discovery._types import Fact, SourceRef


class ArticleFact(Fact):
    """A structured fact extracted from an article/report/transcript."""

    claim: str = Field(description="single discrete extractable claim")
    kind_hint: str | None = Field(default=None, description="candidate taxonomy kind (unedited)")
    evidence_excerpt: str | None = None
    keywords: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class FilingFact(Fact):
    """A structured fact from a regulatory filing (company/SEBI/government)."""

    doc_type: str = Field(description="e.g. earnings_call, annual_report, exchange_filing")
    period_ended: str | None = None
    metric: str | None = Field(default=None, description="e.g. revenue, EBIT margin, ROCE")
    value: float | None = None
    change_qoq: float | None = None
    change_yoy: float | None = None

    model_config = {"extra": "forbid"}


__all__ = ["ArticleFact", "FilingFact", "SourceRef"]
