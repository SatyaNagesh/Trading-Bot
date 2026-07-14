"""Condition expression evaluator for strategy DSL."""

import operator
from typing import Any

import numpy as np

from packages.core.exceptions import QuantLabError
from packages.core.logging import get_logger

logger = get_logger("condition_evaluator")

_COMPARATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

_LOGICAL = {
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "not": lambda a: not a,
}


class ConditionEvaluator:
    def __init__(self, indicators: dict[str, np.ndarray], bar_index: int):
        self.indicators = indicators
        self.bar_index = bar_index

    def evaluate(self, condition: str) -> bool:
        tokens = condition.strip().split()
        if len(tokens) == 1:
            return bool(self._resolve(tokens[0]))
        elif len(tokens) == 3 and tokens[1] in _COMPARATORS:
            left = self._resolve(tokens[0])
            right = self._resolve(tokens[2])
            return bool(_COMPARATORS[tokens[1]](left, right))
        elif len(tokens) == 2 and tokens[0] == "not":
            return not self.evaluate(tokens[1])
        elif len(tokens) == 3 and tokens[1] in _LOGICAL:
            return _LOGICAL[tokens[1]](self.evaluate(tokens[0]), self.evaluate(tokens[2]))
        raise QuantLabError(f"Cannot evaluate condition: {condition}")

    def _resolve(self, token: str) -> Any:
        if token in self.indicators:
            arr = self.indicators[token]
            if self.bar_index < len(arr):
                return float(arr[self.bar_index])
            return float(arr[-1]) if len(arr) else 0.0
        try:
            return float(token)
        except ValueError:
            return token
