"""上下文预算服务（领域层，对应 PRD 9.3 / 9.4）。

多档预算（对齐 PRD 9.3）：
- 硬预算 ``input_token_budget``：单次模型完整输入上限；为工具/RAG 预留 ``dynamic_reserve``；
- ``max_recent_turns``：最近最多保留的完整交互轮数（软上限）；
- ``min_recent_turns``：至少保留的完整交互轮数（硬下限）；
- ``summary_max_tokens``：摘要上限（超出截断）；
- ``safety_ratio``：token 估算安全比例（覆盖估算误差/消息包装开销）；
- ``compact_trigger_tokens``：持久化上下文超过该值时，回答完成后触发**异步**滚动压缩（为下一轮预压缩）。

压缩以**完整交互**（HumanMessage + 其后的 AI(tool_calls)/ToolMessage/AI）为最小单位，不拆散工具链。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from domain.assistant.adapter.port.isummarizer_port import ISummarizer
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
        input_token_budget: int = 24576,
        compact_trigger_tokens: int = 16384,
        summary_max_tokens: int = 2048,
        recent_max_tokens: int = 8192,
        min_recent_turns: int = 4,
        max_recent_turns: int = 6,
        dynamic_reserve_tokens: int = 6144,
        safety_ratio: float = 0.15,
    ) -> None:
        self._summarizer = summarizer
        self._input_budget = input_token_budget
        self._compact_trigger = compact_trigger_tokens
        self._summary_max = summary_max_tokens
        self._recent_max = recent_max_tokens
        self._min_recent_turns = min_recent_turns
        self._max_recent_turns = max_recent_turns
        self._dynamic_reserve = dynamic_reserve_tokens
        self._safety_ratio = safety_ratio

    @staticmethod
    def estimate_tokens(messages: list[BaseMessage]) -> int:
        total = 0
        for m in messages:
            content = m.content if isinstance(m.content, str) else str(m.content)
            total += len(content)
        return total // 2 + len(messages) * 4

    def _safe(self, tokens: int) -> int:
        """加安全比例后的 token 估算。"""
        return int(tokens * (1 + self._safety_ratio))

    def _used_safe(self, summary: str, interactions: list[list[BaseMessage]], current: BaseMessage) -> int:
        parts: list[BaseMessage] = []
        if summary:
            parts.append(SystemMessage(content=summary))
        for inter in interactions:
            parts.extend(inter)
        parts.append(current)
        return self._safe(self.estimate_tokens(parts))

    def _over_hard(self, summary: str, interactions: list[list[BaseMessage]], current: BaseMessage) -> bool:
        """硬预算：summary+recent+current 超过 input_budget - dynamic_reserve（含安全比例）。"""
        return self._used_safe(summary, interactions, current) > (self._input_budget - self._dynamic_reserve)

    def should_compact_post(self, ctx: SessionContext) -> bool:
        """回答完成后是否触发异步压缩：持久化（summary+messages）超过 compact_trigger。"""
        parts: list[BaseMessage] = []
        if ctx.summary:
            parts.append(SystemMessage(content=ctx.summary))
        parts.extend(ctx.messages)
        return self._safe(self.estimate_tokens(parts)) >= self._compact_trigger

    def _cap_summary(self, summary: str) -> str:
        max_chars = self._summary_max * 2  # ~2 字符/token
        if len(summary) > max_chars:
            return summary[:max_chars] + "…"
        return summary

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
