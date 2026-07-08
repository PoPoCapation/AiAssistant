"""阶段 1 验证：单轮 DeepSeek 对话能拿到回复。

直接运行（无需 pytest）：
    .venv/Scripts/python.exe tests/test_llm.py
pytest 运行（安装 pytest 后）：
    .venv/Scripts/python.exe -m pytest tests/test_llm.py -s

需要 ``.env`` 中配置可用的 ``DEEPSEEK_API_KEY``。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 直接运行本脚本时，把项目根目录加入 sys.path（pytest 下由根 conftest.py 处理）
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api.dto.chat import ChatRequest
from app.dependency import get_assistant_service
from common.exception import AppException


def test_single_turn_chat_returns_reply() -> None:
    """发一条「你好」，应拿到非空回复。"""
    service = get_assistant_service()
    req = ChatRequest(user_id="u_test", message="你好，请用一句话介绍你自己。")
    resp = asyncio.run(service.chat(req))
    assert resp.reply and resp.reply.strip(), f"回复为空: {resp!r}"
    print("\n[DeepSeek 回复]", resp.reply)


def test_empty_message_raises() -> None:
    """空消息应抛出 AppException（ILLEGAL_PARAMETER）。"""
    service = get_assistant_service()
    req = ChatRequest(user_id="u_test", message="   ")
    raised = False
    try:
        asyncio.run(service.chat(req))
    except AppException:
        raised = True
    assert raised, "空消息应抛出 AppException"


def test_chat_stream_yields_tokens() -> None:
    """流式接口应产出非空 token 序列。"""
    service = get_assistant_service()
    req = ChatRequest(user_id="u_test", message="用一句话说『你好』。")

    async def _run() -> str:
        from domain.assistant.service.assistant_service_impl import _to_messages

        messages = _to_messages(req, system_prompt="")
        tokens: list[str] = []
        # 单轮服务当前未直接暴露流式；这里直接用底层端口验证 chat_stream
        port = get_assistant_service()._llm_port  # noqa: SLF001
        async for tok in port.chat_stream(messages):
            tokens.append(tok)
        return "".join(tokens)

    text = asyncio.run(_run())
    assert text.strip(), "流式输出为空"
    print("\n[DeepSeek 流式输出]", text)


if __name__ == "__main__":
    svc = get_assistant_service()
    request = ChatRequest(user_id="u_test", message="你好，请用一句话介绍你自己。")
    response = asyncio.run(svc.chat(request))
    print("=" * 60)
    print("user  :", request.message)
    print("reply :", response.reply)
    print("=" * 60)
    request = ChatRequest(user_id="u_test", message="你好，我加cb。")
    response = asyncio.run(svc.chat(request))
    print("=" * 60)
    print("user  :", request.message)
    print("reply :", response.reply)
    print("=" * 60)
    request = ChatRequest(user_id="u_test", message="你好，我是谁。")
    response = asyncio.run(svc.chat(request))
    print("=" * 60)
    print("user  :", request.message)
    print("reply :", response.reply)
    print("=" * 60)

    assert response.reply and response.reply.strip(), "回复为空"
    print("阶段 1 验证通过 ✓")
