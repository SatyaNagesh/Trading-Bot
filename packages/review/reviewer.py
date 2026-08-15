"""AI Strategy Review — generate explanations for surviving candidates."""

from dataclasses import dataclass

from packages.strategies.runner import CandidateResult
from packages.strategies.templates import StrategyTemplate


@dataclass
class StrategyReview:
    strategy_id: str
    strategy_name: str
    explanation: str = ""
    why_it_works: str = ""
    market_conditions: str = ""
    weaknesses: str = ""
    strengths: str = ""
    expected_regime: str = ""
    risk_profile: str = ""
    confidence_level: str = "medium"


def _describe_indicator(template: StrategyTemplate) -> str:
    parts = []
    for ind in template.indicators:
        params = ", ".join(f"{k}={v}" for k, v in ind.params.items())
        parts.append(f"{ind.factory}({params})")
    return "; ".join(parts) if parts else "price action"


def _infer_regime(template: StrategyTemplate) -> str:
    for ind in template.indicators:
        if ind.factory in ("sma", "ema") and any(
            p >= 100 for p in ind.params.values() if isinstance(p, (int, float))
        ):
            return "trending"
        if ind.factory == "rsi":
            return "mean_reverting"
        if ind.factory == "bollinger":
            return "mean_reverting"
        if ind.factory == "macd":
            return "trending"
    return "any"


def _infer_risk(template: StrategyTemplate, result: CandidateResult) -> str:
    max_dd = abs(result.max_drawdown)
    if max_dd > 15:
        return "high"
    if max_dd > 8:
        return "medium"
    return "low"


def _confidence(result: CandidateResult) -> str:
    if result.sharpe_ratio > 1.5 and result.total_trades > 50 and result.profit_factor > 1.5:
        return "high"
    if result.sharpe_ratio > 0.5 and result.total_trades > 20:
        return "medium"
    return "low"


def generate_review(template: StrategyTemplate, result: CandidateResult) -> StrategyReview:
    indicator_desc = _describe_indicator(template)
    regime = _infer_regime(template)
    risk = _infer_risk(template, result)
    conf = _confidence(result)

    entry_op = template.entry.operator if template.entry else "unknown"
    exit_desc = []
    e = template.exit
    if e.take_profit_pct:
        exit_desc.append(f"TP at {e.take_profit_pct}%")
    if e.stop_loss_pct:
        exit_desc.append(f"SL at {e.stop_loss_pct}%")
    if e.trailing_stop_pct:
        exit_desc.append(f"trailing {e.trailing_stop_pct}%")
    exit_str = ", ".join(exit_desc) if exit_desc else "none"

    strengths = []
    if result.sharpe_ratio > 1.0:
        strengths.append(f"Strong risk-adjusted returns (Sharpe {result.sharpe_ratio:.2f})")
    if result.win_rate > 50:
        strengths.append(f"High win rate ({result.win_rate:.1f}%)")
    if result.max_drawdown < 10:
        strengths.append(f"Low drawdown ({result.max_drawdown:.1f}%)")
    if result.profit_factor > 2.0:
        strengths.append(f"Excellent profit factor ({result.profit_factor:.2f})")

    weaknesses = []
    if result.sharpe_ratio < 0.5:
        weaknesses.append("Marginal risk-adjusted returns")
    if result.total_trades < 20:
        weaknesses.append("Limited trade sample size")
    if result.max_drawdown > 15:
        weaknesses.append("High drawdown exposure")
    if result.profit_factor < 1.2:
        weaknesses.append("Low profit factor")
    if result.total_return < 0:
        weaknesses.append("Negative overall return")

    explanation = (
        f"Strategy uses {indicator_desc} with {entry_op} entry and {exit_str} exits. "
        f"Performs best in {regime} markets. "
        f"Sharpe {result.sharpe_ratio:.2f}, return {result.total_return:.1f}%, "
        f"win rate {result.win_rate:.1f}%, {result.total_trades} trades."
    )

    return StrategyReview(
        strategy_id=template.id,
        strategy_name=template.name,
        explanation=explanation,
        why_it_works=f"The {indicator_desc} indicator captures {regime} behavior effectively",
        market_conditions=f"Best in {regime} markets; avoid during opposing regimes",
        weaknesses="; ".join(weaknesses) if weaknesses else "None identified",
        strengths="; ".join(strengths) if strengths else "Adequate performance",
        expected_regime=regime,
        risk_profile=risk,
        confidence_level=conf,
    )


def generate_batch_reviews(
    templates: list[StrategyTemplate],
    results: list[CandidateResult],
) -> list[StrategyReview]:
    result_map = {r.strategy_id: r for r in results}
    reviews = []
    for t in templates:
        r = result_map.get(t.id)
        if r is not None:
            reviews.append(generate_review(t, r))
    return reviews
