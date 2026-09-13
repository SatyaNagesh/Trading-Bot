"""Fundamental CHANGE features (the Scout uses change, not absolute quality).

The working hypothesis is improving fundamentals + catalyst + under-reaction.
Levels (valuation etc.) only enter as context inside opportunity_scoring.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class FundamentalSnapshot(BaseModel):
    """One period's fundamentals for a symbol."""

    symbol: str
    as_of: date
    revenue: float | None = None
    ebit_margin: float | None = None
    roe: float | None = None
    roce: float | None = None
    net_debt: float | None = None
    free_cash_flow: float | None = None
    order_book: float | None = None
    capacity: float | None = None
    attributable_profit: float | None = None

    model_config = {"extra": "forbid"}


class FundamentalChange(BaseModel):
    """Change/acceleration features that feed hypothesis generation."""

    symbol: str
    period_end: date
    event_ts: str | None = None
    revenue_growth_qoq: float | None = None
    revenue_growth_yoy: float | None = None
    revenue_acceleration: float | None = Field(
        default=None, description="growth minus prior growth")
    eps_growth_yoy: float | None = None
    eps_acceleration: float | None = None
    margin_change_yoy: float | None = None
    roce_change_yoy: float | None = None
    debt_change_yoy: float | None = None
    cashflow_change_yoy: float | None = None
    order_book_growth_yoy: float | None = None
    capacity_added_yoy: float | None = None
    est_revision_up: int | None = None
    est_revision_down: int | None = None
    own_trend: float | None = Field(
        default=None, description="institutional ownership change, validated")

    model_config = {"extra": "forbid"}


__all__ = ["FundamentalSnapshot", "FundamentalChange"]
