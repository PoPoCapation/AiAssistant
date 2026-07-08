"""用户额度仓储实现：Redis + MySQL 双读。

参考 ai-agent-scaffold-draw-io 的 ``LimitRepository``：
- 剩余额度：Redis ``user_quota:{userId}``（实时，``getRemainingQuota`` 逻辑：无键则 0）；
- 总额度 / 已用：MySQL ``{quota_db}.user_quota``（quota_count / used）；
- 近期发放流水：MySQL ``{quota_db}.user_quota_usage``（最近 5 条，含 biz_type/order_no）。

Redis 不可用时剩余降级为 0（与原实现一致）；MySQL 不可用抛 ``AppException``。
"""
from __future__ import annotations

from common.enums import ResponseCode
from common.exception import AppException
from domain.mcp.adapter.repository.iuser_quota_repository import IUserQuotaRepository
from domain.mcp.model.entity.groupbuy import BalanceUsage
from infrastructure.mysql.mysql_client import MysqlClient
from infrastructure.redis.redis_client import get_redis_client

_QUOTA_KEY = "user_quota:{user_id}"


class UserQuotaRepositoryImpl(IUserQuotaRepository):
    """用户额度仓储（Redis 热数据 + MySQL 持久化）。"""

    def __init__(self, mysql: MysqlClient, quota_db: str, quota_redis_db: int = 0) -> None:
        self._mysql = mysql
        self._quota_db = quota_db
        self._quota_redis_db = quota_redis_db

    async def get_balance_usage(self, user_id: str) -> BalanceUsage:
        # 1) Redis 剩余额度（实时账户）
        remaining = 0
        try:
            redis = get_redis_client(db=self._quota_redis_db)
            value = await redis.get(_QUOTA_KEY.format(user_id=user_id))
            if value is not None:
                remaining = int(value)
        except Exception:
            # Redis 不可用时降级为 0（与 getRemainingQuota 一致）
            remaining = 0

        # 2) MySQL 总额度 / 已用
        try:
            row = await self._mysql.fetch_one(
                f"SELECT quota_count, used FROM {self._quota_db}.user_quota WHERE user_id = %s",
                (user_id,),
            )
        except Exception as e:
            raise AppException(ResponseCode.SESSION_ERROR, f"查询额度失败: {e}", cause=e) from e
        total = int(row["quota_count"]) if row else 0
        used = int(row["used"]) if row else 0

        # 3) MySQL 近期发放流水（最近 5 条）
        rows = await self._mysql.fetch_all(
            f"SELECT order_no, quota_count, biz_type FROM {self._quota_db}.user_quota_usage "
            "WHERE user_id = %s ORDER BY id DESC LIMIT 5",
            (user_id,),
        )
        grants = [f"{r['biz_type']} +{r['quota_count']}（订单 {r['order_no']}）" for r in rows]

        return BalanceUsage(
            user_id=user_id,
            total_quota=total,
            used=used,
            remaining=remaining,
            recent_grants=grants,
        )
