"""group-buy-market HTTP 网关（对应 IMPL 3.2）。

通过 httpx 调用 group-buy-market 的真实接口：
- ``/api/v1/gbm/trade/query_user_order_list``  查用户订单（用于 teamId -> goodsId）
- ``/api/v1/gbm/index/query_group_buy_market_config``  查拼团营销配置（含 Team 进度：

每次请求新建 ``httpx.AsyncClient``，避免跨 event loop 复用连接（同 redis.asyncio 的教训）。
响应统一为 ``{code, info, data}``，code != "0000" 视为业务失败。
"""
from __future__ import annotations

import httpx

from common.enums import ResponseCode
from common.exception import AppException


class GroupBuyGateway:
    """group-buy-market HTTP 网关。"""

    def __init__(self, base_url: str, source: str, channel: str, timeout: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._source = source
        self._channel = channel
        self._timeout = timeout

    async def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body)
        except Exception as e:
            raise AppException(
                ResponseCode.HTTP_EXCEPTION,
                f"group-buy-market 调用失败（{url}）: {e}",
                cause=e,
            ) from e
        if resp.status_code != 200:
            raise AppException(
                ResponseCode.HTTP_EXCEPTION,
                f"{url} HTTP {resp.status_code}: {resp.text[:200]}",
            )
        payload = resp.json()
        if payload.get("code") != ResponseCode.SUCCESS.code:
            raise AppException(
                ResponseCode.HTTP_EXCEPTION,
                f"{url} 业务失败: {payload.get('code')} {payload.get('info')}",
            )
        return payload.get("data") or {}

    async def query_user_order_list(self, user_id: str) -> list[dict]:
        """查用户拼团订单列表（含 teamId / goodsId）。"""
        data = await self._post("/api/v1/gbm/trade/query_user_order_list", {"userId": user_id})
        return data.get("orderList") or []

    async def query_group_buy_market_config(self, user_id: str, goods_id: str) -> dict:
        """查拼团营销配置，返回含 teamList（[0] 为用户置顶团）。"""
        return await self._post(
            "/api/v1/gbm/index/query_group_buy_market_config",
            {
                "userId": user_id,
                "source": self._source,
                "channel": self._channel,
                "goodsId": goods_id,
            },
        )
