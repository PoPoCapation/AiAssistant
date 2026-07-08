"""Redis 异步客户端（对应 PRD ``infrastructure/redis/redis_client.py``）。

按 **(event loop, db)** 缓存客户端：``redis.asyncio`` 连接绑定创建它的 loop，
跨 loop 复用会报错（典型：测试里多次 ``asyncio.run``）。
- 会话仓储用 ``get_redis_client()``（默认 db = settings.redis_db）；
- 额度查询用 ``get_redis_client(db=0)``（ai-agent-scaffold-draw-io 的 quota 库）。
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Tuple

import redis.asyncio as aioredis

from app.config.settings import settings

# 按 (loop id, db) 缓存客户端
_clients: Dict[Tuple[int, int], aioredis.Redis] = {}


def get_redis_client(db: Optional[int] = None) -> aioredis.Redis:
    """返回当前 event loop + 指定 db 对应的 async Redis 客户端。"""
    loop = asyncio.get_running_loop()
    if db is None:
        db = settings.redis_db
    key = (id(loop), db)
    client = _clients.get(key)
    if client is None:
        client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        _clients[key] = client
    return client
