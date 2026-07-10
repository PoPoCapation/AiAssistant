"""阶段 5 验证：PDF OCR 提取（百炼 qwen-vl-ocr）+ PDF->RAG 全链路（按页切块）。

直接运行：.venv/Scripts/python.exe tests/test_pdf.py
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PIL import Image, ImageDraw

from app.config.settings import settings
from infrastructure.rag.embedding_service import DashScopeEmbeddingService
from infrastructure.rag.pdf_extractor import PdfOcrExtractor
from infrastructure.rag.qdrant_repository import QdrantVectorRepository
from infrastructure.rag.rerank_service import DashScopeRerankService
from infrastructure.rag.retrieval_service_impl import RetrievalServiceImpl

TEST_COLLECTION = "ai_assistant_pdf_test"


def _make_pdf(text: str) -> bytes:
    """生成一张带文字的图片型 PDF（pypdf 提不出，必须 OCR）。"""
    img = Image.new("RGB", (560, 160), "white")
    ImageDraw.Draw(img).text((10, 65), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def test_pdf_ocr_extract_pages() -> None:
    """extract_pages 返回页码 + 文本。"""
    extractor = PdfOcrExtractor(settings.dashscope_api_key)
    pages = asyncio.run(extractor.extract_pages(_make_pdf("GroupBuy rule: need 3 people to complete")))
    print("\n[PDF OCR 页]:", [(p.page_no, p.text) for p in pages])
    assert pages and pages[0].page_no == 1
    assert any("3" in p.text or "people" in p.text.lower() for p in pages)


def test_pdf_rag_pipeline() -> None:
    """PDF -> extract_pages -> ingest_pages（清洗+按页切块）-> 检索，chunk 带 page_no。"""
    emb = DashScopeEmbeddingService(
        settings.dashscope_api_key, settings.dashscope_base_url, settings.embedding_model_sync
    )
    vec = QdrantVectorRepository(settings.qdrant_url, settings.qdrant_api_key, TEST_COLLECTION, dim=1024)
    rs = RetrievalServiceImpl(emb, vec, DashScopeRerankService(settings.dashscope_api_key, settings.rerank_model))
    extractor = PdfOcrExtractor(settings.dashscope_api_key)

    async def _run():
        await vec.delete_collection()
        pages = await extractor.extract_pages(_make_pdf("GroupBuy rule: need 3 people to complete"))
        n = await rs.ingest_pages(pages, source="pdf_test")
        docs = await rs.retrieve("how many people needed to complete?", top_k=2)
        await vec.delete_collection()
        return n, docs

    n, docs = asyncio.run(_run())
    print(f"\n[PDF->RAG] 入库 {n} 切片 | 检索命中 {len(docs)}")
    for d in docs:
        print(f"  - page={d.page_no} score={d.score:.3f} | {d.content[:50]}")
    assert n > 0, "应入库切片"
    assert docs, "应检索到文档"
    assert any("3" in d.content or "people" in d.content.lower() for d in docs), "应召回含 3/people 的片段"
    assert any(d.page_no is not None for d in docs), "chunk 应带 page_no"


if __name__ == "__main__":
    test_pdf_ocr_extract_pages()
    test_pdf_rag_pipeline()
    print("\n阶段 5 PDF OCR 验证通过 ✓")
