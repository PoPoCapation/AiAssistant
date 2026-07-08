"""用户额度仓储接口（领域层抽象）。

用户额度（账户余额）来自 ai-agent-scaffold-draw-io 的 quota 系统
（Redis + MySQL 双写）。domain 只定义接口，infrastructure 实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.mcp.model.entity.groupbuy import BalanceUsage


class IUserQuotaRepository(ABC):
    """用户额度仓储。"""

    @abstractmethod
    async def get_balance_usage(self, user_id: str) -> BalanceUsage:
        """查用户额度：总额度、已用、剩余（Redis 实时）、近期发放流水。"""
