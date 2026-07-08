"""拼团仓储实现：直接查 group_buy_market MySQL 库。

替换原 HTTP 网关方案（group-buy-market 服务未启动，但数据库可直连）。
- T-1 拼团进度 / T-2 成团进度：查 ``group_buy_order`` 表（团级聚合，直接有
  target_count/lock_count/complete_count/valid_end_time）。团员来自 ``group_buy_order_list``。
  字段映射：target_count->target_people、lock_count->current_people、
  remain=target-lock、lock_count>=target_count->成团。
- T-3 余额使用：库中无账户/余额表，``raise NotImplementedError``，由工具层降级提示（PRD 8.5）。

仓储依赖 ``MysqlClient``（fetch_one/fetch_all），便于测试时注入 fake。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from common.enums import ResponseCode
from common.exception import AppException
from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository
from domain.mcp.model.entity.groupbuy import GroupBuyProgress, TeamComplete
from infrastructure.mysql.mysql_client import MysqlClient


def _format_time(t: Any) -> str:
    """DB 的 DATETIME 返回 datetime 对象；时间戳/字符串也兼容。"""
    if t is None or t == "":
        return "未知"
    if isinstance(t, datetime):
        return t.strftime("%Y-%m-%d %H:%M")
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d %H:%M")
    return str(t)


class GroupBuyRepositoryImpl(IGroupBuyRepository):
    """真实拼团仓储：直查 MySQL。"""

    def __init__(self, db: MysqlClient) -> None:
        self._db = db

    async def _fetch_team(self, team_id: str) -> dict:
        row = await self._db.fetch_one(
            "SELECT team_id, target_count, lock_count, complete_count, valid_end_time, status "
            "FROM group_buy_order WHERE team_id = %s LIMIT 1",
            (team_id,),
        )
        if not row:
            raise AppException(ResponseCode.UN_ERROR, f"未找到 team_id={team_id} 的拼团")
        return row

    async def get_progress(self, user_id: str, team_id: str) -> GroupBuyProgress:
        # user_id 暂未做归属/权限校验（PRD 8.3 待补），目前按 team_id 查
        row = await self._fetch_team(team_id)
        target = int(row.get("target_count") or 0)
        lock = int(row.get("lock_count") or 0)
        return GroupBuyProgress(
            team_id=row.get("team_id") or team_id,
            current_people=lock,
            target_people=target,
            remain_people=max(target - lock, 0),
            expire_at=_format_time(row.get("valid_end_time")),
        )

    async def get_complete_status(self, user_id: str, team_id: str) -> TeamComplete:
        row = await self._fetch_team(team_id)
        target = int(row.get("target_count") or 0)
        lock = int(row.get("lock_count") or 0)
        is_complete = target > 0 and lock >= target
        # 团员 = 该 team 下未退单（status 0锁/1完成）的用户
        members_rows = await self._db.fetch_all(
            "SELECT DISTINCT user_id FROM group_buy_order_list "
            "WHERE team_id = %s AND status IN (0, 1)",
            (team_id,),
        )
        members = [r["user_id"] for r in members_rows]
        return TeamComplete(
            team_id=row.get("team_id") or team_id,
            is_complete=is_complete,
            complete_at=_format_time(row.get("valid_end_time")) if is_complete else None,
            members=members,
        )
