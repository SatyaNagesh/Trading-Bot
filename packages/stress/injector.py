"""Stress injection — simulate real-world noise to test strategy fragility."""

import random
from dataclasses import dataclass
from decimal import Decimal
from copy import deepcopy

from packages.domain.models import Bar


@dataclass
class StressConfig:
    commission_multiplier: float = 2.0
    slippage_multiplier: float = 2.0
    execution_delay_bars: int = 2
    missing_candle_prob: float = 0.01
    data_gap_prob: float = 0.005
    volatility_shock_prob: float = 0.02
    volatility_shock_magnitude: float = 0.05


class StressInjector:
    def __init__(self, config: StressConfig | None = None):
        self.config = config or StressConfig()

    def inject(self, bars: list[Bar]) -> list[Bar]:
        result: list[Bar] = []
        for i, b in enumerate(bars):
            if random.random() < self.config.missing_candle_prob:
                continue
            if random.random() < self.config.data_gap_prob:
                continue
            bar = deepcopy(b)
            if random.random() < self.config.volatility_shock_prob:
                shock = 1 + random.uniform(
                    -self.config.volatility_shock_magnitude, self.config.volatility_shock_magnitude
                )
                bar.open = bar.open * Decimal(str(round(shock, 4)))
                bar.high = bar.high * Decimal(str(round(shock, 4)))
                bar.low = bar.low * Decimal(str(round(shock, 4)))
                bar.close = bar.close * Decimal(str(round(shock, 4)))
            result.append(bar)
        return result

    def stress_config(
        self, base_commission: Decimal, base_slippage: Decimal
    ) -> tuple[Decimal, Decimal]:
        return (
            base_commission * Decimal(str(self.config.commission_multiplier)),
            base_slippage * Decimal(str(self.config.slippage_multiplier)),
        )


def inject_stress(bars: list[Bar], config: StressConfig | None = None) -> list[Bar]:
    injector = StressInjector(config)
    return injector.inject(bars)
