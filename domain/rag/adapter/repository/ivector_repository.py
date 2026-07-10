"""向量仓储接口（领域层抽象，对应 IMPL 5.1）。

实现：Qdrant。支持 upsert / search / delete。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.rag.model.entity.document import DocumentChunk


class IVectorRepository(ABC):
    """向量存储仓储。"""

    @abstractmethod
    async def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """写入/更新片段及其向量。"""

    @abstractmethod
    async def search(self, embedding: list[float], top_k: int) -> list[DocumentChunk]:
        """按向量相似度召回 top_k 个片段。"""

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """按 id 删除片段。"""
