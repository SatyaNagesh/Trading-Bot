"""Strategy generator — enumerate thousands of candidates from a search space."""

from dataclasses import dataclass, field

from packages.strategies.templates import (
    StrategyTemplate,
    IndicatorTemplate,
    ExitTemplate,
    EntryRuleTemplate,
)


@dataclass
class SearchSpace:
    indicators: list[dict] = field(
        default_factory=lambda: [
            {"factory": "sma", "params": [{"period": p} for p in [10, 20, 30, 50, 100, 200]]},
            {"factory": "ema", "params": [{"period": p} for p in [10, 20, 30, 50, 100, 200]]},
            {"factory": "rsi", "params": [{"period": p} for p in [7, 14, 21]]},
            {
                "factory": "macd",
                "params": [
                    {"fast": f, "slow": s, "signal": 9} for f, s in [(12, 26), (8, 21), (16, 32)]
                ],
            },
            {
                "factory": "bollinger",
                "params": [{"period": p, "std_dev": s} for p in [20, 50] for s in [1.5, 2.0, 2.5]],
            },
            {"factory": "atr", "params": [{"period": p} for p in [7, 14, 21]]},
        ]
    )
    entry_rules: list[dict] = field(
        default_factory=lambda: [
            {"indicator_a": None, "operator": ">", "threshold": 0},
            {"indicator_a": None, "operator": "<", "threshold": 0},
            {"indicator_a": None, "operator": "cross_above", "threshold": 0},
            {"indicator_a": None, "operator": "cross_below", "threshold": 0},
            {"indicator_a": None, "operator": "above", "indicator_b": None},
            {"indicator_a": None, "operator": "below", "indicator_b": None},
        ]
    )
    exits: list[dict] = field(
        default_factory=lambda: [
            {"take_profit_pct": 0, "stop_loss_pct": 0, "trailing_stop_pct": 0, "max_bars_hold": 0},
            {
                "take_profit_pct": 2.0,
                "stop_loss_pct": 1.0,
                "trailing_stop_pct": 0,
                "max_bars_hold": 0,
            },
            {
                "take_profit_pct": 3.0,
                "stop_loss_pct": 1.5,
                "trailing_stop_pct": 0,
                "max_bars_hold": 0,
            },
            {
                "take_profit_pct": 5.0,
                "stop_loss_pct": 2.0,
                "trailing_stop_pct": 0,
                "max_bars_hold": 0,
            },
            {
                "take_profit_pct": 0,
                "stop_loss_pct": 0,
                "trailing_stop_pct": 2.0,
                "max_bars_hold": 0,
            },
            {
                "take_profit_pct": 3.0,
                "stop_loss_pct": 1.0,
                "trailing_stop_pct": 1.5,
                "max_bars_hold": 30,
            },
        ]
    )
    max_candidates: int = 10000


class StrategyGenerator:
    def __init__(self, search_space: SearchSpace | None = None):
        self.space = search_space or SearchSpace()

    def estimate_size(self) -> int:
        n_indicators = sum(len(g["params"]) for g in self.space.indicators)
        n_rules = len(self.space.entry_rules)
        n_exits = len(self.space.exits)
        return n_indicators * n_rules * n_exits

    def generate(
        self, prefix: str = "candidate", max_candidates: int = 0
    ) -> list[StrategyTemplate]:
        candidates: list[StrategyTemplate] = []
        limit = max_candidates or self.space.max_candidates
        counter = 0

        for ind_group in self.space.indicators:
            for ind_params in ind_group["params"]:
                ind_name = f"{ind_group['factory']}_{'_'.join(str(v) for v in ind_params.values())}"
                indicator = IndicatorTemplate(
                    name=ind_name,
                    factory=ind_group["factory"],
                    params=dict(ind_params),
                )
                for rule in self.space.entry_rules:
                    entry = EntryRuleTemplate(
                        indicator_a=ind_name,
                        operator=rule["operator"],
                        indicator_b=rule.get("indicator_b"),
                        threshold=rule.get("threshold"),
                    )
                    for exit_cfg in self.space.exits:
                        if limit > 0 and counter >= limit:
                            return candidates
                        exit_t = ExitTemplate(**exit_cfg)
                        param_desc = "x".join(str(v) for v in ind_params.values())
                        candidates.append(
                            StrategyTemplate(
                                id=f"{prefix}_{counter:06d}",
                                name=f"{ind_group['factory']}_{param_desc}_{rule['operator']}_tp{exit_t.take_profit_pct}_sl{exit_t.stop_loss_pct}",
                                indicators=[indicator],
                                entry=entry,
                                exit=exit_t,
                                description=f"{ind_group['factory']}({param_desc}) {rule['operator']} threshold",
                            )
                        )
                        counter += 1
        return candidates


def generate_candidates(
    search_space: SearchSpace | None = None, prefix: str = "candidate", max_candidates: int = 0
) -> list[StrategyTemplate]:
    gen = StrategyGenerator(search_space)
    return gen.generate(prefix=prefix, max_candidates=max_candidates)
