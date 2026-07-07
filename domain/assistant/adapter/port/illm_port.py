"""LLM 端口接口（领域层抽象，由 infrastructure 实现）。

对应 IMPL 阶段 1.1：``ILLMPort``。
domain 仅定义接口，不依赖任何具体 LLM 实现，便于替换 DeepSeek -> 其他模型。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from langchain_core.messages import BaseMessage


class ILLMPort(ABC):
    """LLM 能力端口：非流式 + 流式对话。"""

    @abstractmethod
    async def chat(self, messages: list[BaseMessage]) -> str:
        """非流式对话，返回完整回复文本。"""

    @abstractmethod
    async def chat_stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:
        """流式对话，逐 token 返回（异步生成器）。"""
