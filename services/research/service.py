"""Research Engine — hypothesis formulation and data exploration."""

from datetime import date

from packages.core.logging import get_logger
from packages.domain.models import Hypothesis, HypothesisStatus
from packages.knowledge.graph import create_entity, find_entities

logger = get_logger("research_service")


async def create_hypothesis(title: str, description: str, keywords: list[str] | None = None) -> dict:
    hypothesis = Hypothesis(
        title=title,
        description=description,
        keywords=keywords or [],
    )
    props = {
        "title": hypothesis.title,
        "description": hypothesis.description,
        "status": hypothesis.status.value,
        "confidence": hypothesis.confidence,
        "keywords": hypothesis.keywords,
    }
    result = await create_entity("Hypothesis", props)
    logger.info("hypothesis_created", title=title)
    return result


async def list_hypotheses(status: str | None = None) -> list[dict]:
    filters = {"status": status} if status else None
    return await find_entities("Hypothesis", filters)


async def get_available_data(symbol: str, start: date, end: date) -> dict:
    from packages.market.data_pipeline import fetch_bars
    bars = await fetch_bars(symbol, start, end)
    return {
        "symbol": symbol,
        "bar_count": len(bars),
        "start": str(start),
        "end": str(end),
        "date_range": f"{bars[0].timestamp.date() if bars else 'N/A'} — {bars[-1].timestamp.date() if bars else 'N/A'}",
    }
