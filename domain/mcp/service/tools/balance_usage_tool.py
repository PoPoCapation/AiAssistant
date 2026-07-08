"""余额使用工具（T-3，对应 IMPL 3.3）。"""
from __future__ import annotations

from langchain_core.tools import tool

from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository


def build_balance_usage_tool(repo: IGroupBuyRepository):
    @tool
    async def balance_usage(user_id: str) -> str:
        """查看账户余额使用情况。当用户问「我的余额」「余额还能用吗」「为什么余额不能用」时调用。
        入参：user_id 用户ID。
        返回：账户余额、可用余额、近期消费、可用活动。"""
        try:
            b = await repo.get_balance_usage(user_id)
        except Exception as e:
            # 余额接口暂未开放（PRD 8.2），降级提示而非报错
            return f"余额查询暂未开放：{e}。建议联系人工客服。"
        usage = "；".join(b.recent_usage) if b.recent_usage else "无"
        acts = "、".join(b.available_activities) if b.available_activities else "无"
        return (
            f"用户 {b.user_id}：账户余额 {b.total_balance}，可用 {b.available_balance}；"
            f"近期消费：{usage}；可用活动：{acts}。"
        )

    return balance_usage
