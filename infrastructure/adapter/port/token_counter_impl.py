"""Token 计数实现（对应 IMPL 5.5.4）。

字符近似估算：~2 字符/token + 每条消息 4 token 包装开销；计入 ``tool_calls`` / ``tool_call_id``；
最终乘以 ``1 + safety_ratio``。无外部 tokenizer 依赖，不可用时降级为字符估算（不中断请求）。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage

from domain.assistant.adapter.port.itoken_counter import ITokenCounter


class TokenCounterImpl(ITokenCounter):
    def __init__(self, safety_ratio: float = 0.15) -> None:
        self._safety = safety_ratio

    def count_text(self, text: str) -> int:
        return int((len(text) // 2) * (1 + self._safety))

    def count_messages(self, messages: list[BaseMessage]) -> int:
        raw = sum(self._msg_len(m) for m in messages) // 2 + len(messages) * 4
        return int(raw * (1 + self._safety))

    @staticmethod
    def _msg_len(m: BaseMessage) -> int:
        content = m.content if isinstance(m.content, str) else str(m.content)
        extra = 0
        for tc in getattr(m, "tool_calls", None) or []:
            extra += len(str(tc.get("name", ""))) + len(str(tc.get("args", {})))
        tool_call_id = getattr(m, "tool_call_id", None) or ""
        return len(content) + extra + len(str(tool_call_id))
