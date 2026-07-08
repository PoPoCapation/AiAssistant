"""Redis 异步客户端（对应 PRD ``infrastructure/redis/redis_client.py``）。

按 **event loop** 缓存客户端：``redis.asyncio`` 的连接绑定到创建它的 event loop，
跨 loop 复用会报错（典型场景：测试里多次 ``asyncio.run`` 各开一个 loop）。
- 生产环境（uvicorn）只有一个 loop，自然单例；
- 测试环境每个 loop 各得一个独立客户端。

用 ``decode_responses=True``：读回直接是 str，省去手动 decode。
"""
from __future__ import annotations

import asyncio
from typing import Dict

import redis.asyncio as aioredis

from app.config.settings import settings

# 按 loop id 缓存客户端
_clients: Dict[int, aioredis.Redis] = {}


def get_redis_client() -> aioredis.Redis:
    """返回当前 event loop 对应的 async Redis 客户端。"""
    loop = asyncio.get_running_loop()
    lid = id(loop)
    client = _clients.get(lid)
    if client is None:
        client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        _clients[lid] = client
    return client
