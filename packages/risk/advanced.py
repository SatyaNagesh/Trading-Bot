"""Advanced Risk — real-time VaR, stress testing, margin computation."""

import numpy as np
from packages.core.logging import get_logger
from packages.domain.models import Bar

logger = get_logger("advanced_risk")


class VaREngine:
    def __init__(self, confidence: float = 0.95):
        self.confidence = confidence

    def parametric_var(self, returns: np.ndarray, horizon: int = 1) -> float:
        from scipy.stats import norm
        mu = np.mean(returns) * horizon
        sigma = np.std(returns) * np.sqrt(horizon)
        z = norm.ppf(1 - self.confidence)
        return float(-(mu + z * sigma))

    def historical_var(self, returns: np.ndarray, horizon: int = 1) -> float:
        rolled = returns[:len(returns) - horizon + 1]
        for i in range(1, horizon):
            rolled += returns[i:len(returns) - horizon + 1 + i]
        return float(-np.percentile(rolled, (1 - self.confidence) * 100))

    def monte_carlo_var(self, returns: np.ndarray, n_simulations: int = 10000, horizon: int = 1) -> float:
        mu = np.mean(returns)
        sigma = np.std(returns)
        simulated = np.random.normal(mu, sigma, (n_simulations, horizon))
        path_returns = simulated.sum(axis=1)
        return float(-np.percentile(path_returns, (1 - self.confidence) * 100))


class StressTestEngine:
    SCENARIOS = {
        "2008_financial_crisis": {"equity_drop": -0.40, "vol_spike": 3.0, "corr_spike": 0.3},
        "covid_crash_2020": {"equity_drop": -0.34, "vol_spike": 2.5, "corr_spike": 0.25},
        "rate_hike_shock": {"equity_drop": -0.15, "bond_drop": -0.08, "vol_spike": 1.5},
        "flash_crash": {"equity_drop": -0.10, "recovery_days": 1, "vol_spike": 4.0},
        "currency_crisis": {"fx_drop": -0.20, "equity_drop": -0.25, "vol_spike": 2.0},
    }

    def run_scenario(self, portfolio_value: float, scenario: str, exposures: dict[str, float]) -> dict:
        params = self.SCENARIOS.get(scenario)
        if not params:
            return {"error": f"Unknown scenario: {scenario}"}
        pnl = 0.0
        details = {}
        for asset_class, exposure in exposures.items():
            factor = params.get(f"{asset_class}_drop", params.get("equity_drop", -0.2))
            loss = exposure * factor
            details[asset_class] = {
                "exposure": exposure,
                "factor": factor,
                "loss": round(loss, 2),
            }
            pnl += loss
        return {
            "scenario": scenario,
            "portfolio_value": portfolio_value,
            "total_loss": round(pnl, 2),
            "loss_pct": round((pnl / portfolio_value) * 100, 2) if portfolio_value else 0,
            "details": details,
        }

    def run_all_scenarios(self, portfolio_value: float, exposures: dict[str, float]) -> list[dict]:
        results = []
        for scenario in self.SCENARIOS:
            result = self.run_scenario(portfolio_value, scenario, exposures)
            results.append(result)
        return results


def compute_margin(positions: list[dict], var_95: float, leverage: float = 1.0) -> dict:
    gross_exposure = sum(abs(p.get("market_value", 0)) for p in positions)
    initial_margin = gross_exposure * 0.1
    maintenance_margin = gross_exposure * 0.05
    var_margin = var_95 * leverage
    return {
        "gross_exposure": round(gross_exposure, 2),
        "initial_margin": round(initial_margin, 2),
        "maintenance_margin": round(maintenance_margin, 2),
        "var_margin": round(var_margin, 2),
        "total_margin_required": round(max(initial_margin, var_margin), 2),
    }
