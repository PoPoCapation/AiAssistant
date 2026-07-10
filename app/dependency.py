"""依赖注入装配（对应 PRD ``app/dependency.py``）。

把 infrastructure 的实现注入 domain/trigger。
- Phase 1：LLM 端口；
- Phase 2：会话仓储(Redis) + LangGraph 工作流 + 助手服务；
- Phase 3：拼团仓储(MySQL 直查) + 用户额度仓储(Redis+MySQL 双读) + 3 个 @tool，注入 graph。
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
from domain.mcp.adapter.repository.iuser_quota_repository import IUserQuotaRepository
from domain.mcp.service.tools.balance_usage_tool import build_balance_usage_tool
from domain.mcp.service.tools.group_buy_progress_tool import build_group_buy_progress_tool
from domain.mcp.service.tools.group_complete_tool import build_group_complete_tool
from infrastructure.adapter.port.deepseek_llm_adapter import DeepSeekLLMAdapter
from infrastructure.adapter.repository.groupbuy_repository_impl import GroupBuyRepositoryImpl
from infrastructure.adapter.repository.redis_session_repository import RedisSessionRepository
from infrastructure.adapter.repository.user_quota_repository_impl import UserQuotaRepositoryImpl
from infrastructure.llm.deepseek_chat import build_deepseek_chat
from infrastructure.mysql.mysql_client import MysqlClient
from infrastructure.redis.redis_client import get_redis_client
from domain.rag.adapter.port.iembedding_port import IEmbeddingService
from domain.rag.adapter.port.irerank_port import IRerankService
from domain.rag.adapter.repository.ivector_repository import IVectorRepository
from domain.rag.service.retrieval_service import IRetrievalService
from domain.rag.service.tools.knowledge_search_tool import build_knowledge_search_tool
from infrastructure.rag.embedding_service import DashScopeEmbeddingService
from infrastructure.rag.qdrant_repository import QdrantVectorRepository
from infrastructure.rag.rerank_service import DashScopeRerankService
from infrastructure.rag.retrieval_service_impl import RetrievalServiceImpl
from infrastructure.rag.pdf_extractor import PdfOcrExtractor


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
    """单例拼团业务仓储：直查 group_buy_market MySQL。"""
    return GroupBuyRepositoryImpl(MysqlClient())


@lru_cache(maxsize=1)
def get_user_quota_repository() -> IUserQuotaRepository:
    """单例用户额度仓储：Redis(db=0) + MySQL(xfg_frame_archetype) 双读。"""
    return UserQuotaRepositoryImpl(
        mysql=MysqlClient(),
        quota_db=settings.quota_mysql_database,
        quota_redis_db=settings.quota_redis_db,
    )


@lru_cache(maxsize=1)
def get_embedding_service() -> IEmbeddingService:
    """单例嵌入服务（百炼 text-embedding-v4，1024 维）。"""
    return DashScopeEmbeddingService(
        settings.dashscope_api_key, settings.dashscope_base_url, settings.embedding_model_sync
    )


@lru_cache(maxsize=1)
def get_rerank_service() -> IRerankService:
    """单例重排序服务（百炼 qwen3-vl-rerank）。"""
    return DashScopeRerankService(settings.dashscope_api_key, settings.rerank_model)


@lru_cache(maxsize=1)
def get_vector_repository() -> IVectorRepository:
    """单例 Qdrant 向量仓储（Cosine）。"""
    return QdrantVectorRepository(
        settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection, dim=1024
    )


@lru_cache(maxsize=1)
def get_retrieval_service() -> IRetrievalService:
    """单例 RAG 检索服务：嵌入 + Qdrant 召回 + rerank。"""
    return RetrievalServiceImpl(
        get_embedding_service(), get_vector_repository(), get_rerank_service()
    )


@lru_cache(maxsize=1)
def get_pdf_extractor() -> PdfOcrExtractor:
    """单例 PDF OCR 提取器（百炼 qwen-vl-ocr）。"""
    return PdfOcrExtractor(settings.dashscope_api_key)


@lru_cache(maxsize=1)
def get_groupbuy_tools() -> list:
    """单例工具列表：拼团进度 / 成团 / 余额；rag_enabled 时追加 knowledge_search（RAG）。"""
    gb_repo = get_groupbuy_repository()
    quota_repo = get_user_quota_repository()
    tools = [
        build_group_buy_progress_tool(gb_repo),
        build_group_complete_tool(gb_repo),
        build_balance_usage_tool(quota_repo),
    ]
    if settings.rag_enabled:
        tools.append(build_knowledge_search_tool(get_retrieval_service()))
    return tools


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
