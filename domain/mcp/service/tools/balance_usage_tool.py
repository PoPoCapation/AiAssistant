"""余额（用户额度）工具（T-3，对应 IMPL 3.3）。

数据来自 ai-agent-scaffold-draw-io 的 quota 系统（Redis + MySQL 双写），
通过 ``IUserQuotaRepository`` 查询。
"""
from __future__ import annotations

from langchain_core.tools import tool

from domain.mcp.adapter.repository.iuser_quota_repository import IUserQuotaRepository


def build_balance_usage_tool(repo: IUserQuotaRepository):
    @tool
    async def balance_usage(user_id: str) -> str:
        """查看账户额度使用情况。当用户问「我的余额/额度」「还能用多少」「额度剩多少」「为什么额度不能用」时调用。
        入参：user_id 用户ID。
        返回：总额度、已用、剩余额度、近期发放流水。"""
        try:
            b = await repo.get_balance_usage(user_id)
        except Exception as e:
            return f"额度查询失败：{e}。建议稍后重试或联系人工客服。"
        grants = "；".join(b.recent_grants) if b.recent_grants else "无"
        return (
            f"用户 {b.user_id}：总额度 {b.total_quota}，已用 {b.used}，剩余 {b.remaining}；"
            f"近期发放：{grants}。"
        )

    return balance_usage
