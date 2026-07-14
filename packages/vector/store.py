"""Qdrant vector store client for semantic search and memory."""

from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)

from packages.core.config import settings
from packages.core.logging import get_logger

logger = get_logger("vector_store")

DEFAULT_SIZE = 384


@dataclass
class VectorStore:
    client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        self.client = AsyncQdrantClient(url=settings.qdrant_url)
        logger.info("qdrant_connected", url=settings.qdrant_url)

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def ensure_collection(
        self, name: str, size: int = DEFAULT_SIZE, distance: Distance = Distance.COSINE
    ) -> None:
        if not self.client:
            await self.connect()
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=size, distance=distance),
            )
            logger.info("collection_created", name=name, size=size)

    async def upsert(self, collection: str, points: list[PointStruct]) -> int:
        if not self.client:
            await self.connect()
        result = await self.client.upsert(collection_name=collection, points=points)
        return len(points)

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        score_threshold: float | None = None,
        filter_by: dict[str, Any] | None = None,
    ) -> list[dict]:
        if not self.client:
            await self.connect()
        query_filter = None
        if filter_by:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_by.items()
            ]
            query_filter = Filter(must=conditions)

        hits = await self.client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return [
            {
                "id": h.id,
                "score": h.score,
                "payload": h.payload,
            }
            for h in hits
        ]

    async def delete_collection(self, name: str) -> None:
        if not self.client:
            await self.connect()
        await self.client.delete_collection(collection_name=name)
        logger.info("collection_deleted", name=name)
