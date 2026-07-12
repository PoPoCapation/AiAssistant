"""LLM 摘要器实现（用 ILLMPort 做滚动摘要）。

把「旧摘要 + 被淘汰的轮次」压成新摘要，供 ``ContextBudgetService.compact`` 使用。
摘要失败时保留旧摘要，不阻塞主对话流程。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.adapter.port.isummarizer_port import ISummarizer

_SUMMARY_PROMPT = (
    "你是对话摘要器。把「已有摘要 + 新增对话」合并成一段精简摘要，"
    "保留：用户问题、关键结论、关键数据（如拼团号 / 金额 / 时间）。不超过 200 字，只输出摘要。"
)


class LLMSummarizer(ISummarizer):
    def __init__(self, llm_port: ILLMPort) -> None:
        self._llm_port = llm_port

    async def summarize(self, prev_summary: str, messages: list[BaseMessage]) -> str:
        parts: list[str] = []
        if prev_summary:
            parts.append(f"已有摘要：{prev_summary}")
        dialog = "\n".join(
            f"{'用户' if isinstance(m, HumanMessage) else '客服'}: {m.content}"
            for m in messages
            if isinstance(m.content, str)
        )
        parts.append(f"新增对话：\n{dialog}")
        messages_in = [SystemMessage(content=_SUMMARY_PROMPT), HumanMessage(content="\n".join(parts))]
        try:
            return (await self._llm_port.chat(messages_in)).strip()
        except Exception:
            return prev_summary  # 摘要失败保留旧摘要，不影响主流程
