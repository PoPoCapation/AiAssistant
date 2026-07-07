"""智能助手单轮服务（领域层）。

对应 IMPL 阶段 1.4：``IAssistantService.chat(req)`` -> 调 ``ILLMPort``。
领域服务仅依赖 ``ILLMPort`` 端口，具体实现由 infrastructure 注入。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from api.dto.chat import ChatMessageDTO, ChatRequest, ChatResponse
from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.port.illm_port import ILLMPort

# 默认系统提示：客服助手定位（参考 PRD 第八章业务边界）
_DEFAULT_SYSTEM_PROMPT = (
    "你是「拼团营销平台」的智能客服助手。请用简洁、专业的中文回答用户关于拼团进度、"
    "成团状态、账户余额、活动规则、退款等问题。涉及用户真实业务数据时，仅依据工具返回"
    "结果作答，不要编造。无法确认意图时，先追问一个最小必要信息。"
)

# 角色 -> LangChain 消息类型
_ROLE_TO_MSG = {
    "user": HumanMessage,
    "assistant": AIMessage,
}


def _to_messages(req: ChatRequest, system_prompt: str) -> List[BaseMessage]:
    """把 ChatRequest 转成 LangChain 消息列表（system + history + 本轮）。"""
    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    for m in req.history:
        cls = _ROLE_TO_MSG.get(m.role.lower())
        if cls is not None:
            messages.append(cls(content=m.content))
        # system 角色历史忽略：已用统一 system_prompt
    messages.append(HumanMessage(content=req.message))
    return messages


class IAssistantService(ABC):
    """智能助手服务接口。"""

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """单轮对话：根据请求调用 LLM，返回回复。"""


class AssistantServiceImpl(IAssistantService):
    """单轮助手服务实现：组装消息 -> 调 LLM 端口 -> 包装响应。"""

    def __init__(self, llm_port: ILLMPort, system_prompt: str = _DEFAULT_SYSTEM_PROMPT) -> None:
        self._llm_port = llm_port
        self._system_prompt = system_prompt

    async def chat(self, req: ChatRequest) -> ChatResponse:
        if not req.message or not req.message.strip():
            raise AppException(ResponseCode.ILLEGAL_PARAMETER, "消息内容不能为空")

        messages = _to_messages(req, self._system_prompt)
        try:
            reply = await self._llm_port.chat(messages)
        except AppException:
            # 端口已抛出带码异常，原样上抛
            raise
        except Exception as e:  # 兜底：未知异常归一为 LLM_ERROR
            raise AppException(
                ResponseCode.LLM_ERROR,
                str(e) or ResponseCode.LLM_ERROR.info,
                cause=e,
            ) from e

        return ChatResponse(
            session_id=req.session_id,
            user_id=req.user_id,
            reply=reply,
        )
