"""嵌入服务端口（领域层抽象，由 infrastructure 实现）。

把文本转向量。实现：百炼 DashScope（text-embedding-v4 等）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IEmbeddingService(ABC):
    """文本嵌入服务。"""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量把文本转向量，返回与 texts 等长的向量列表。"""
