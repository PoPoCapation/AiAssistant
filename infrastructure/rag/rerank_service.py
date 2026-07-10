"""百炼 DashScope 重排序服务实现。

调用原生 rerank 接口 ``qwen3-vl-rerank``，按 query 对文档重排序，返回 ``(原下标, 相关度)``。
"""
from __future__ import annotations

from typing import List, Tuple

import httpx

from common.enums import ResponseCode
from common.exception import AppException
from domain.rag.adapter.port.irerank_port import IRerankService

_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"


class DashScopeRerankService(IRerankService):
    def __init__(self, api_key: str, model: str = "qwen3-vl-rerank") -> None:
        self._api_key = api_key
        self._model = model

    async def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        if not documents:
            return []
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                resp = await client.post(
                    _RERANK_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model, "input": {"query": query, "documents": documents}},
                )
        except Exception as e:
            raise AppException(ResponseCode.LLM_ERROR, f"rerank 调用失败: {e}", cause=e) from e
        if resp.status_code != 200:
            raise AppException(ResponseCode.LLM_ERROR, f"rerank HTTP {resp.status_code}: {resp.text[:200]}")
        results = resp.json().get("output", {}).get("results", [])
        results.sort(key=lambda x: -x.get("relevance_score", 0.0))
        return [(r["index"], r.get("relevance_score", 0.0)) for r in results[:top_k]]
