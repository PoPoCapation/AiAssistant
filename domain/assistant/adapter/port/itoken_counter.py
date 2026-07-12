"""Token 计数端口（领域层抽象，对应 IMPL 5.5.4）。

可独立替换/测试的 Token 计数组件。实现：字符近似估算（含安全比例）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage


class ITokenCounter(ABC):
    """Token 计数器。"""

    @abstractmethod
    def count_messages(self, messages: list[BaseMessage]) -> int:
        """估算一组消息的 token 数（含角色/包装/tool_calls 开销 + 安全比例）。"""

    @abstractmethod
    def count_text(self, text: str) -> int:
        """估算纯文本的 token 数。"""
