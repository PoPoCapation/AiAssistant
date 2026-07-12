"""上下文预算服务（领域层，对应 PRD 9.3 / 9.4 / IMPL 5.5.5）。

多档预算 + 滚动摘要，以**完整交互**为最小单位压缩。Token 计数委托 ``ITokenCounter``。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from domain.assistant.adapter.port.isummarizer_port import ISummarizer
from domain.assistant.adapter.port.itoken_counter import ITokenCounter
from domain.assistant.model.valobj.session_context import SessionContext


def group_interactions(messages: list[BaseMessage]) -> list[list[BaseMessage]]:
    """按 HumanMessage 切完整交互：每条 HumanMessage 开启新交互，后续 AI/Tool 归入同一交互。"""
    interactions: list[list[BaseMessage]] = []
    cur: list[BaseMessage] = []
    for m in messages:
        if isinstance(m, HumanMessage) and cur:
            interactions.append(cur)
            cur = [m]
        else:
            cur.append(m)
    if cur:
        interactions.append(cur)
    return interactions


class ContextBudgetService:
    def __init__(
        self,
        summarizer: ISummarizer,
        token_counter: ITokenCounter,
        input_token_budget: int = 24576,
        compact_trigger_tokens: int = 16384,
        summary_max_tokens: int = 2048,
        recent_max_tokens: int = 8192,
        min_recent_turns: int = 4,
        max_recent_turns: int = 6,
        dynamic_reserve_tokens: int = 6144,
    ) -> None:
        self._summarizer = summarizer
        self._tc = token_counter
        self._input_budget = input_token_budget
        self._compact_trigger = compact_trigger_tokens
        self._summary_max = summary_max_tokens
        self._recent_max = recent_max_tokens
        self._min_recent_turns = min_recent_turns
        self._max_recent_turns = max_recent_turns
        self._dynamic_reserve = dynamic_reserve_tokens

    def _used(self, summary: str, interactions: list[list[BaseMessage]], current: BaseMessage) -> int:
        parts: list[BaseMessage] = []
        if summary:
            parts.append(SystemMessage(content=summary))
        for inter in interactions:
            parts.extend(inter)
        parts.append(current)
        return self._tc.count_messages(parts)

    def _over_hard(self, summary: str, interactions: list[list[BaseMessage]], current: BaseMessage) -> bool:
        return self._used(summary, interactions, current) > (self._input_budget - self._dynamic_reserve)

    def should_compact_post(self, ctx: SessionContext) -> bool:
        """持久化（summary + messages）是否超 compact_trigger，触发异步压缩。"""
        parts: list[BaseMessage] = []
        if ctx.summary:
            parts.append(SystemMessage(content=ctx.summary))
        parts.extend(ctx.messages)
        return self._tc.count_messages(parts) >= self._compact_trigger

    def _cap_summary(self, summary: str) -> str:
        max_chars = self._summary_max * 2
        return summary[:max_chars] + "…" if len(summary) > max_chars else summary

    async def compact(self, ctx: SessionContext, current: BaseMessage) -> SessionContext:
        """超硬预算或超最大轮数时，按完整交互滚动摘要最老轮次，保留至少 min_recent_turns 轮。"""
        summary = ctx.summary
        interactions = group_interactions(ctx.messages)
        source_count = ctx.source_message_count
        while (
            len(interactions) > self._max_recent_turns
            or self._over_hard(summary, interactions, current)
        ) and len(interactions) > self._min_recent_turns:
            dropped = interactions.pop(0)
            source_count += len(dropped)
            summary = self._cap_summary(await self._summarizer.summarize(summary, dropped))
        messages = [m for inter in interactions for m in inter]
        return SessionContext(
            summary=summary,
            messages=messages,
            source_message_count=source_count,
            revision=ctx.revision,
            updated_at=ctx.updated_at,
        )
