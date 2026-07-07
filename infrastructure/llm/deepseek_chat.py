"""LangChain ChatOpenAI（DeepSeek）封装。

对应 IMPL 阶段 1.2：用 ``ChatOpenAI(model=deepseek-chat, base_url=DEEPSEEK_BASE_URL, api_key=...)``。
DeepSeek 提供 OpenAI 兼容接口，故直接复用 ``langchain_openai.ChatOpenAI``。
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config.settings import settings


def build_deepseek_chat() -> ChatOpenAI:
    """构造指向 DeepSeek 的 ``ChatOpenAI`` 实例。"""
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY 未配置，请检查 .env / 环境变量")
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=60,
        max_retries=2,
    )
