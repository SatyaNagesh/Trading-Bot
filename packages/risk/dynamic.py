"""Dynamic risk adaptation — regime-aware and drawdown-based risk adjustment."""

from enum import Enum
from packages.core.logging import get_logger

logger = get_logger("dynamic_risk")


class RiskRegime(Enum):
    NORMAL = "normal"
    CAUTIOUS = "cautious"
    DEFENSIVE = "defensive"
    EMERGENCY = "emergency"


class AdaptiveRiskController:
    def __init__(self):
        self.current_drawdown: float = 0.0
        self.volatility_regime: str = "normal"
        self.regime = RiskRegime.NORMAL

    def update(self, drawdown_pct: float, volatility: float, consecutive_losses: int = 0) -> RiskRegime:
        self.current_drawdown = drawdown_pct
        if volatility > 0.03:
            self.volatility_regime = "high"
        elif volatility > 0.015:
            self.volatility_regime = "elevated"
        else:
            self.volatility_regime = "normal"
        if drawdown_pct > 0.25 or consecutive_losses >= 5:
            self.regime = RiskRegime.EMERGENCY
        elif drawdown_pct > 0.15 or consecutive_losses >= 3:
            self.regime = RiskRegime.DEFENSIVE
        elif drawdown_pct > 0.05 or self.volatility_regime == "high":
            self.regime = RiskRegime.CAUTIOUS
        else:
            self.regime = RiskRegime.NORMAL
        logger.debug("risk_regime_updated", regime=self.regime.value)
        return self.regime

    def position_size_multiplier(self) -> float:
        multipliers = {
            RiskRegime.NORMAL: 1.0,
            RiskRegime.CAUTIOUS: 0.7,
            RiskRegime.DEFENSIVE: 0.4,
            RiskRegime.EMERGENCY: 0.1,
        }
        return multipliers.get(self.regime, 1.0)

    def max_leverage(self) -> float:
        limits = {
            RiskRegime.NORMAL: 1.0,
            RiskRegime.CAUTIOUS: 0.7,
            RiskRegime.DEFENSIVE: 0.3,
            RiskRegime.EMERGENCY: 0.0,
        }
        return limits.get(self.regime, 1.0)
