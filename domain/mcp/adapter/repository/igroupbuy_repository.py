"""拼团业务数据仓储接口（领域层抽象，对应 IMPL 3.1）。

infrastructure 实现：真实接入走 ``gateway/groupbuy_gateway`` 调 group-buy-market
（IMPL 3.2）。domain 只定义接口，便于替换数据来源。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.mcp.model.entity.groupbuy import GroupBuyProgress, TeamComplete


class IGroupBuyRepository(ABC):
    """拼团业务数据仓储。"""

    @abstractmethod
    async def get_progress(self, user_id: str, team_id: str) -> GroupBuyProgress:
        """拼团进度（T-1）。"""

    @abstractmethod
    async def get_complete_status(self, user_id: str, team_id: str) -> TeamComplete:
        """成团进度（T-2）。"""
