"""``ILLMPort`` 的 DeepSeek 实现（基础设施层）。

对应 IMPL 阶段 1.3 / 3.4：内部持有 ``ChatOpenAI``，
对外提供非流式 ``chat``、流式 ``chat_stream``、带工具 ``chat_with_tools``。
"""
from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.port.illm_port import ILLMPort


def _content_to_text(content) -> str:
    """``AIMessage.content`` 可能是 str 或多模态 list，统一取文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


class DeepSeekLLMAdapter(ILLMPort):
    """DeepSeek LLM 端口适配器。"""

    def __init__(self, llm: ChatOpenAI) -> None:
        self._llm = llm

    async def chat(self, messages: list[BaseMessage]) -> str:
        try:
            resp = await self._llm.ainvoke(messages)
        except Exception as e:
            raise AppException(
                ResponseCode.LLM_ERROR,
                str(e) or ResponseCode.LLM_ERROR.info,
                cause=e,
            ) from e
        return _content_to_text(resp.content)

    async def chat_with_tools(self, messages: list[BaseMessage], tools: list) -> AIMessage:
        try:
            bound = self._llm.bind_tools(tools) if tools else self._llm
            return await bound.ainvoke(messages)
        except Exception as e:
            raise AppException(
                ResponseCode.LLM_ERROR,
                str(e) or ResponseCode.LLM_ERROR.info,
                cause=e,
            ) from e

    async def chat_stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:
        try:
            async for chunk in self._llm.astream(messages):
                text = _content_to_text(chunk.content)
                if text:
                    yield text
        except Exception as e:
            raise AppException(
                ResponseCode.LLM_STREAM_ERROR,
                str(e) or ResponseCode.LLM_STREAM_ERROR.info,
                cause=e,
            ) from e
