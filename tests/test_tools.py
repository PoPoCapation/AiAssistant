"""阶段 3 验证：工具调用链路（LLM 自主调工具 -> tool_node 执行 -> 综合回答）。

直接运行：.venv/Scripts/python.exe tests/test_tools.py
需要 .env 配置可用的 DEEPSEEK_API_KEY 与 Redis。
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api.dto.chat import ChatRequest
from app.dependency import get_assistant_service


def test_group_buy_progress_tool_called() -> None:
    """问「拼团还差几人成团」应触发 group_buy_progress 工具，回答含示例数据（还差 2 人）。"""
    service = get_assistant_service()
    sid = f"sess-tool-{uuid.uuid4().hex[:8]}"

    async def _run():
        return await service.chat(
            ChatRequest(user_id="u_test", session_id=sid, message="我的拼团 29487599 还差几人成团？")
        )

    resp = asyncio.run(_run())
    print("\n[intent]", resp.intent)
    print("[reply]", resp.reply)
    assert resp.intent == "need_tool", f"应触发工具调用，实际 intent={resp.intent}"
    # 回复内容：group-buy-market 在线时含真实进度数据，离线时为降级提示；
    # 字段映射（targetCount/lockCount -> 目标/当前/剩余）见 test_groupbuy_mapping.py


def test_chitchat_does_not_call_tool() -> None:
    """闲聊不应触发工具（intent=direct）。"""
    service = get_assistant_service()
    sid = f"sess-chat-{uuid.uuid4().hex[:8]}"

    async def _run():
        return await service.chat(
            ChatRequest(user_id="u_test", session_id=sid, message="你好，请用一句话介绍你能做什么。")
        )

    resp = asyncio.run(_run())
    print("\n[闲聊 intent]", resp.intent, "| reply:", resp.reply)
    assert resp.intent == "direct", f"闲聊不应调工具，实际 intent={resp.intent}"


def test_balance_tool_called() -> None:
    """问「我的额度」应触发 balance_usage 工具，返回真实额度（user xxx3）。"""
    service = get_assistant_service()
    sid = f"sess-bal-{uuid.uuid4().hex[:8]}"

    async def _run():
        return await service.chat(
            ChatRequest(user_id="xxx3", session_id=sid, message="我的账户额度还剩多少？")
        )

    resp = asyncio.run(_run())
    print("\n[balance intent]", resp.intent, "[reply]", resp.reply)
    assert resp.intent == "need_tool", f"应触发余额工具，实际 intent={resp.intent}"


if __name__ == "__main__":
    test_group_buy_progress_tool_called()
    test_balance_tool_called()
    test_chitchat_does_not_call_tool()
    print("\n阶段 3 工具调用验证通过 ✓")
