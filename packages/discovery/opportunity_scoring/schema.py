"""RESEARCH score (not a trading score).

Components are numeric and pre-registered (weights fixed in a spec amendment
before use). The output bucket is EARLY OPPORTUNITY / RESEARCH ONLY / REJECTED.
There is NO BUY output at this layer.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OpportunityBucket(str, Enum):
    """Research-grade output bucket; there is no BUY at this layer."""
    EARLY_OPPORTUNITY = "EARLY_OPPORTUNITY"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    REJECTED = "REJECTED"


class ScoreComponents(BaseModel):
    """All components are 0..1 continuous; weights are fixed pre-registered."""

    fundamental_improvement: float = 0.0
    event_strength: float = 0.0
    industry_tailwind: float = 0.0
    macro_alignment: float = 0.0
    abnormal_market_reaction: float = 0.0
    relative_strength: float = 0.0
    valuation_context: float = 0.0
    liquidity: float = 0.0
    already_priced_in_penalty: float = Field(default=0.0, ge=0.0, description="subtract later")

    model_config = {"extra": "forbid"}


class OpportunityScore(BaseModel):
    """Scored research candidate with component breakdown and evidence refs."""
    symbol: str
    event_id: str
    components: ScoreComponents
    score: float = Field(ge=0.0, le=1.0)
    bucket: OpportunityBucket
    evidence_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


__all__ = ["OpportunityBucket", "ScoreComponents", "OpportunityScore"]
