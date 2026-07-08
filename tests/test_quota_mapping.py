"""阶段 3 用户额度映射验证（fake Redis + fake MySQL，无需在线）。

验证 ``UserQuotaRepositoryImpl`` 把 ai-agent-scaffold-draw-io 的 quota 数据
（Redis ``user_quota:{userId}`` 剩余 + MySQL ``user_quota`` 总额/已用 +
``user_quota_usage`` 流水）正确映射成 ``BalanceUsage``。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import infrastructure.adapter.repository.user_quota_repository_impl as quota_mod
from domain.mcp.service.tools.balance_usage_tool import build_balance_usage_tool
from infrastructure.adapter.repository.user_quota_repository_impl import UserQuotaRepositoryImpl


class FakeMysql:
    def __init__(self, quota_row: dict | None = None, usage_rows: list[dict] | None = None) -> None:
        self._quota = quota_row
        self._usage = usage_rows

    async def fetch_one(self, sql: str, args: tuple | None = None) -> dict | None:
        return self._quota  # 只用于查 user_quota

    async def fetch_all(self, sql: str, args: tuple | None = None) -> list[dict]:
        return self._usage or []


class FakeRedis:
    def __init__(self, value: str | None = None) -> None:
        self._v = value

    async def get(self, key: str) -> str | None:
        return self._v


def _patch_redis(value: str | None) -> None:
    """让额度仓储内的 get_redis_client 返回 FakeRedis。"""
    quota_mod.get_redis_client = lambda db=None: FakeRedis(value=value)


def test_quota_mapping() -> None:
    """Redis 剩余 50 + MySQL 总额 100/已用 50 + 1 条流水。"""
    _patch_redis("50")
    mysql = FakeMysql(
        quota_row={"quota_count": 100, "used": 50},
        usage_rows=[{"order_no": "69065413", "quota_count": 50, "biz_type": "team_success"}],
    )
    repo = UserQuotaRepositoryImpl(mysql=mysql, quota_db="xfg_frame_archetype", quota_redis_db=0)
    b = asyncio.run(repo.get_balance_usage("xxx3"))
    print("\n[quota]", b.model_dump())
    assert b.total_quota == 100
    assert b.used == 50
    assert b.remaining == 50
    assert len(b.recent_grants) == 1
    assert "team_success" in b.recent_grants[0]


def test_quota_no_redis_key() -> None:
    """Redis 无键 -> remaining=0（与 getRemainingQuota 一致），总额仍来自 MySQL。"""
    _patch_redis(None)
    mysql = FakeMysql(quota_row={"quota_count": 220, "used": 0}, usage_rows=[])
    repo = UserQuotaRepositoryImpl(mysql=mysql, quota_db="xfg", quota_redis_db=0)
    b = asyncio.run(repo.get_balance_usage("admin"))
    print("[quota no-redis]", b.model_dump())
    assert b.remaining == 0
    assert b.total_quota == 220


def test_balance_tool_format() -> None:
    _patch_redis("50")
    mysql = FakeMysql(
        quota_row={"quota_count": 100, "used": 50},
        usage_rows=[{"order_no": "o1", "quota_count": 50, "biz_type": "team_success"}],
    )
    repo = UserQuotaRepositoryImpl(mysql=mysql, quota_db="xfg", quota_redis_db=0)
    tool = build_balance_usage_tool(repo)
    out = asyncio.run(tool.ainvoke({"user_id": "xxx3"}))
    print("[balance tool]", out)
    assert "100" in out and "50" in out and "team_success" in out, out


if __name__ == "__main__":
    test_quota_mapping()
    test_quota_no_redis_key()
    test_balance_tool_format()
    print("\n阶段 3 用户额度映射验证通过 ✓")
