"""成团进度工具（T-2，对应 IMPL 3.3）。"""
from __future__ import annotations

from langchain_core.tools import tool

from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository


def build_group_complete_tool(repo: IGroupBuyRepository):
    @tool
    async def group_complete(user_id: str, team_id: str) -> str:
        """查看拼团是否成团。当用户问「成团了吗」「什么时候成团」「团员有哪些」时调用。
        入参：user_id 用户ID，team_id 拼团/队伍ID。
        返回：是否成团、成团时间、团员列表。"""
        t = await repo.get_complete_status(user_id, team_id)
        members = "、".join(t.members) if t.members else "（团员详情接口未开放）"
        if t.is_complete:
            return f"拼团 {t.team_id} 已成团，成团时间 {t.complete_at}，团员：{members}。"
        return f"拼团 {t.team_id} 尚未成团，当前团员：{members}。"

    return group_complete
