"""Neo4j knowledge graph driver and repository."""

from dataclasses import dataclass

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from packages.core.config import settings
from packages.core.logging import get_logger

logger = get_logger("knowledge_graph")


@dataclass
class KnowledgeGraph:
    driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await self.driver.verify_connectivity()
        logger.info("neo4j_connected", uri=settings.neo4j_uri)

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()

    async def session(self) -> AsyncSession:
        if not self.driver:
            await self.connect()
        return self.driver.session() if self.driver else None


async def create_entity(node_type: str, properties: dict) -> dict:
    kg = KnowledgeGraph()
    async with kg.session() as session:
        result = await session.run(
            f"CREATE (n:{node_type} $props) RETURN id(n) AS node_id, n",
            props=properties,
        )
        record = await result.single()
        return {"id": record["node_id"], **properties} if record else {}


async def find_entities(node_type: str, filters: dict | None = None) -> list[dict]:
    kg = KnowledgeGraph()
    async with kg.session() as session:
        query = f"MATCH (n:{node_type})"
        params = {}
        if filters:
            clauses = [f"n.{k} = ${k}" for k in filters]
            query += " WHERE " + " AND ".join(clauses)
            params = filters
        query += " RETURN id(n) AS node_id, n"
        result = await session.run(query, params)
        return [{"id": r["node_id"], **dict(r["n"])} async for r in result]


async def create_relationship(
    from_id: int, rel_type: str, to_id: int, properties: dict | None = None
) -> bool:
    kg = KnowledgeGraph()
    async with kg.session() as session:
        query = (
            f"MATCH (a) WHERE id(a) = $from_id "
            f"MATCH (b) WHERE id(b) = $to_id "
            f"CREATE (a)-[r:{rel_type} $props]->(b) "
            f"RETURN id(r) AS rel_id"
        )
        result = await session.run(query, from_id=from_id, to_id=to_id, props=properties or {})
        return await result.single() is not None


async def find_related(node_id: int, rel_type: str | None = None, depth: int = 1) -> list[dict]:
    kg = KnowledgeGraph()
    async with kg.session() as session:
        rel_filter = f":{rel_type}" if rel_type else ""
        query = (
            f"MATCH (n)-[r{rel_filter}]-(m) WHERE id(n) = $node_id "
            f"RETURN id(m) AS node_id, labels(m) AS labels, m, type(r) AS rel_type"
        )
        if depth > 1:
            query = (
                f"MATCH (n)-[r{rel_filter}*1..{depth}]-(m) WHERE id(n) = $node_id "
                f"RETURN id(m) AS node_id, labels(m) AS labels, m"
            )
        result = await session.run(query, node_id=node_id)
        return [{"id": r["node_id"], "labels": list(r["labels"]), **dict(r.get("m", {}))} async for r in result]


async def search_by_text(query_text: str, node_type: str | None = None) -> list[dict]:
    kg = KnowledgeGraph()
    async with kg.session() as session:
        label = f":{node_type}" if node_type else ""
        query = (
            f"MATCH (n{label}) WHERE ANY(k IN keys(n) WHERE n[k] CONTAINS $q) "
            f"RETURN id(n) AS node_id, labels(n) AS labels, n LIMIT 50"
        )
        result = await session.run(query, q=query_text)
        return [{"id": r["node_id"], "labels": list(r["labels"]), **dict(r["n"])} async for r in result]
