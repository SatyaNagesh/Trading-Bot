"""Hypothesis registry + multiple-testing ledger.

Every `event x exposure x horizon x metric` cell under test is registered here
up front and counts toward the discovery universe. No winner-only reporting.
FDR / permutation controls from research/ apply to the ledger.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from packages.discovery.opportunity_scoring.schema import OpportunityBucket


class Hypothesis(BaseModel):
    """A falsifiable, preregistered research hypothesis."""

    h_id: str
    created_utc: datetime
    event_kind: str
    exposure_mechanism: str
    horizon_days: list[int] = Field(description="e.g. [1,3,5,10,20]")
    metric: str = Field(description="e.g. forward_return, abnormal_return, drift")
    universe_rule: str = ""
    expected_bucket: OpportunityBucket = OpportunityBucket.RESEARCH_ONLY
    status: str = "registered"  # registered | in_test | reported
    commit_ref: str | None = Field(
        default=None, description="git commit that froze this hypothesis")

    model_config = {"extra": "forbid"}


class TestResult(BaseModel):
    """One registered cell's outcome."""

    h_id: str
    cell: str = Field(description="event x exposure x horizon x metric key")
    n_event_cells: int = Field(description="total hypothesis universe counted for FDR")
    n: int = 0
    effect: float | None = None
    effect_sem: float | None = None
    pvalue_perm: float | None = None
    qvalue_fdr: float | None = None
    reportable: bool = False

    model_config = {"extra": "forbid"}


class HypothesisDeck(BaseModel):
    """The full, counted discovery universe (multiple-testing surface)."""

    deck_id: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    results: list[TestResult] = Field(default_factory=list)

    def universe_size(self) -> int:
        """Total counted event x horizon cells (multiple-testing surface)."""
        return sum(len(h.horizon_days) for h in self.hypotheses)


__all__ = ["Hypothesis", "TestResult", "HypothesisDeck"]
