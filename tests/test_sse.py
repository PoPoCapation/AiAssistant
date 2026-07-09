"""阶段 4 验证：SSE 流式 /chat 接口。

直接运行：.venv/Scripts/python.exe tests/test_sse.py
用 fastapi TestClient 调 /chat，验证逐 token 事件 + [DONE] + 多轮记忆 + trace-id。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi.testclient import TestClient

from app.main import app


def _sse_events(resp) -> list[str]:
    """收集流式响应里的 data 事件 payload（去掉 ``data: `` 前缀）。"""
    events: list[str] = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(line[len("data: "):])
    return events


def _tokens_text(events: list[str]) -> str:
    """从事件里拼出 token 文本。"""
    out: list[str] = []
    for e in events:
        if e == "[DONE]":
            break
        try:
            obj = json.loads(e)
            if "token" in obj:
                out.append(obj["token"])
        except Exception:
            pass
    return "".join(out)


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json().get("status") == "ok"


def test_sse_stream_tokens() -> None:
    """流式 /chat 应返回 token 事件 + [DONE]，且响应带 trace-id 头。"""
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/v1/assistant/chat",
        json={"user_id": "u_test", "message": "你好，一句话介绍自己。"},
    ) as resp:
        assert resp.status_code == 200, resp.text
        has_trace = "trace-id" in {k.lower() for k in resp.headers.keys()}
        events = _sse_events(resp)
    print("\n事件数:", len(events), "| 前2:", events[:2], "| 末尾:", events[-2:])
    assert any('"token"' in e for e in events), f"无 token 事件: {events[:5]}"
    assert "[DONE]" in events, f"无 [DONE] 结束标记: {events[-3:]}"
    assert has_trace, "响应应带 trace-id 头"


def test_sse_multi_turn() -> None:
    """同 session_id 两轮流式对话，第二轮应记住上文。"""
    client = TestClient(app)
    sid = "sess-sse-multi"
    with client.stream(
        "POST",
        "/api/v1/assistant/chat",
        json={"user_id": "u_test", "session_id": sid, "message": "请记住我的名字叫cb。"},
    ) as r1:
        assert r1.status_code == 200
        assert "[DONE]" in _sse_events(r1)
    with client.stream(
        "POST",
        "/api/v1/assistant/chat",
        json={"user_id": "u_test", "session_id": sid, "message": "我的名字是什么？只回答名字 再给我写一首100字诗歌。"},
    ) as r2:
        assert r2.status_code == 200
        text = _tokens_text(_sse_events(r2))
    print("\n[turn2 流式回复]:", text)
    assert "cb" in text.lower(), f"第二轮未记住上文: {text}"


def test_sync_chat() -> None:
    """非流式 /chat/sync 返回统一 Response。"""
    client = TestClient(app)
    r = client.post(
        "/api/v1/assistant/chat/sync",
        json={"user_id": "u_test", "message": "你好"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("code") == "0000", body
    assert body.get("data", {}).get("reply"), body


if __name__ == "__main__":
    test_health()
    test_sse_stream_tokens()
    test_sse_multi_turn()
    test_sync_chat()
    print("\n阶段 4 SSE 验证通过 ✓")
