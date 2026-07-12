"""会话仓储接口（领域层抽象，对应 IMPL 2.4 / 上下文管理 v2）。

v2：``load`` 返回 ``SessionContext``（摘要 + 最近轮次），``save`` 存 ``SessionContext``。
infrastructure 用 Redis 实现（存 ``{summary, recent}`` JSON）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.assistant.model.valobj.session_context import SessionContext


class ISessionRepository(ABC):
    """多轮会话上下文仓储（v2）。"""

    @abstractmethod
    async def load(self, session_id: str) -> SessionContext:
        """加载会话上下文（摘要 + 最近轮次）。无记录返回空 SessionContext。"""

    @abstractmethod
    async def save(self, session_id: str, ctx: SessionContext) -> None:
        """保存会话上下文（覆盖写，内部裁剪到最近 N 轮）。"""
