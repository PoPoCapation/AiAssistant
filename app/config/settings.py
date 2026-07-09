"""应用配置（Pydantic Settings，读取项目根目录 ``.env``）。

对应 PRD ``app/config/settings.py``。环境变量见 ``.env.example``。
字段名小写、大小写不敏感，自动映射环境变量（如 ``DEEPSEEK_API_KEY`` -> ``deepseek_api_key``）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/config/settings.py -> app/config -> app -> 项目根
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- DeepSeek LLM ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---- Redis（多轮会话存储）----
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # ---- 业务数据网关（group-buy-market）----
    groupbuy_api_base: str = "http://localhost:8091"

    # ---- MySQL（直查 group_buy_market 库，工具真实数据来源）----
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "group_buy_market"

    # ---- 用户额度（ai-agent-scaffold-draw-io 的 quota，Redis+MySQL 双写）----
    quota_redis_db: int = 0  # quota 存在默认 db=0
    quota_mysql_database: str = "xfg_frame_archetype"  # quota 表所在库

    # ---- 应用 ----
    app_host: str = "0.0.0.0"
    app_port: int = 8088
    app_debug: bool = False

    # ---- 会话 ----
    # 20 轮 1天
    session_max_turns: int = 20
    session_ttl_seconds: int = 86400

    # ---- RAG（向量存储 Qdrant）----
    rag_enabled: bool = False
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "ai_assistant"
    qdrant_prefer_grpc: bool = False
    qdrant_grpc_port: int = 6334
    qdrant_timeout_seconds: int = 5
    qdrant_replicas: int = 1

    # ---- 嵌入模型 & 切块策略 ----
    embedding_provider: Literal["dashscope", "openai", "local"] = "dashscope"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 32
    embedding_chunk_size: int = 512
    embedding_chunk_overlap: int = 100
    embedding_cache_dir: str = str(_PROJECT_ROOT / "storage" / "embedding_cache")

    # ---- RAG 模型（阿里云百炼 DashScope）----
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "qwen3-vl-embedding"
    embedding_model_sync: str = "text-embedding-v4"
    embedding_model_async: str = "text-embedding-async-v2"
    rerank_model: str = "qwen3-vl-rerank"

    # ---- RAG 文本 / PDF 解析 ----
    rag_source_dir: str = str(_PROJECT_ROOT / "storage" / "rag_sources")
    rag_allow_pdf: bool = True
    rag_allow_text: bool = True
    rag_pdf_ocr_enabled: bool = True
    rag_pdf_ocr_provider: Literal["tesseract", "dashscope", "none"] = "tesseract"
    rag_ingest_concurrency: int = 4
    rag_ingest_batch_size: int = 20


settings = Settings()
