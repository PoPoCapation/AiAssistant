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
    """用户额度（T-3 余额）。字段对齐 ai-agent-scaffold-draw-io 的 quota 系统。"""

    user_id: str
    total_quota: int  # 总额度（MySQL user_quota.quota_count）
    used: int  # 已用额度（MySQL user_quota.used）
    remaining: int  # 剩余额度（Redis user_quota:{userId}，实时）
    recent_grants: list[str]  # 近期额度发放流水（user_quota_usage）
