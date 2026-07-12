"""会话仓储接口（领域层抽象，对应 IMPL 2.4 / 5.5.2）。

domain 只定义接口；infrastructure 用 Redis 实现。``save_if_revision`` 用于后台异步压缩的乐观锁。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.assistant.model.valobj.session_context import SessionContext


class ISessionRepository(ABC):
    """多轮会话上下文仓储。"""

    @abstractmethod
    async def load(self, session_id: str) -> SessionContext:
        """加载会话上下文（摘要 + 完整消息）。无记录/损坏返回空 SessionContext。"""

    @abstractmethod
    async def save(self, session_id: str, ctx: SessionContext) -> None:
        """保存会话上下文（覆盖写，revision 递增）。"""

    @abstractmethod
    async def save_if_revision(self, session_id: str, expected_revision: int, ctx: SessionContext) -> bool:
        """乐观锁保存：仅当当前 revision == expected_revision 时写入并递增，返回是否成功。"""
