"""阶段 3 字段映射验证（mock 网关，无需 group-buy-market 在线）。

直接运行：.venv/Scripts/python.exe tests/test_groupbuy_mapping.py
验证 ``GroupBuyRepositoryImpl`` 把 group-buy-market 真实字段
（targetCount/lockCount/completeCount/validEndTime）正确映射成值对象，
以及工具输出格式、teamId->goodsId 链式查、T-3 余额降级。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from domain.mcp.service.tools.balance_usage_tool import build_balance_usage_tool
from domain.mcp.service.tools.group_complete_tool import build_group_complete_tool
from domain.mcp.service.tools.group_buy_progress_tool import build_group_buy_progress_tool
from infrastructure.adapter.repository.groupbuy_repository_impl import GroupBuyRepositoryImpl


class FakeGateway:
    """模拟 group-buy-market 网关返回（实现 query_user_order_list / query_group_buy_market_config）。"""

    def __init__(self, orders: list[dict], team: dict) -> None:
        self._orders = orders
        self._team = team

    async def query_user_order_list(self, user_id: str) -> list[dict]:
        return self._orders

    async def query_group_buy_market_config(self, user_id: str, goods_id: str) -> dict:
        return {"teamList": [self._team]}


def _make_repo(team: dict, team_id: str = "team_001") -> GroupBuyRepositoryImpl:
    team = dict(team)
    team.setdefault("teamId", team_id)
    gw = FakeGateway(
        orders=[{"teamId": team_id, "goodsId": "9890001", "status": "PROGRESS"}],
        team=team,
    )
    return GroupBuyRepositoryImpl(gw)


def test_progress_mapping() -> None:
    """targetCount=5, lockCount=3 -> target=5, current=3, remain=2。"""
    repo = _make_repo({"targetCount": 5, "lockCount": 3, "completeCount": 3, "validEndTime": "2026-07-10T20:00:00"})
    p = asyncio.run(repo.get_progress("u_test", "team_001"))
    print("\n[progress]", p.model_dump())
    assert p.target_people == 5
    assert p.current_people == 3
    assert p.remain_people == 2
    assert p.team_id == "team_001"


def test_progress_tool_format() -> None:
    repo = _make_repo({"targetCount": 5, "lockCount": 3, "completeCount": 3, "validEndTime": "2026-07-10T20:00:00"})
    tool = build_group_buy_progress_tool(repo)
    out = asyncio.run(tool.ainvoke({"user_id": "u_test", "team_id": "team_001"}))
    print("[progress tool]", out)
    assert "3" in out and "5" in out and "2" in out, out


def test_complete_mapping_not_complete() -> None:
    """lockCount(3) < targetCount(5) -> 未成团。"""
    repo = _make_repo({"targetCount": 5, "lockCount": 3, "completeCount": 3, "validEndTime": "2026-07-10T20:00:00"})
    t = asyncio.run(repo.get_complete_status("u_test", "team_001"))
    print("[complete not-done]", t.model_dump())
    assert t.is_complete is False
    assert t.complete_at is None


def test_complete_mapping_complete() -> None:
    """lockCount(5) >= targetCount(5) -> 已成团。"""
    repo = _make_repo({"targetCount": 5, "lockCount": 5, "completeCount": 5, "validEndTime": "2026-07-09T10:00:00"}, team_id="team_002")
    t = asyncio.run(repo.get_complete_status("u_test", "team_002"))
    print("[complete done]", t.model_dump())
    assert t.is_complete is True
    assert t.complete_at is not None


def test_team_not_found() -> None:
    """teamId 不在用户订单里应抛 AppException。"""
    from common.exception import AppException

    repo = _make_repo({"targetCount": 5, "lockCount": 3, "completeCount": 3, "validEndTime": "x"})
    raised = False
    try:
        asyncio.run(repo.get_progress("u_test", "team_999"))
    except AppException:
        raised = True
    assert raised, "未找到 team 应抛 AppException"


def test_balance_graceful() -> None:
    """T-3 余额无接口，工具应降级返回友好提示而非抛错。"""
    repo = _make_repo({"targetCount": 5, "lockCount": 3, "completeCount": 3, "validEndTime": "x"})
    tool = build_balance_usage_tool(repo)
    out = asyncio.run(tool.ainvoke({"user_id": "u_test"}))
    print("[balance tool]", out)
    assert "暂未开放" in out, out


if __name__ == "__main__":
    test_progress_mapping()
    test_progress_tool_format()
    test_complete_mapping_not_complete()
    test_complete_mapping_complete()
    test_team_not_found()
    test_balance_graceful()
    print("\n阶段 3 字段映射验证通过 ✓")
