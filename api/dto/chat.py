"""对话相关 DTO（对应 PRD ``api/dto/chat.py``）。

请求体见 PRD 5.1：``{ session_id?, user_id, message }``。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessageDTO(BaseModel):
    """单条消息（角色 + 内容），用于历史/多轮上下文。"""

    role: str = Field(..., description="消息角色：system / user / assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求。"""

    user_id: str = Field(..., description="用户标识")
    message: str = Field(..., description="本轮用户消息")
    session_id: Optional[str] = Field(default=None, description="会话 ID，缺省表示新建")
    history: List[ChatMessageDTO] = Field(
        default_factory=list, description="历史消息（单轮可空，多轮由会话仓储维护）"
    )


class ChatResponse(BaseModel):
    """对话响应（非流式）。"""

    session_id: Optional[str] = None
    user_id: str
    reply: str = Field(..., description="助手回复内容")
    intent: Optional[str] = Field(default=None, description="意图（Phase 2+ 填充）")
