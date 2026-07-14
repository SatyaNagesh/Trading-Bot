"""Contradiction detection — query-based consistency checks across knowledge entities."""

from packages.knowledge.graph import find_entities
from packages.core.logging import get_logger

logger = get_logger("contradiction")


async def detect_hypothesis_strategy_contradictions() -> list[dict]:
    hypotheses = await find_entities("Hypothesis")
    strategies = await find_entities("Strategy")
    contradictions = []
    for h in hypotheses:
        h_keywords = set(k.lower() for k in h.get("keywords", []))
        for s in strategies:
            s_tags = set(t.lower() for t in s.get("tags", []))
            if "mean-reversion" in h_keywords and "momentum" in s_tags:
                contradictions.append({
                    "type": "approach_mismatch",
                    "hypothesis": h.get("title"),
                    "strategy": s.get("name"),
                    "detail": "Mean-reversion hypothesis vs momentum strategy",
                })
    logger.info("contradiction_check", found=len(contradictions))
    return contradictions


async def validate_result_consistency(strategy_id: str, results: dict) -> dict:
    warnings = []
    sharpe = results.get("sharpe", 0)
    total_return = results.get("total_return", 0)
    max_dd = results.get("max_drawdown", 0)
    if sharpe > 3 and total_return > 50:
        warnings.append("Very high Sharpe with high returns — possible overfitting")
    if max_dd > 30 and sharpe > 2:
        warnings.append("High Sharpe despite severe drawdown — check risk metrics")
    if total_return < -20:
        warnings.append("Significant negative return — review strategy viability")
    return {"strategy_id": strategy_id, "warnings": warnings, "consistent": len(warnings) == 0}
