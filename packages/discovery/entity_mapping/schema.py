"""Entity / exposure mapping.

The critical layer: EVENT -> INDUSTRY -> ECONOMIC MECHANISM <- COMPANY EXPOSURE.

Exposure must be computed by a QUANT MODEL from financials (revenue exposure,
input-cost share, historical sensitivity). LLM/NLP never writes BUY/SELL here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Industry(BaseModel):
    """A classification bucket shared across entities and macro events."""

    industry: str
    description: str = ""


class Exposure(BaseModel):
    """Quant-computed exposure of a symbol to a mechanism direction."""

    symbol: str
    industry: str
    mechanism: str = Field(description="same wording as the event's mechanism")
    direction: int = Field(description="+1 beneficiary / -1 loser under the mechanism")
    exposure_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    revenue_exposure: float | None = Field(default=None, description="share of revenue hit")
    input_cost_share: float | None = None
    historical_sensitivity: float | None = None
    evidence: str = ""

    model_config = {"extra": "forbid"}


class ExposureMap(BaseModel):
    """Snapshot of ALL exposures for a given event/mechanism."""

    mechanism_key: str
    exposures: list[Exposure] = Field(default_factory=list)

    def symbols(self) -> list[str]:
        """Return the member symbols."""
        return [e.symbol for e in self.exposures]


__all__ = ["Industry", "Exposure", "ExposureMap"]
