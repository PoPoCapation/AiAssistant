"""会话仓储接口（领域层抽象，对应 IMPL 2.4）。

domain 只定义接口；infrastructure 用 Redis 实现。便于替换存储（Redis -> 其它）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage


class ISessionRepository(ABC):
    """多轮会话历史仓储。"""

    @abstractmethod
    async def load(self, session_id: str) -> list[BaseMessage]:
        """加载某会话的历史消息（不含 system prompt）。无记录返回空列表。"""

    @abstractmethod
    async def save(self, session_id: str, messages: list[BaseMessage]) -> None:
        """保存会话历史（覆盖写，内部裁剪到最近 N 轮）。"""
