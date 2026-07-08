"""智能助手服务实现（领域层）。

对应 IMPL 阶段 2：通过 LangGraph 工作流 + 会话仓储实现多轮对话。
- ``session_id`` 缺省则新建；
- 调用前 ``load`` 历史、调用后 ``save`` 历史；
- graph 负责 LLM 工作流（intent/tool/response），service 负责持久化编排。
接口定义见 ``assistant_service.py``。
"""
from __future__ import annotations

import uuid
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from api.dto.chat import ChatRequest, ChatResponse
from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.adapter.repository.isession_repository import ISessionRepository
from domain.assistant.service.assistant_service import IAssistantService

# 默认系统提示：客服助手定位（参考 PRD 第八章业务边界）
_DEFAULT_SYSTEM_PROMPT = (
    "你是「拼团营销平台」的智能客服助手。请用简洁、专业的中文回答用户关于拼团进度、"
    "成团状态、账户余额、活动规则、退款等问题。涉及用户真实业务数据时，仅依据工具返回"
    "结果作答，不要编造。无法确认意图时，先追问一个最小必要信息。"
)

# 角色 -> LangChain 消息类型（保留供流式测试 / 手动组装使用）
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


def _last_ai_text(messages: List[BaseMessage]) -> str:
    """取消息列表中最后一条 AIMessage 的文本。"""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            return content if isinstance(content, str) else str(content)
    return ""


class AssistantServiceImpl(IAssistantService):
    """多轮助手服务实现：load 历史 -> 跑 graph -> save 历史。"""

    def __init__(
        self,
        llm_port: ILLMPort,
        session_repo: ISessionRepository,
        graph,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._llm_port = llm_port
        self._session_repo = session_repo
        self._graph = graph
        self._system_prompt = system_prompt

    async def chat(self, req: ChatRequest) -> ChatResponse:
        if not req.message or not req.message.strip():
            raise AppException(ResponseCode.ILLEGAL_PARAMETER, "消息内容不能为空")

        # session_id 缺省新建（同一 session_id 复用历史 -> 多轮记忆）
        session_id = req.session_id or str(uuid.uuid4())

        # 1) 加载历史（不含 system prompt）
        history = await self._session_repo.load(session_id)

        # 系统提示追加用户上下文：让 LLM 调用工具时能带上 user_id
        system_prompt = (
            f"{self._system_prompt}\n\n[当前上下文] 用户ID：{req.user_id}；会话ID：{session_id}。"
            "查询用户数据时请使用此 user_id。"
        )

        # 2) 组装初始状态，交给 graph
        initial_state = {
            "messages": history + [HumanMessage(content=req.message)],
            "user_id": req.user_id,
            "session_id": session_id,
            "system_prompt": system_prompt,
            "intent": None,
            "tool_results": [],
        }
        try:
            result = await self._graph.ainvoke(initial_state)
        except AppException:
            raise
        except Exception as e:  # graph 内未知异常归一为 LLM_ERROR
            raise AppException(
                ResponseCode.LLM_ERROR,
                str(e) or ResponseCode.LLM_ERROR.info,
                cause=e,
            ) from e

        # 3) 取最终回答
        reply = _last_ai_text(result.get("messages", []))

        # 4) 持久化更新后的历史（含本轮 user + assistant），不存 system
        await self._session_repo.save(session_id, result.get("messages", []))

        return ChatResponse(
            session_id=session_id,
            user_id=req.user_id,
            reply=reply,
            intent=result.get("intent"),
        )
