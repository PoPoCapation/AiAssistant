"""摘要器端口（领域层抽象）。

把「旧摘要 + 被淘汰的轮次」压成新摘要（滚动摘要）。实现：LLM（ILLMPort）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage


class ISummarizer(ABC):
    """对话滚动摘要器。"""

    @abstractmethod
    async def summarize(self, prev_summary: str, messages: list[BaseMessage]) -> str:
        """把 ``messages``（被淘汰的轮次）合并进 ``prev_summary``，返回新的摘要。"""
