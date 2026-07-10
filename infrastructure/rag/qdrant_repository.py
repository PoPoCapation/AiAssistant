"""Qdrant 向量仓储实现（对应 IMPL 5.1）。

用**同步** ``QdrantClient`` + ``asyncio.to_thread``，避免 async client 跨 event loop 复用问题
（同 redis.asyncio / aiomysql 的教训）。首次使用时按向量维度创建 collection（Cosine 距离）。
"""
from __future__ import annotations

import asyncio

from qdrant_client import QdrantClient, models

from domain.rag.adapter.repository.ivector_repository import IVectorRepository
from domain.rag.model.entity.document import DocumentChunk


class QdrantVectorRepository(IVectorRepository):
    def __init__(self, url: str, api_key: str, collection: str, dim: int = 1024) -> None:
        self._client = QdrantClient(url=url, api_key=api_key, timeout=30)
        self._collection = collection
        self._dim = dim
        self._ensured = False

    def _ensure_collection(self) -> None:
        if self._ensured:
            return
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=self._dim, distance=models.Distance.COSINE),
            )
        self._ensured = True

    async def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        def _do() -> None:
            self._ensure_collection()
            points = []
            for c, e in zip(chunks, embeddings):
                payload = {"content": c.content, "source": c.source}
                if c.page_no is not None:
                    payload["page_no"] = c.page_no
                points.append(models.PointStruct(id=c.id, vector=e, payload=payload))
            self._client.upsert(self._collection, points=points)

        await asyncio.to_thread(_do)

    async def search(self, embedding: list[float], top_k: int) -> list[DocumentChunk]:
        def _do() -> list[DocumentChunk]:
            self._ensure_collection()
            result = self._client.query_points(
                collection_name=self._collection, query=embedding, limit=top_k
            )
            hits = result.points
            return [
                DocumentChunk(
                    id=str(h.id),
                    content=(h.payload or {}).get("content", ""),
                    source=(h.payload or {}).get("source", ""),
                    score=h.score or 0.0,
                    page_no=(h.payload or {}).get("page_no"),
                )
                for h in hits
            ]

        return await asyncio.to_thread(_do)

    async def delete(self, ids: list[str]) -> None:
        def _do() -> None:
            self._client.delete(self._collection, points_selector=models.PointIdsList(points=ids))

        await asyncio.to_thread(_do)

    async def delete_collection(self) -> None:
        """删除整个 collection（测试清理用）。"""

        def _do() -> None:
            if self._client.collection_exists(self._collection):
                self._client.delete_collection(self._collection)
            self._ensured = False

        await asyncio.to_thread(_do)
