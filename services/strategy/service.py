"""Strategy Engine — strategy definition, validation, and lifecycle."""

from datetime import datetime, timezone

from packages.core.logging import get_logger
from packages.domain.models import (
    StrategyDefinition, StrategyStatus, Signal, SignalDirection,
)
from packages.knowledge.graph import create_entity, find_entities

logger = get_logger("strategy_service")


async def create_strategy(
    name: str, dsl: str = "", author: str = "", tags: list[str] | None = None
) -> dict:
    strategy = StrategyDefinition(
        name=name, dsl=dsl, author=author, tags=tags or [],
    )
    props = {
        "name": strategy.name,
        "version": strategy.version,
        "status": strategy.status.value,
        "dsl": strategy.dsl,
        "author": strategy.author,
        "tags": strategy.tags,
    }
    result = await create_entity("Strategy", props)
    logger.info("strategy_created", name=name)
    return result


async def list_strategies(status: str | None = None) -> list[dict]:
    filters = {"status": status} if status else None
    return await find_entities("Strategy", filters)


async def evaluate_dsl(dsl_source: str) -> dict:
    import ast
    try:
        tree = ast.parse(dsl_source)
        node_count = len(list(ast.walk(tree)))
        return {"valid": True, "ast_nodes": node_count}
    except SyntaxError as e:
        return {"valid": False, "error": str(e)}
