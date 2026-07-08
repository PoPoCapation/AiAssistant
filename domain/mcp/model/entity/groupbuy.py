"""拼团业务值对象（对应 PRD 4.2 工具输出 / IMPL 3.1）。

工具返回的业务数据结构。字段对齐 PRD 8.2 待确认的核心数据
（currentPeople/targetPeople/remainPeople/expireAt 等）。
"""
from __future__ import annotations

from pydantic import BaseModel


class GroupBuyProgress(BaseModel):
    """拼团进度（T-1）。"""

    team_id: str
    current_people: int  # 当前参团人数
    target_people: int  # 目标人数
    remain_people: int  # 剩余名额
    expire_at: str  # 截止时间（字符串，便于直接交给 LLM）


class TeamComplete(BaseModel):
    """成团进度（T-2）。"""

    team_id: str
    is_complete: bool  # 是否成团
    complete_at: str | None  # 成团时间
    members: list[str]  # 团员列表


class BalanceUsage(BaseModel):
    """余额使用（T-3）。"""

    user_id: str
    total_balance: float  # 账户余额
    available_balance: float  # 可用余额
    recent_usage: list[str]  # 近期消费明细（摘要）
    available_activities: list[str]  # 可用活动
