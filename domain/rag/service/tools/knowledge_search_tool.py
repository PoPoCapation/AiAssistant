"""知识库检索工具（RAG，对应 PRD 4.4）。

把 RAG 检索封装成一个 LangChain ``@tool``：LLM 遇到规则/说明类问题时自主调用，
检索 Qdrant + rerank 后返回相关片段，再由 response_node 综合回答。
"""
from __future__ import annotations

from langchain_core.tools import tool

from domain.rag.service.retrieval_service import IRetrievalService


def build_knowledge_search_tool(retrieval_service: IRetrievalService):
    @tool
    async def knowledge_search(query: str) -> str:
        """检索拼团产品文档 / FAQ 知识库。当用户问「拼团规则是什么」「怎么退款」「活动怎么参与」「成团条件」等规则/说明类问题时调用。
        入参：query 用户的检索问题。
        返回：相关文档片段，用于回答规则类问题。"""
        try:
            docs = await retrieval_service.retrieve(query, top_k=3)
        except Exception as e:
            return f"知识库检索失败: {e}"
        if not docs:
            return "未检索到相关文档。"
        return "\n---\n".join(f"[{i + 1}] {d.content}" for i, d in enumerate(docs))

    return knowledge_search
