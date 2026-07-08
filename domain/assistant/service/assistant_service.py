"""智能助手服务接口（领域层）。

对应 IMPL 阶段 1.4：``IAssistantService.chat(req)``。
接口与实现分离（对齐 Java 习惯：接口与 Impl 分文件），实现见 ``assistant_service_impl.py``。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from api.dto.chat import ChatRequest, ChatResponse


class IAssistantService(ABC):
    """智能助手服务接口。"""

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """单轮对话：根据请求调用 LLM，返回回复。"""
