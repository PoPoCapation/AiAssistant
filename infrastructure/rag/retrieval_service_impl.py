"""RAG 检索服务实现（对应 IMPL 5.1）。

整合 ``IEmbeddingService`` + ``IVectorRepository`` + ``IRerankService``：
- ``ingest``：纯文本 -> ``chunk_text`` 切块 -> embed -> upsert；
- ``ingest_pages``：PDF 多页 -> ``clean_pages`` 清洗 -> ``chunk_pages`` 按页切块（带 page_no + 跨页标记）-> embed -> upsert；
- ``retrieve``：query -> embed -> 向量召回（top_k*3）-> rerank 取 top_k。
"""
from __future__ import annotations

import uuid

from domain.rag.adapter.port.iembedding_port import IEmbeddingService
from domain.rag.adapter.port.irerank_port import IRerankService
from domain.rag.adapter.repository.ivector_repository import IVectorRepository
from domain.rag.model.entity.document import DocumentChunk, PageContent
from domain.rag.service.retrieval_service import IRetrievalService
from infrastructure.rag.text_chunker import chunk_pages, chunk_text, clean_pages


class RetrievalServiceImpl(IRetrievalService):
    def __init__(
        self,
        embedding: IEmbeddingService,
        vector_repo: IVectorRepository,
        rerank: IRerankService,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> None:
        self._embedding = embedding
        self._vector = vector_repo
        self._rerank = rerank
        self._chunk_size = chunk_size
        self._overlap = overlap  # 段落/句子切块不使用滑窗 overlap，保留字段兼容

    async def ingest(self, text: str, source: str = "") -> int:
        pieces = chunk_text(text, self._chunk_size, self._overlap)
        if not pieces:
            return 0
        embeddings = await self._embedding.embed(pieces)
        chunks = [
            DocumentChunk(id=str(uuid.uuid4()), content=p, source=source, page_no=None) for p in pieces
        ]
        await self._vector.upsert(chunks, embeddings)
        return len(chunks)

    async def ingest_pages(self, pages: list[PageContent], source: str = "") -> int:
        cleaned = clean_pages(pages)  # 去页码 / 页眉页脚 / 重复行
        pieces = chunk_pages(cleaned, self._chunk_size)  # [(text, page_no), ...]，跨页带 [PAGE N] 标记
        if not pieces:
            return 0
        texts = [c for c, _ in pieces]
        embeddings = await self._embedding.embed(texts)
        chunks = [
            DocumentChunk(id=str(uuid.uuid4()), content=c, source=source, page_no=pno)
            for c, pno in pieces
        ]
        await self._vector.upsert(chunks, embeddings)
        return len(chunks)

    async def retrieve(self, query: str, top_k: int = 3) -> list[DocumentChunk]:
        q_emb = (await self._embedding.embed([query]))[0]
        candidates = await self._vector.search(q_emb, top_k * 3)  # 召回多一些再精排
        if not candidates:
            return []
        docs = [c.content for c in candidates]
        ranked = await self._rerank.rerank(query, docs, top_k)
        return [candidates[idx] for idx, _ in ranked if idx < len(candidates)]
