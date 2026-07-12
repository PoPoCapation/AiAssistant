"""会话仓储的 Redis 实现（Session v2，对应 PRD 9.5）。

**Key 保持不变**：``aiassistant:session:{session_id}``（与 v1 同 key）。
Value 采用版本化 JSON：
``{"schema_version": 2, "summary": "...", "messages": [message_to_dict, ...]}``

向后兼容：读到 v1（``[{role, content}, ...]`` 列表）时自动升级为 v2 结构（无损化）。
消息用 LangChain ``message_to_dict`` / ``messages_from_dict`` 无损序列化，保留 ``tool_calls`` / ``tool_call_id``。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable

import redis.asyncio as aioredis
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, message_to_dict, messages_from_dict

from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.repository.isession_repository import ISessionRepository
from domain.assistant.model.valobj.session_context import SessionContext

# v1 的 role <-> 消息类型（仅 human/assistant，v1 不存工具消息）
_V1_TYPE_FROM_ROLE = {"user": HumanMessage, "assistant": AIMessage}


def _from_v1(records: list[dict]) -> list[BaseMessage]:
    """v1 ``[{role, content}]`` -> LangChain 消息（无损升级的退化情形）。"""
    return [
        _V1_TYPE_FROM_ROLE.get(r.get("role", "user"), HumanMessage)(content=r.get("content", ""))
        for r in records
    ]


class RedisSessionRepository(ISessionRepository):
    """Redis 会话仓储（Session v2：摘要 + 完整消息，同 key 版本化）。"""

    def __init__(
        self,
        client_factory: Callable[[], aioredis.Redis],
        max_turns: int = 20,
        ttl_seconds: int = 86400,
    ) -> None:
        self._client_factory = client_factory
        self._max_turns = max_turns  # 异常保护上限（按交互数 ×4 估算消息条数）
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"aiassistant:session:{session_id}"  # 与 v1 同 key

    async def load(self, session_id: str) -> SessionContext:
        try:
            client = self._client_factory()
            raw = await client.get(self._key(session_id))
        except Exception as e:
            raise AppException(ResponseCode.SESSION_ERROR, f"读取会话失败: {e}", cause=e) from e
        if not raw:
            return SessionContext(summary="", messages=[])
        data = json.loads(raw)
        # v1：[{role, content}, ...] 列表 -> 自动升级
        if isinstance(data, list):
            return SessionContext(summary="", messages=_from_v1(data))
        # v2：{schema_version, summary, messages:[message_to_dict]}
        summary = data.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("content", "")
        messages = messages_from_dict(data.get("messages", []))
        return SessionContext(
            summary=summary,
            messages=messages,
            revision=data.get("revision", 0),
            updated_at=data.get("updated_at", ""),
            source_message_count=data.get("source_message_count", 0),
        )

    async def save(self, session_id: str, ctx: SessionContext) -> None:
        # 异常保护上限：只保留最近 max_turns 轮（按 ~4 条/交互估算）
        trimmed = ctx.messages[-self._max_turns * 4 :]
        payload = {
            "schema_version": 2,
            "revision": ctx.revision + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "summary": ctx.summary,
            "source_message_count": ctx.source_message_count,
            "messages": [message_to_dict(m) for m in trimmed],
        }
        try:
            client = self._client_factory()
            await client.set(self._key(session_id), json.dumps(payload, ensure_ascii=False), ex=self._ttl)
        except Exception as e:
            raise AppException(ResponseCode.SESSION_ERROR, f"保存会话失败: {e}", cause=e) from e
