"""非流式对话接口（对应 PRD ``assistant_controller``）。

``POST /api/v1/assistant/chat/sync``：返回统一 ``Response<ChatResponse>``。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dto.chat import ChatRequest
from api.response import Response
from app.dependency import get_assistant_service
from domain.assistant.service.assistant_service import IAssistantService

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat/sync")
async def chat_sync(req: ChatRequest, svc: IAssistantService = Depends(get_assistant_service)):
    """非流式对话：一次性返回完整回复。"""
    resp = await svc.chat(req)
    return Response.success(resp)
