"""阶段 5 验证：RAG 检索增强（真实 Qdrant + 百炼 embedding/rerank）。

直接运行：.venv/Scripts/python.exe tests/test_rag.py
用独立测试 collection（ai_assistant_test），结束自动清理。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.config.settings import settings
from domain.rag.service.tools.knowledge_search_tool import build_knowledge_search_tool
from infrastructure.rag.embedding_service import DashScopeEmbeddingService
from infrastructure.rag.qdrant_repository import QdrantVectorRepository
from infrastructure.rag.rerank_service import DashScopeRerankService
from infrastructure.rag.retrieval_service_impl import RetrievalServiceImpl

TEST_COLLECTION = "ai_assistant_test"
DOC = (
    "拼团规则：满 3 人即可成团，成团后 24 小时内发货。"
    "退款需在成团前申请，成团后不支持退款。"
    "拼团有效期为 24 小时，超时未成团则自动取消并全额退款。"
)


def _make_rs():
    emb = DashScopeEmbeddingService(
        settings.dashscope_api_key, settings.dashscope_base_url, settings.embedding_model_sync
    )
    vec = QdrantVectorRepository(settings.qdrant_url, settings.qdrant_api_key, TEST_COLLECTION, dim=1024)
    rerank = DashScopeRerankService(settings.dashscope_api_key, settings.rerank_model)
    return RetrievalServiceImpl(emb, vec, rerank), vec


def test_rag_ingest_and_retrieve() -> None:
    """入库一篇文档后，retrieve 应召回成团规则相关片段。"""
    rs, vec = _make_rs()

    async def _run():
        await vec.delete_collection()  # 清理旧测试数据
        n = await rs.ingest(DOC, source="test")
        docs = await rs.retrieve("拼团满几人成团？", top_k=2)
        return n, docs

    n, docs = asyncio.run(_run())
    print(f"\n[ingest] {n} 切片入库")
    print("[retrieve] 命中片段:")
    for d in docs:
        print(f"  - score={d.score:.3f} | {d.content[:40]}")
    assert n > 0, "入库切片数应 > 0"
    assert docs, "应检索到文档"
    assert any("3 人" in d.content or "成团" in d.content for d in docs), "应召回成团规则相关片段"
    asyncio.run(vec.delete_collection())


def test_knowledge_search_tool() -> None:
    """knowledge_search 工具应返回退款相关片段。"""
    rs, vec = _make_rs()
    tool = build_knowledge_search_tool(rs)

    async def _run():
        await vec.delete_collection()
        await rs.ingest(DOC, source="test")
        return await tool.ainvoke({"query": "怎么退款？"})

    out = asyncio.run(_run())
    print("\n[knowledge_search 工具输出]:", out[:120])
    assert "退款" in out, "工具应返回退款相关片段"
    asyncio.run(vec.delete_collection())


if __name__ == "__main__":
    test_rag_ingest_and_retrieve()
    test_knowledge_search_tool()
    print("\n阶段 5 RAG 验证通过 ✓")
