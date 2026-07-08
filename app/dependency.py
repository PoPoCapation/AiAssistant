"""依赖注入装配（对应 PRD ``app/dependency.py``）。

把 infrastructure 的实现注入 domain/trigger。
- Phase 1：LLM 端口；
- Phase 2：会话仓储(Redis) + LangGraph 工作流 + 助手服务；
- Phase 3：拼团业务仓储(stub) + 3 个 @tool 工具，注入 graph。
"""
from __future__ import annotations

from functools import lru_cache

from app.config.settings import settings
from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.adapter.repository.isession_repository import ISessionRepository
from domain.assistant.service.assistant_service import IAssistantService
from domain.assistant.service.assistant_service_impl import AssistantServiceImpl
from domain.assistant.service.graph.assistant_graph import build_assistant_graph
from domain.mcp.adapter.repository.igroupbuy_repository import IGroupBuyRepository
from domain.mcp.service.tools.balance_usage_tool import build_balance_usage_tool
from domain.mcp.service.tools.group_buy_progress_tool import build_group_buy_progress_tool
from domain.mcp.service.tools.group_complete_tool import build_group_complete_tool
from infrastructure.adapter.port.deepseek_llm_adapter import DeepSeekLLMAdapter
from infrastructure.adapter.repository.groupbuy_repository_impl import GroupBuyRepositoryImpl
from infrastructure.gateway.groupbuy_gateway import GroupBuyGateway
from infrastructure.adapter.repository.redis_session_repository import RedisSessionRepository
from infrastructure.llm.deepseek_chat import build_deepseek_chat
from infrastructure.redis.redis_client import get_redis_client


@lru_cache(maxsize=1)
def get_llm_port() -> ILLMPort:
    """单例 LLM 端口（DeepSeek 实现）。"""
    return DeepSeekLLMAdapter(build_deepseek_chat())


@lru_cache(maxsize=1)
def get_session_repository() -> ISessionRepository:
    """单例会话仓储（Redis 实现）。客户端按 loop 在仓储内部按需获取。"""
    return RedisSessionRepository(
        client_factory=get_redis_client,
        max_turns=settings.session_max_turns,
        ttl_seconds=settings.session_ttl_seconds,
    )


@lru_cache(maxsize=1)
def get_groupbuy_repository() -> IGroupBuyRepository:
    """单例拼团业务仓储：通过 GroupBuyGateway 调真实 group-buy-market（T-3 余额无接口，降级）。"""
    gateway = GroupBuyGateway(
        base_url=settings.groupbuy_api_base,
        source=settings.groupbuy_source,
        channel=settings.groupbuy_channel,
    )
    return GroupBuyRepositoryImpl(gateway)


@lru_cache(maxsize=1)
def get_groupbuy_tools() -> list:
    """单例工具列表：拼团进度 / 成团 / 余额。"""
    repo = get_groupbuy_repository()
    return [
        build_group_buy_progress_tool(repo),
        build_group_complete_tool(repo),
        build_balance_usage_tool(repo),
    ]


@lru_cache(maxsize=1)
def get_assistant_graph():
    """单例 LangGraph 工作流（注入 LLM 端口 + 工具列表）。"""
    return build_assistant_graph(get_llm_port(), tools=get_groupbuy_tools())


@lru_cache(maxsize=1)
def get_assistant_service() -> IAssistantService:
    """单例助手服务：注入 LLM 端口 + 会话仓储 + 工作流。"""
    return AssistantServiceImpl(
        llm_port=get_llm_port(),
        session_repo=get_session_repository(),
        graph=get_assistant_graph(),
    )


# 便于被 trigger/controller 直接 Depends 引用（Phase 4）
def get_settings():
    return settings
