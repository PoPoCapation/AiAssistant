"""会话仓储的 Redis 实现（对应 IMPL 2.4）。

存最近 N 轮（N*2 条消息），序列化为 JSON ``[{"role","content"}, ...]``。
不存 system prompt（每次由 service 重新注入），避免历史里堆积系统提示。

客户端通过 ``client_factory`` 按需获取（见 ``redis_client.get_redis_client``），
保证每个 event loop 用各自的连接，避免跨 loop 复用报错。
"""
from __future__ import annotations

import json
from typing import Callable, List

import redis.asyncio as aioredis
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.repository.isession_repository import ISessionRepository

# LangChain 消息类型 <-> 角色字符串
_ROLE_FROM_TYPE = {HumanMessage: "user", AIMessage: "assistant", SystemMessage: "system"}
_TYPE_FROM_ROLE = {"user": HumanMessage, "assistant": AIMessage, "system": SystemMessage}


def _to_records(messages: List[BaseMessage]) -> list[dict]:
    records: list[dict] = []
    for m in messages:
        role = _ROLE_FROM_TYPE.get(type(m), "user")
        content = m.content if isinstance(m.content, str) else str(m.content)
        records.append({"role": role, "content": content})
    return records


def _from_records(records: list[dict]) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for r in records:
        cls = _TYPE_FROM_ROLE.get(r.get("role", "user"), HumanMessage)
        messages.append(cls(content=r.get("content", "")))
    return messages


class RedisSessionRepository(ISessionRepository):
    """Redis 会话仓储。key: ``aiassistant:session:{session_id}``。"""

    def __init__(
        self,
        client_factory: Callable[[], aioredis.Redis],
        max_turns: int = 20,
        ttl_seconds: int = 86400,
    ) -> None:
        self._client_factory = client_factory
        self._max_turns = max_turns
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"aiassistant:session:{session_id}"

    async def load(self, session_id: str) -> list[BaseMessage]:
        client = self._client_factory()
        try:
            raw = await client.get(self._key(session_id))
        except Exception as e:
            raise AppException(ResponseCode.SESSION_ERROR, f"读取会话失败: {e}", cause=e) from e
        if not raw:
            return []
        return _from_records(json.loads(raw))

    async def save(self, session_id: str, messages: List[BaseMessage]) -> None:
        # 只存最近 max_turns 轮（每轮 user + assistant 两条）
        trimmed = messages[-self._max_turns * 2 :]
        payload = json.dumps(_to_records(trimmed), ensure_ascii=False)
        client = self._client_factory()
        try:
            await client.set(self._key(session_id), payload, ex=self._ttl)
        except Exception as e:
            raise AppException(ResponseCode.SESSION_ERROR, f"保存会话失败: {e}", cause=e) from e
