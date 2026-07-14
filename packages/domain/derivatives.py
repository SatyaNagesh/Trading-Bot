"""Futures and options data models and pricing."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from packages.domain.models import Bar


class ContractType(Enum):
    FUTURES = "futures"
    CALL = "call"
    PUT = "put"


class SettlementType(Enum):
    CASH = "cash"
    PHYSICAL = "physical"


@dataclass
class FuturesContract:
    symbol: str
    underlying: str
    expiry: date
    contract_size: int = 1
    tick_size: Decimal = Decimal("0.05")
    settlement: SettlementType = SettlementType.CASH


@dataclass
class OptionsContract:
    symbol: str
    underlying: str
    expiry: date
    strike: Decimal
    contract_type: ContractType
    contract_size: int = 1
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


def black_scholes_price(
    spot: Decimal,
    strike: Decimal,
    time_to_expiry: float,
    risk_free: float = 0.05,
    iv: float = 0.20,
    option_type: ContractType = ContractType.CALL,
) -> Decimal:
    import math
    from scipy.stats import norm
    S = float(spot)
    K = float(strike)
    T = max(time_to_expiry, 1e-10)
    r = risk_free
    sigma = iv
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == ContractType.CALL:
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return Decimal(str(round(max(price, 0), 2)))
