"""阶段 2 验证：多轮对话能记住上文（Redis 会话仓储 + LangGraph 工作流）。

直接运行：.venv/Scripts/python.exe tests/test_session.py
需要 .env 配置可用的 DEEPSEEK_API_KEY 与 Redis。
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# 直接运行时把项目根加入 sys.path（pytest 下由根 conftest.py 处理）
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api.dto.chat import ChatRequest
from app.dependency import get_assistant_service


def test_multi_turn_remembers_context() -> None:
    """同一 session_id 两轮：第一轮告知名字，第二轮应能回忆。"""
    service = get_assistant_service()
    sid = f"sess-test-{uuid.uuid4().hex[:8]}"

    async def _run():
        r1 = await service.chat(
            ChatRequest(user_id="u_test", session_id=sid, message="请记住我的名字叫cb。")
        )
        r2 = await service.chat(
            ChatRequest(user_id="u_test", session_id=sid, message="我的名字是什么？只回答名字本身。")
        )
        return r1, r2

    r1, r2 = asyncio.run(_run())
    print("\n[turn1]", r1.reply)
    print("[turn2]", r2.reply)
    assert "cb" in r2.reply.lower(), f"第二轮未记住上文: {r2.reply}"
    assert r2.session_id == sid, "应沿用同一 session_id"


def test_different_sessions_isolated() -> None:
    """不同 session_id 之间历史隔离：B 会话没被告知名字，不应答出 cb。"""
    service = get_assistant_service()
    sid_a = f"sess-iso-a-{uuid.uuid4().hex[:8]}"
    sid_b = f"sess-iso-b-{uuid.uuid4().hex[:8]}"

    async def _run():
        await service.chat(ChatRequest(user_id="u", session_id=sid_a, message="请记住我的名字叫cb。"))
        rb = await service.chat(ChatRequest(user_id="u", session_id=sid_b, message="我的名字是什么？"))
        return rb

    rb = asyncio.run(_run())
    print("\n[sessionB 未被告知名字]", rb.reply)
    assert "cb" not in rb.reply.lower(), "不同会话不应串历史"


def test_new_session_id_returned() -> None:
    """不传 session_id 时，响应应返回新建的 session_id。"""
    service = get_assistant_service()
    resp = asyncio.run(service.chat(ChatRequest(user_id="u", message="你好")))
    assert resp.session_id, "缺省应新建并返回 session_id"
    print("\n[new session_id]", resp.session_id)


if __name__ == "__main__":
    test_multi_turn_remembers_context()
    test_different_sessions_isolated()
    test_new_session_id_returned()
    print("\n阶段 2 验证通过 ✓")
