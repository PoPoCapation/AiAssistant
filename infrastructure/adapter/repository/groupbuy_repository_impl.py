"""拼团仓储实现（对应 IMPL 3.2）：通过 ``GroupBuyGateway`` 调真实 group-buy-market。

- T-1 拼团进度 / T-2 成团进度：走 ``query_group_buy_market_config``。
  该接口按 goodsId 查，故先用 ``query_user_order_list`` 由 teamId 换出 goodsId（链式查）。
  字段映射：targetCount->target_people、lockCount->current_people、
  remain=target-lock、validEndTime->expire_at、lockCount>=targetCount->成团。
- T-3 余额使用：group-buy-market 无对应接口，``raise NotImplementedError``，
  由工具层捕获后降级提示（PRD 8.5），待接口补齐后实现（PRD 8.2）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from common.enums import ResponseCode
from common.exception import AppException
from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository
from domain.mcp.model.entity.groupbuy import BalanceUsage, GroupBuyProgress, TeamComplete
from infrastructure.gateway.groupbuy_gateway import GroupBuyGateway


def _format_time(t: Any) -> str:
    """Java Date 可能序列化为毫秒时间戳或字符串，统一成可读时间。"""
    if t is None or t == "":
        return "未知"
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    return str(t)


class GroupBuyRepositoryImpl(IGroupBuyRepository):
    """真实拼团仓储：gateway 链式查询 + 字段映射。"""

    def __init__(self, gateway: GroupBuyGateway) -> None:
        self._gw = gateway

    async def _resolve_goods_id(self, user_id: str, team_id: str) -> str:
        """由 teamId 从用户订单里换出 goodsId。"""
        orders = await self._gw.query_user_order_list(user_id)
        for o in orders:
            if o.get("teamId") == team_id:
                goods_id = o.get("goodsId")
                if goods_id:
                    return goods_id
        raise AppException(
            ResponseCode.UN_ERROR,
            f"未找到 team_id={team_id} 对应的拼团订单",
        )

    async def _get_user_team(self, user_id: str, team_id: str) -> dict:
        """取用户在该团（goodsId）的置顶 Team 字典。"""
        goods_id = await self._resolve_goods_id(user_id, team_id)
        cfg = await self._gw.query_group_buy_market_config(user_id, goods_id)
        teams = cfg.get("teamList") or []
        if not teams:
            raise AppException(ResponseCode.UN_ERROR, f"未找到 team_id={team_id} 的拼团进度")
        return teams[0]  # teamList[0] 为用户置顶团

    async def get_progress(self, user_id: str, team_id: str) -> GroupBuyProgress:
        team = await self._get_user_team(user_id, team_id)
        target = int(team.get("targetCount") or 0)
        lock = int(team.get("lockCount") or 0)
        return GroupBuyProgress(
            team_id=team.get("teamId") or team_id,
            current_people=lock,
            target_people=target,
            remain_people=max(target - lock, 0),
            expire_at=_format_time(team.get("validEndTime")),
        )

    async def get_complete_status(self, user_id: str, team_id: str) -> TeamComplete:
        team = await self._get_user_team(user_id, team_id)
        target = int(team.get("targetCount") or 0)
        lock = int(team.get("lockCount") or 0)
        is_complete = target > 0 and lock >= target
        return TeamComplete(
            team_id=team.get("teamId") or team_id,
            is_complete=is_complete,
            complete_at=_format_time(team.get("validEndTime")) if is_complete else None,
            members=[],  # 接口未暴露团员列表
        )

    async def get_balance_usage(self, user_id: str) -> BalanceUsage:
        # group-buy-market 暂无余额查询接口（PRD 8.2 待补齐）
        raise NotImplementedError("余额查询接口暂未开放，待 group-buy-market 补齐")
