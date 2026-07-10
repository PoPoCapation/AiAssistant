"""重排序服务端口（领域层抽象，由 infrastructure 实现）。

对召回的一批文档按与 query 的相关度重排序。实现：百炼 qwen3-vl-rerank。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple


class IRerankService(ABC):
    """文档重排序服务。"""

    @abstractmethod
    async def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        """对 documents 按 query 相关度排序，返回前 top_k 个 ``(原下标, 分数)``。"""
