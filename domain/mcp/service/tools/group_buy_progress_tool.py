"""拼团进度工具（T-1，对应 IMPL 3.3）。

LangChain ``@tool``，描述用中文写清「何时调用 / 入参 / 返回」，便于 LLM 正确选择。
通过工厂注入 ``IGroupBuyRepository``，工具内只调接口，不关心数据来源。
"""
from __future__ import annotations

from langchain_core.tools import tool

from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository


def build_group_buy_progress_tool(repo: IGroupBuyRepository):
    @tool
    async def group_buy_progress(user_id: str, team_id: str) -> str:
        """查看某个拼团的进度。当用户问「我的拼团还差几人」「拼团进度」「还差多少人成团」时调用。
        入参：user_id 用户ID，team_id 拼团/队伍ID。
        返回：当前人数、目标人数、剩余名额、截止时间。"""
        p = await repo.get_progress(user_id, team_id)
        return (
            f"拼团 {p.team_id}：当前 {p.current_people} 人，目标 {p.target_people} 人，"
            f"还差 {p.remain_people} 人成团，截止 {p.expire_at}。"
        )

    return group_buy_progress
