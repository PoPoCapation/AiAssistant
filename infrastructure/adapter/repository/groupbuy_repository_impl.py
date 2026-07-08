"""拼团仓储实现（对应 IMPL 3.2）。

⚠️ 当前为 **STUB**：返回示例数据，用于打通工具调用链路。
真实接入需通过 ``gateway/groupbuy_gateway`` 调用 group-buy-market 的 HTTP 接口
（接口地址 / 字段 / 鉴权待 PRD 8.2 补齐后实现，替换本文件方法体即可）。
"""
from __future__ import annotations

from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository
from domain.mcp.model.entity.groupbuy import BalanceUsage, GroupBuyProgress, TeamComplete


class GroupBuyRepositoryImpl(IGroupBuyRepository):
    """Stub 实现。TODO: 替换为真实 gateway 调用。"""

    async def get_progress(self, user_id: str, team_id: str) -> GroupBuyProgress:
        return GroupBuyProgress(
            team_id=team_id,
            current_people=3,
            target_people=5,
            remain_people=2,
            expire_at="2026-07-10 20:00",
        )

    async def get_complete_status(self, user_id: str, team_id: str) -> TeamComplete:
        return TeamComplete(
            team_id=team_id,
            is_complete=False,
            complete_at=None,
            members=["u_001", "u_002", "u_003"],
        )

    async def get_balance_usage(self, user_id: str) -> BalanceUsage:
        return BalanceUsage(
            user_id=user_id,
            total_balance=100.0,
            available_balance=88.5,
            recent_usage=["2026-07-05 拼团扣款 11.5"],
            available_activities=["夏季拼团满减"],
        )
