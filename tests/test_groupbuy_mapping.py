"""阶段 3 字段映射验证（fake DB，无需 MySQL 在线）。

验证 ``GroupBuyRepositoryImpl`` 把 ``group_buy_order`` 表字段
（target_count/lock_count/complete_count/valid_end_time）正确映射成值对象，
以及团员查询、未找到团队。余额（额度）映射见 ``test_quota_mapping.py``。
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from domain.mcp.service.tools.group_complete_tool import build_group_complete_tool
from domain.mcp.service.tools.group_buy_progress_tool import build_group_buy_progress_tool
from infrastructure.adapter.repository.groupbuy_repository_impl import GroupBuyRepositoryImpl


class FakeDb:
    """模拟 MysqlClient：fetch_one / fetch_all 返回写死的行（dict）。"""

    def __init__(self, one: dict | None = None, all_rows: list[dict] | None = None) -> None:
        self._one = one
        self._all = all_rows

    async def fetch_one(self, sql: str, args: tuple | None = None) -> dict | None:
        return self._one

    async def fetch_all(self, sql: str, args: tuple | None = None) -> list[dict]:
        return self._all or []


def _team_row(target: int = 5, lock: int = 3, complete: int = 3, team_id: str = "team_001") -> dict:
    return {
        "team_id": team_id,
        "target_count": target,
        "lock_count": lock,
        "complete_count": complete,
        "valid_end_time": datetime(2026, 7, 10, 20, 0),
        "status": 0,
    }


def test_progress_mapping() -> None:
    """target_count=5, lock_count=3 -> target=5, current=3, remain=2。"""
    repo = GroupBuyRepositoryImpl(FakeDb(one=_team_row(target=5, lock=3)))
    p = asyncio.run(repo.get_progress("u_test", "team_001"))
    print("\n[progress]", p.model_dump())
    assert p.target_people == 5
    assert p.current_people == 3
    assert p.remain_people == 2


def test_progress_tool_format() -> None:
    repo = GroupBuyRepositoryImpl(FakeDb(one=_team_row(target=5, lock=3)))
    tool = build_group_buy_progress_tool(repo)
    out = asyncio.run(tool.ainvoke({"user_id": "u_test", "team_id": "team_001"}))
    print("[progress tool]", out)
    assert "3" in out and "5" in out and "2" in out, out


def test_complete_not_done() -> None:
    """lock(3) < target(5) -> 未成团；团员来自 order_list。"""
    repo = GroupBuyRepositoryImpl(
        FakeDb(one=_team_row(target=5, lock=3), all_rows=[{"user_id": "u1"}, {"user_id": "u2"}])
    )
    t = asyncio.run(repo.get_complete_status("u_test", "team_001"))
    print("[complete not-done]", t.model_dump())
    assert t.is_complete is False
    assert t.complete_at is None
    assert t.members == ["u1", "u2"]


def test_complete_done() -> None:
    """lock(5) >= target(5) -> 已成团。"""
    repo = GroupBuyRepositoryImpl(FakeDb(one=_team_row(target=5, lock=5), all_rows=[{"user_id": "u1"}]))
    t = asyncio.run(repo.get_complete_status("u_test", "team_001"))
    print("[complete done]", t.model_dump())
    assert t.is_complete is True
    assert t.complete_at is not None


def test_team_not_found() -> None:
    """team 不存在应抛 AppException。"""
    from common.exception import AppException

    repo = GroupBuyRepositoryImpl(FakeDb(one=None))
    raised = False
    try:
        asyncio.run(repo.get_progress("u_test", "team_999"))
    except AppException:
        raised = True
    assert raised, "未找到 team 应抛 AppException"


if __name__ == "__main__":
    test_progress_mapping()
    test_progress_tool_format()
    test_complete_not_done()
    test_complete_done()
    test_team_not_found()
    print("\n阶段 3 字段映射验证通过 ✓")
