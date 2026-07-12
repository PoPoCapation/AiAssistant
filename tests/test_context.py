"""上下文管理验证：多档预算 + 滚动摘要 + Redis v2（PRD 第九章）。

直接运行：.venv/Scripts/python.exe tests/test_context.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from domain.assistant.adapter.port.isummarizer_port import ISummarizer
from domain.assistant.model.valobj.session_context import SessionContext
from domain.assistant.service.context_budget_service import ContextBudgetService, group_interactions
from infrastructure.adapter.port.token_counter_impl import TokenCounterImpl


class FakeSummarizer(ISummarizer):
    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, prev_summary: str, messages) -> str:
        self.calls += 1
        return f"{prev_summary}[摘要{self.calls}:{len(messages)}条]"


def test_group_interactions() -> None:
    """工具交互（Human + AI(tool_calls) + ToolMessage + AI）作为一个完整交互。"""
    msgs = [
        HumanMessage(content="q1"), AIMessage(content="a1"),
        HumanMessage(content="q2"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c1", "type": "tool_call"}]),
        ToolMessage(content="r", tool_call_id="c1"),
        AIMessage(content="a2final"),
    ]
    inter = group_interactions(msgs)
    print("\n[group] 交互数:", len(inter), "| 每组:", [len(x) for x in inter])
    assert len(inter) == 2
    assert len(inter[1]) == 4  # 工具链不拆散


def test_compact_by_hard_budget() -> None:
    """超硬预算 -> 压到 min_recent_turns，source_count 累计。"""
    fake = FakeSummarizer()
    msgs = [m for i in range(6) for m in (HumanMessage(content=f"q{i}" * 300), AIMessage(content=f"a{i}" * 300))]
    ctx = SessionContext(summary="", messages=msgs)
    budget = ContextBudgetService(fake, TokenCounterImpl(),input_token_budget=500, dynamic_reserve_tokens=0, min_recent_turns=4, max_recent_turns=6)
    new_ctx = asyncio.run(budget.compact(ctx, HumanMessage(content="now" * 300)))
    kept = group_interactions(new_ctx.messages)
    print(f"\n[hard budget] 摘要={fake.calls} 交互 6->{len(kept)} source_count={new_ctx.source_message_count}")
    assert fake.calls > 0
    assert len(kept) == 4  # 压到 min_recent_turns
    assert new_ctx.source_message_count > 0


def test_compact_by_max_turns() -> None:
    """未超预算但超最大轮数 -> 压到 max_recent_turns。"""
    fake = FakeSummarizer()
    msgs = [m for i in range(8) for m in (HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}"))]
    ctx = SessionContext(summary="", messages=msgs)
    budget = ContextBudgetService(fake, TokenCounterImpl(),input_token_budget=100000, dynamic_reserve_tokens=0, min_recent_turns=4, max_recent_turns=6)
    new_ctx = asyncio.run(budget.compact(ctx, HumanMessage(content="now")))
    kept = group_interactions(new_ctx.messages)
    print(f"\n[max turns] 摘要={fake.calls} 交互 8->{len(kept)}")
    assert fake.calls == 2  # 8 -> 6
    assert len(kept) == 6


def test_compact_noop_when_under_budget() -> None:
    fake = FakeSummarizer()
    ctx = SessionContext(summary="", messages=[HumanMessage(content="短"), AIMessage(content="答")])
    budget = ContextBudgetService(fake, TokenCounterImpl(),input_token_budget=100000, max_recent_turns=6)
    new_ctx = asyncio.run(budget.compact(ctx, HumanMessage(content="本")))
    assert fake.calls == 0
    assert len(new_ctx.messages) == 2


def test_should_compact_post() -> None:
    """持久化超 compact_trigger -> 触发异步压缩标志。"""
    budget = ContextBudgetService(FakeSummarizer(), TokenCounterImpl(),compact_trigger_tokens=100)
    big = SessionContext(summary="", messages=[HumanMessage(content="x" * 500)])
    small = SessionContext(summary="", messages=[HumanMessage(content="短")])
    assert budget.should_compact_post(big)
    assert not budget.should_compact_post(small)


def test_redis_v2_lossless_and_metadata() -> None:
    """Redis v2 同 key 无损存取（含工具链）+ 元数据（revision/updated_at/source_message_count）。"""
    from app.dependency import get_session_repository

    repo = get_session_repository()
    sid = "sess-ctx-v2-full"
    ctx = SessionContext(
        summary="摘要内容",
        messages=[
            HumanMessage(content="查拼团"),
            AIMessage(content="", tool_calls=[{"name": "group_buy_progress", "args": {"team_id": "T1"}, "id": "c1", "type": "tool_call"}]),
            ToolMessage(content="还差2人", tool_call_id="c1"),
            AIMessage(content="还差2人成团"),
        ],
        source_message_count=6,
    )

    async def _run():
        await repo.save(sid, ctx)
        return await repo.load(sid)

    loaded = asyncio.run(_run())
    print(f"\n[v2] revision={loaded.revision} updated_at={loaded.updated_at[:10]} source_count={loaded.source_message_count} | msgs={[type(m).__name__ for m in loaded.messages]}")
    assert loaded.summary == "摘要内容"
    assert loaded.revision == 1  # 保存时递增
    assert loaded.updated_at  # 有时间戳
    assert loaded.source_message_count == 6
    assert len(loaded.messages) == 4
    assert isinstance(loaded.messages[1], AIMessage) and loaded.messages[1].tool_calls  # 无损
    assert isinstance(loaded.messages[2], ToolMessage) and loaded.messages[2].tool_call_id == "c1"


def test_save_if_revision() -> None:
    """乐观锁：revision 匹配写入成功，不匹配放弃。"""
    from app.dependency import get_session_repository

    repo = get_session_repository()
    sid = "sess-if-revision-test"
    ctx = SessionContext(summary="s", messages=[HumanMessage(content="hi")])

    async def _run():
        await repo.save(sid, ctx)  # revision 0 -> 1
        loaded = await repo.load(sid)
        ok = await repo.save_if_revision(sid, loaded.revision, loaded)  # 匹配 -> 写入 -> rev 2
        stale = await repo.save_if_revision(sid, loaded.revision, loaded)  # 旧 revision -> 放弃
        return ok, stale

    ok, stale = asyncio.run(_run())
    print(f"\n[save_if_revision] ok={ok} stale={stale}")
    assert ok is True
    assert stale is False


def test_corrupt_data_degradation() -> None:
    """损坏 Redis 数据降级为空会话。"""
    from app.dependency import get_session_repository
    from infrastructure.redis.redis_client import get_redis_client

    repo = get_session_repository()
    sid = "sess-corrupt-test"

    async def _run():
        redis = get_redis_client()
        await redis.set(f"aiassistant:session:{sid}", "NOT_VALID_JSON{", ex=60)
        return await repo.load(sid)

    ctx = asyncio.run(_run())
    print(f"\n[corrupt] summary={ctx.summary!r} messages={len(ctx.messages)}")
    assert ctx.summary == ""
    assert len(ctx.messages) == 0


def test_v1_upgrade() -> None:
    """v1 列表格式自动升级为 v2 SessionContext。"""
    import json as _json

    from app.dependency import get_session_repository
    from infrastructure.redis.redis_client import get_redis_client

    repo = get_session_repository()
    sid = "sess-v1-upgrade-test"

    async def _run():
        redis = get_redis_client()
        v1 = _json.dumps([{"role": "user", "content": "旧格式问题"}, {"role": "assistant", "content": "旧格式回答"}])
        await redis.set(f"aiassistant:session:{sid}", v1, ex=60)
        return await repo.load(sid)

    ctx = asyncio.run(_run())
    print(f"\n[v1 upgrade] messages={len(ctx.messages)} summary={ctx.summary!r}")
    assert len(ctx.messages) == 2
    assert ctx.messages[0].content == "旧格式问题"
    assert ctx.summary == ""


if __name__ == "__main__":
    test_group_interactions()
    test_compact_by_hard_budget()
    test_compact_by_max_turns()
    test_compact_noop_when_under_budget()
    test_should_compact_post()
    test_redis_v2_lossless_and_metadata()
    test_save_if_revision()
    test_corrupt_data_degradation()
    test_v1_upgrade()
    print("\n上下文管理验证通过 ✓")
