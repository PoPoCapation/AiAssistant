"""对话 SSE 流式接口（对应 IMPL 阶段 4.1）。

``POST /api/v1/assistant/chat``：SSE 流式，事件格式：
- token：``data: {"token": "..."}\n\n``
- 工具：``data: {"tool": "...", "args": {...}}\n\n``
- 结束：``data: [DONE]\n\n``
- 异常：``data: {"error": "..."}\n\n``（不返回 500，PRD 4.2）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.dto.chat import ChatRequest
from app.dependency import get_assistant_service
from domain.assistant.service.assistant_service import IAssistantService

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def chat(req: ChatRequest, svc: IAssistantService = Depends(get_assistant_service)):
    """SSE 流式对话。"""
    return StreamingResponse(svc.chat_stream(req), media_type="text/event-stream")
