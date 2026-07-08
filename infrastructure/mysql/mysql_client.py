"""MySQL 异步客户端（直查 group_buy_market 库）。

工具的真实数据来源。每次查询新建一个连接、用完即关--连接在当前（活的）
event loop 上创建和关闭，不跨 loop 复用，避免 aiomysql 连接池在多 asyncio.run
场景下「死 loop 上 GC 连接」报 ``Event loop is closed``。
工具调用频率低，免池开销可接受；后续高频场景可再引入连接池。
"""
from __future__ import annotations

from typing import Any, Optional

import aiomysql

from app.config.settings import settings


async def _connect() -> aiomysql.Connection:
    return await aiomysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_database,
        autocommit=True,
        charset="utf8mb4",
    )


class MysqlClient:
    """异步 MySQL 查询客户端（只读 fetch，每次一连接）。"""

    async def fetch_one(self, sql: str, args: Optional[tuple] = None) -> Optional[dict[str, Any]]:
        conn = await _connect()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchone()
        finally:
            conn.close()

    async def fetch_all(self, sql: str, args: Optional[tuple] = None) -> list[dict[str, Any]]:
        conn = await _connect()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchall()
        finally:
            conn.close()
