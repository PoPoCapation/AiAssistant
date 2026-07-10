"""百炼 DashScope 嵌入服务实现。

通过 OpenAI 兼容模式调用 ``text-embedding-v4``（1024 维）。
每次请求新建 ``httpx.AsyncClient``（``trust_env=False`` 绕过本机代理），避免跨 loop 复用。
"""
from __future__ import annotations

import httpx

from common.enums import ResponseCode
from common.exception import AppException
from domain.rag.adapter.port.iembedding_port import IEmbeddingService


class DashScopeEmbeddingService(IEmbeddingService):
    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-v4") -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                resp = await client.post(
                    f"{self._base}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model, "input": texts},
                )
        except Exception as e:
            raise AppException(ResponseCode.LLM_ERROR, f"嵌入调用失败: {e}", cause=e) from e
        if resp.status_code != 200:
            raise AppException(ResponseCode.LLM_ERROR, f"嵌入 HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json().get("data", [])
        data.sort(key=lambda x: x.get("index", 0))  # 保证顺序与输入一致
        return [d["embedding"] for d in data]
