"""Parameter perturber — small perturbations to detect fragility."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from packages.domain.models import Bar
from packages.strategies.templates import StrategyTemplate


@dataclass
class PerturbationResult:
    base_sharpe: float = 0.0
    perturbed_sharpe: float = 0.0
    sharpe_change: float = 0.0
    base_return: float = 0.0
    perturbed_return: float = 0.0
    pass_fail: str = "pass"


class ParameterPerturber:
    def __init__(self, max_sharpe_change: float = 0.5):
        self.max_sharpe_change = max_sharpe_change

    async def perturb(
        self,
        template: StrategyTemplate,
        symbol: str,
        bars: list[Bar],
        initial_capital: Decimal = Decimal("1000000"),
    ) -> list[PerturbationResult]:
        from packages.strategies.runner import run_strategy

        base = await run_strategy(template, symbol, bars, initial_capital)
        results = []

        for ind in template.indicators:
            for key, val in ind.params.items():
                if not isinstance(val, (int, float)) or val == 0:
                    continue
                for delta in [-1, 1, -2, 2]:
                    new_val = max(1, int(val + delta)) if isinstance(val, int) else val + delta
                    if new_val <= 0:
                        continue
                    perturbed = PerturbationResult(
                        base_sharpe=base.sharpe_ratio,
                    )
                    perturbed_template = _copy_and_set(template, ind.name, key, new_val)
                    perturbed_result = await run_strategy(
                        perturbed_template, symbol, bars, initial_capital
                    )
                    perturbed.perturbed_sharpe = perturbed_result.sharpe_ratio
                    perturbed.perturbed_return = perturbed_result.total_return
                    perturbed.base_return = base.total_return
                    perturbed.sharpe_change = (
                        abs(perturbed_result.sharpe_ratio - base.sharpe_ratio)
                        if base.sharpe_ratio != 0
                        else 0
                    )
                    perturbed.pass_fail = (
                        "fail" if perturbed.sharpe_change > self.max_sharpe_change else "pass"
                    )
                    results.append(perturbed)
        return results


def _copy_and_set(
    template: StrategyTemplate, ind_name: str, key: str, val: Any
) -> StrategyTemplate:
    import copy

    t = copy.deepcopy(template)
    for ind in t.indicators:
        if ind.name == ind_name:
            ind.params[key] = val
            ind.name = f"{ind.factory}_{'_'.join(str(v) for v in ind.params.values())}"
            break
    return t
