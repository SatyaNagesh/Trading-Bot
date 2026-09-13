"""Event taxonomy (CLOSED SET).

New event kinds require a spec amendment under the pre-registration
discipline — the taxonomy is deliberately small and controlled.
"""
from __future__ import annotations

from typing import Final

MACRO: Final = "macro"
POLICY_GEOPOLITICS: Final = "policy_geopolitics"
COMPANY: Final = "company"

# (category, kind, short description)
EVENT_KINDS: Final[tuple[tuple[str, str, str], ...]] = (
    # ---- macro ----
    (MACRO, "inflation_print", "CPI/WPI inflation print above/below consensus"),
    (MACRO, "rate_change", "policy rate change"),
    (MACRO, "rbi_policy", "RBI monetary policy action / commentary"),
    (MACRO, "fx_shock", "sharp FX move"),
    (MACRO, "commodity_shock", "crude or commodity price shock"),
    (MACRO, "bond_yield_move", "significant bond-yield move"),
    (MACRO, "govt_spending", "government spending announcement"),
    (MACRO, "credit_conditions", "credit conditions / liquidity shift"),
    # ---- policy / geopolitics ----
    (POLICY_GEOPOLITICS, "tariff", "tariff imposition or relief"),
    (POLICY_GEOPOLITICS, "trade_agreement", "trade agreement signed/modified"),
    (POLICY_GEOPOLITICS, "trade_restriction", "import/export restriction"),
    (POLICY_GEOPOLITICS, "incentive", "government incentive / production-linked incentive"),
    (POLICY_GEOPOLITICS, "infrastructure", "infrastructure program"),
    (POLICY_GEOPOLITICS, "sanctions", "sanctions or escalation"),
    (POLICY_GEOPOLITICS, "geopolitical", "geopolitical disruption"),
    # ---- company ----
    (COMPANY, "earnings_surprise", "earnings surprise"),
    (COMPANY, "revenue_acceleration", "revenue growth acceleration"),
    (COMPANY, "margin_expansion", "margin expansion"),
    (COMPANY, "order_win", "order win / contract"),
    (COMPANY, "capacity_expansion", "capacity expansion"),
    (COMPANY, "acquisition", "acquisition / M&A"),
    (COMPANY, "debt_reduction", "debt reduction"),
    (COMPANY, "guidance_change", "management guidance change"),
    (COMPANY, "product_launch", "major product launch"),
)

VALID_KINDS: Final[frozenset[str]] = frozenset(k for _, k, _ in EVENT_KINDS)


def is_valid(kind: str) -> bool:
    """Return whether `kind` exists in the closed event taxonomy."""
    return kind in VALID_KINDS
