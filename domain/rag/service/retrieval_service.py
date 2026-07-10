"""RAG 检索服务接口（领域层抽象，对应 IMPL 5.1）。

整合嵌入、向量召回、重排序，对外提供 ``retrieve``（查询）与 ``ingest`` / ``ingest_pages``（入库）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.rag.model.entity.document import DocumentChunk, PageContent


class IRetrievalService(ABC):
    """RAG 检索增强服务。"""

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 3) -> list[DocumentChunk]:
        """检索与 query 最相关的 top_k 个文档片段（向量召回 + rerank）。"""

    @abstractmethod
    async def ingest(self, text: str, source: str = "") -> int:
        """把文本切块、嵌入、写入向量库，返回切片数。"""

    @abstractmethod
    async def ingest_pages(self, pages: list[PageContent], source: str = "") -> int:
        """把 PDF 多页文本清洗、按页切块（带 page_no + 跨页标记）、嵌入、入库，返回切片数。"""
