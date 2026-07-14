"""Memory to Knowledge Graph promotion pipeline."""

from packages.core.logging import get_logger
from packages.knowledge.graph import create_entity
from packages.memory.engine import MemoryEngine

logger = get_logger("memory_promotion")


async def promote_to_knowledge_graph(memory: MemoryEngine, min_access_count: int = 5) -> int:
    promoted = 0
    semantic_entries = memory.recall(tier="semantic", limit=50)
    for entry in semantic_entries:
        if entry.access_count < min_access_count:
            continue
        try:
            await create_entity("MemoryPromoted", {
                "key": entry.key,
                "value": str(entry.value)[:500],
                "namespace": entry.namespace,
                "access_count": entry.access_count,
                "tags": entry.tags,
            })
            promoted += 1
        except Exception as e:
            logger.error("promotion_failed", key=entry.key, error=str(e))
    logger.info("memory_promoted_to_graph", count=promoted)
    return promoted
