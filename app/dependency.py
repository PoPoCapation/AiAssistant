"""依赖注入装配（对应 PRD ``app/dependency.py``）。

把 infrastructure 的实现注入 domain/trigger。Phase 1 仅装配 LLM 端口 + 单轮服务。
后续 Phase 2/3 在此追加会话仓储、Graph、工具等。
"""
from __future__ import annotations

from functools import lru_cache

from app.config.settings import settings
from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.service.assistant_service import IAssistantService
from domain.assistant.service.assistant_service_impl import AssistantServiceImpl
from infrastructure.adapter.port.deepseek_llm_adapter import DeepSeekLLMAdapter
from infrastructure.llm.deepseek_chat import build_deepseek_chat


@lru_cache(maxsize=1)
def get_llm_port() -> ILLMPort:
    """单例 LLM 端口（DeepSeek 实现）。"""
    return DeepSeekLLMAdapter(build_deepseek_chat())


@lru_cache(maxsize=1)
def get_assistant_service() -> IAssistantService:
    """单例单轮助手服务。"""
    return AssistantServiceImpl(get_llm_port())


# 便于被 trigger/controller 直接 Depends 引用（Phase 4）
def get_settings():
    return settings
