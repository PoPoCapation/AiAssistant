"""应用配置（Pydantic Settings，读取项目根目录 ``.env``）。

对应 PRD ``app/config/settings.py``。环境变量见 ``.env.example``。
字段名小写、大小写不敏感，自动映射环境变量（如 ``DEEPSEEK_API_KEY`` -> ``deepseek_api_key``）。
"""
from __future__ import annotations

from pathlib import Path

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

    # ---- RAG（预留，本期不启用）----
    rag_enabled: bool = False


settings = Settings()
